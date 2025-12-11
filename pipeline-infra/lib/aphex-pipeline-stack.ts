import * as cdk from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as eks from 'aws-cdk-lib/aws-eks';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as s3 from 'aws-cdk-lib/aws-s3';
import { Construct } from 'constructs';
import * as path from 'path';
import { ConfigParser } from './config-parser';
import { WorkflowTemplateGenerator } from './workflow-template-generator';

export interface AphexPipelineStackProps extends cdk.StackProps {
  /**
   * Path to the aphex-config.yaml file.
   * Defaults to '../aphex-config.yaml' (relative to pipeline-infra directory).
   */
  configPath?: string;
}

export class AphexPipelineStack extends cdk.Stack {
  public readonly cluster: eks.Cluster;
  public readonly clusterName: string;
  public readonly argoWorkflowsUrl: string;
  public readonly argoEventsWebhookUrl: string;
  public readonly artifactBucketName: string;
  public readonly workflowExecutionRoleArn: string;

  constructor(scope: Construct, id: string, props?: AphexPipelineStackProps) {
    super(scope, id, props);

    // Parse aphex-config.yaml
    const configPath = props?.configPath || path.join(__dirname, '../../aphex-config.yaml');
    const aphexConfig = ConfigParser.parse(configPath);

    // Create VPC for EKS cluster
    const vpc = new ec2.Vpc(this, 'AphexPipelineVpc', {
      maxAzs: 3,
      natGateways: 1,
      subnetConfiguration: [
        {
          cidrMask: 24,
          name: 'Public',
          subnetType: ec2.SubnetType.PUBLIC,
        },
        {
          cidrMask: 24,
          name: 'Private',
          subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
        },
      ],
    });

    // Create kubectl layer - CDK will use this for kubectl operations
    // Using a minimal layer that CDK will populate with kubectl binary
    const kubectlLayer = lambda.LayerVersion.fromLayerVersionArn(
      this,
      'KubectlLayer',
      `arn:aws:lambda:${this.region}:${this.account}:layer:kubectl:1`
    );

    // Create EKS cluster
    this.cluster = new eks.Cluster(this, 'AphexPipelineCluster', {
      version: eks.KubernetesVersion.V1_28,
      vpc,
      vpcSubnets: [{ subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS }],
      defaultCapacity: 0, // We'll add managed node groups separately
      clusterName: 'aphex-pipeline-cluster',
      kubectlLayer,
    });

    // Add managed node group with autoscaling
    this.cluster.addNodegroupCapacity('AphexPipelineNodeGroup', {
      instanceTypes: [
        new ec2.InstanceType('t3.medium'),
        new ec2.InstanceType('t3.large'),
      ],
      minSize: 2,
      maxSize: 10,
      desiredSize: 3,
      diskSize: 50,
      amiType: eks.NodegroupAmiType.AL2_X86_64,
      capacityType: eks.CapacityType.ON_DEMAND,
    });

    // Store cluster name
    this.clusterName = this.cluster.clusterName;

    // Create namespace for Argo Workflows
    const argoNamespace = this.cluster.addManifest('ArgoNamespace', {
      apiVersion: 'v1',
      kind: 'Namespace',
      metadata: {
        name: 'argo',
      },
    });

    // Install Argo Workflows via Helm
    const argoWorkflows = this.cluster.addHelmChart('ArgoWorkflows', {
      chart: 'argo-workflows',
      repository: 'https://argoproj.github.io/argo-helm',
      namespace: 'argo',
      release: 'argo-workflows',
      version: '0.41.0',
      values: {
        server: {
          enabled: true,
          serviceType: 'LoadBalancer',
          extraArgs: ['--auth-mode=server'],
        },
        controller: {
          enabled: true,
        },
        executor: {
          enabled: true,
        },
      },
    });
    argoWorkflows.node.addDependency(argoNamespace);

    // Create namespace for Argo Events
    const argoEventsNamespace = this.cluster.addManifest('ArgoEventsNamespace', {
      apiVersion: 'v1',
      kind: 'Namespace',
      metadata: {
        name: 'argo-events',
      },
    });

    // Install Argo Events via Helm
    const argoEvents = this.cluster.addHelmChart('ArgoEvents', {
      chart: 'argo-events',
      repository: 'https://argoproj.github.io/argo-helm',
      namespace: 'argo-events',
      release: 'argo-events',
      version: '2.4.0',
      values: {
        controller: {
          enabled: true,
        },
      },
    });
    argoEvents.node.addDependency(argoEventsNamespace);

    // Create EventBus for Argo Events
    const eventBus = this.cluster.addManifest('ArgoEventBus', {
      apiVersion: 'argoproj.io/v1alpha1',
      kind: 'EventBus',
      metadata: {
        name: 'default',
        namespace: 'argo-events',
      },
      spec: {
        nats: {
          native: {
            replicas: 3,
            auth: 'none',
          },
        },
      },
    });
    eventBus.node.addDependency(argoEvents);

    // Create service account for workflow execution with IRSA
    const workflowServiceAccount = this.cluster.addServiceAccount('WorkflowExecutionServiceAccount', {
      name: 'workflow-executor',
      namespace: 'argo',
    });
    workflowServiceAccount.node.addDependency(argoNamespace);

    // Add IAM policies for workflow execution
    // S3 access for artifacts
    workflowServiceAccount.addToPrincipalPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          's3:GetObject',
          's3:PutObject',
          's3:DeleteObject',
          's3:ListBucket',
        ],
        resources: ['*'], // Will be restricted to specific bucket in task 2.5
      })
    );

    // CloudFormation access for CDK deployments
    workflowServiceAccount.addToPrincipalPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          'cloudformation:*',
          'sts:AssumeRole',
        ],
        resources: ['*'],
      })
    );

    // IAM access for cross-account role assumption
    workflowServiceAccount.addToPrincipalPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          'iam:PassRole',
          'iam:GetRole',
        ],
        resources: ['*'],
      })
    );

    // ECR access for container images
    workflowServiceAccount.addToPrincipalPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          'ecr:GetAuthorizationToken',
          'ecr:BatchCheckLayerAvailability',
          'ecr:GetDownloadUrlForLayer',
          'ecr:BatchGetImage',
        ],
        resources: ['*'],
      })
    );

    // Store workflow execution role ARN
    this.workflowExecutionRoleArn = workflowServiceAccount.role.roleArn;

    // Create S3 bucket for build artifacts
    const artifactBucket = new s3.Bucket(this, 'ArtifactBucket', {
      bucketName: `aphex-pipeline-artifacts-${this.account}-${this.region}`,
      encryption: s3.BucketEncryption.S3_MANAGED,
      versioned: true,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      lifecycleRules: [
        {
          id: 'DeleteOldArtifacts',
          enabled: true,
          expiration: cdk.Duration.days(90),
          noncurrentVersionExpiration: cdk.Duration.days(30),
        },
      ],
    });

    // Grant the workflow service account access to the artifact bucket
    artifactBucket.grantReadWrite(workflowServiceAccount.role);

    // Store artifact bucket name
    this.artifactBucketName = artifactBucket.bucketName;

    // Generate and apply WorkflowTemplate based on aphex-config.yaml
    const workflowGenerator = new WorkflowTemplateGenerator(
      aphexConfig,
      this.artifactBucketName,
      'workflow-executor'
    );
    const workflowTemplate = workflowGenerator.generate();

    // Apply WorkflowTemplate to the cluster
    const workflowTemplateManifest = this.cluster.addManifest('AphexPipelineWorkflowTemplate', workflowTemplate);
    workflowTemplateManifest.node.addDependency(argoWorkflows);
    workflowTemplateManifest.node.addDependency(workflowServiceAccount);

    // Placeholder values for components to be implemented in subsequent tasks
    // Argo Workflows URL will be the LoadBalancer DNS
    this.argoWorkflowsUrl = 'http://<LoadBalancer-DNS>:2746';
    this.argoEventsWebhookUrl = '';

    // Stack outputs
    new cdk.CfnOutput(this, 'ClusterName', {
      value: this.cluster.clusterName,
      description: 'EKS Cluster Name',
      exportName: 'AphexPipelineClusterName',
    });

    new cdk.CfnOutput(this, 'ClusterArn', {
      value: this.cluster.clusterArn,
      description: 'EKS Cluster ARN',
    });

    new cdk.CfnOutput(this, 'KubectlRoleArn', {
      value: this.cluster.kubectlRole?.roleArn || 'N/A',
      description: 'IAM Role ARN for kubectl access',
    });

    new cdk.CfnOutput(this, 'ArgoWorkflowsUrl', {
      value: this.argoWorkflowsUrl,
      description: 'Argo Workflows UI URL (LoadBalancer DNS will be available after deployment)',
    });

    new cdk.CfnOutput(this, 'ArgoEventsWebhookUrl', {
      value: this.argoEventsWebhookUrl || 'To be configured after EventSource deployment',
      description: 'Argo Events Webhook URL for GitHub integration',
    });

    new cdk.CfnOutput(this, 'ArtifactBucketName', {
      value: this.artifactBucketName,
      description: 'S3 Bucket for build artifacts',
      exportName: 'AphexPipelineArtifactBucket',
    });

    new cdk.CfnOutput(this, 'WorkflowExecutionRoleArn', {
      value: this.workflowExecutionRoleArn,
      description: 'IAM Role ARN for workflow execution (IRSA)',
      exportName: 'AphexPipelineWorkflowExecutionRole',
    });

    new cdk.CfnOutput(this, 'VpcId', {
      value: vpc.vpcId,
      description: 'VPC ID for the EKS cluster',
    });
  }
}
