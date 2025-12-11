import * as cdk from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as eks from 'aws-cdk-lib/aws-eks';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';
import { Construct } from 'constructs';
import * as path from 'path';
import * as fs from 'fs';
import * as jsyaml from 'js-yaml';
import { ConfigParser } from './config-parser';
import { WorkflowTemplateGenerator } from './workflow-template-generator';

export interface AphexPipelineStackProps extends cdk.StackProps {
  // ===== Required Parameters =====
  
  /**
   * GitHub repository owner (organization or user)
   * @example 'my-org'
   */
  githubOwner: string;
  
  /**
   * GitHub repository name
   * @example 'my-repo'
   */
  githubRepo: string;
  
  /**
   * AWS Secrets Manager secret name containing GitHub token
   * The secret should contain a token with 'repo' scope
   * @example 'github-token'
   */
  githubTokenSecretName: string;
  
  // ===== Optional Configuration =====
  
  /**
   * Path to aphex-config.yaml file
   * @default '../aphex-config.yaml'
   */
  configPath?: string;
  
  /**
   * GitHub branch to trigger on
   * @default 'main'
   */
  githubBranch?: string;
  
  /**
   * AWS Secrets Manager secret name for GitHub webhook validation
   * If not provided, webhook validation will be disabled
   */
  githubWebhookSecretName?: string;
  
  // ===== EKS Cluster Configuration =====
  
  /**
   * EKS cluster name
   * @default 'aphex-pipeline-cluster'
   */
  clusterName?: string;
  
  /**
   * Kubernetes version
   * @default eks.KubernetesVersion.V1_28
   */
  clusterVersion?: eks.KubernetesVersion;
  
  /**
   * Instance types for node group
   * @default [t3.medium, t3.large]
   */
  nodeInstanceTypes?: ec2.InstanceType[];
  
  /**
   * Minimum number of nodes
   * @default 2
   */
  minNodes?: number;
  
  /**
   * Maximum number of nodes
   * @default 10
   */
  maxNodes?: number;
  
  /**
   * Desired number of nodes
   * @default 3
   */
  desiredNodes?: number;
  
  // ===== Artifact Storage =====
  
  /**
   * S3 bucket name for artifacts
   * @default 'aphex-pipeline-artifacts-{account}-{region}'
   */
  artifactBucketName?: string;
  
  /**
   * Artifact retention in days
   * @default 90
   */
  artifactRetentionDays?: number;
  
  // ===== Argo Configuration =====
  
  /**
   * Argo Workflows Helm chart version
   * @default '0.41.0'
   */
  argoWorkflowsVersion?: string;
  
  /**
   * Argo Events Helm chart version
   * @default '2.4.0'
   */
  argoEventsVersion?: string;
  
  /**
   * Namespace for Argo Workflows
   * @default 'argo'
   */
  argoNamespace?: string;
  
  /**
   * Namespace for Argo Events
   * @default 'argo-events'
   */
  argoEventsNamespace?: string;
  
  // ===== Naming =====
  
  /**
   * EventSource name
   * @default 'github'
   */
  eventSourceName?: string;
  
  /**
   * Sensor name
   * @default 'aphex-pipeline-sensor'
   */
  sensorName?: string;
  
  /**
   * WorkflowTemplate name
   * @default 'aphex-pipeline-template'
   */
  workflowTemplateName?: string;
  
  /**
   * Service account name for workflow execution
   * @default 'workflow-executor'
   */
  serviceAccountName?: string;
  
  /**
   * Workflow name prefix for generated workflows
   * @default 'aphex-pipeline-'
   */
  workflowNamePrefix?: string;
  
  // ===== Container Images =====
  
  /**
   * Builder container image
   * @default 'public.ecr.aws/aphex/builder:latest'
   */
  builderImage?: string;
  
  /**
   * Deployer container image
   * @default 'public.ecr.aws/aphex/deployer:latest'
   */
  deployerImage?: string;
  
  // ===== Advanced =====
  
  /**
   * Use existing VPC instead of creating new one
   */
  vpc?: ec2.IVpc;
  
  /**
   * Custom EventSource template path
   */
  eventSourceTemplatePath?: string;
  
  /**
   * Custom Sensor template path
   */
  sensorTemplatePath?: string;
  
  /**
   * Custom logging config template path
   */
  loggingConfigTemplatePath?: string;
}

export class AphexPipelineStack extends cdk.Stack {
  public readonly cluster: eks.Cluster;
  public readonly clusterName: string;
  public readonly argoWorkflowsUrl: string;
  public readonly argoEventsWebhookUrl: string;
  public readonly artifactBucketName: string;
  public readonly workflowExecutionRoleArn: string;

  constructor(scope: Construct, id: string, props: AphexPipelineStackProps) {
    super(scope, id, props);

    // Validate required props
    if (!props.githubOwner || !props.githubRepo || !props.githubTokenSecretName) {
      throw new Error('githubOwner, githubRepo, and githubTokenSecretName are required');
    }

    // Set defaults
    const config = {
      githubBranch: props.githubBranch || 'main',
      clusterName: props.clusterName || 'aphex-pipeline-cluster',
      clusterVersion: props.clusterVersion || eks.KubernetesVersion.V1_28,
      argoNamespace: props.argoNamespace || 'argo',
      argoEventsNamespace: props.argoEventsNamespace || 'argo-events',
      serviceAccountName: props.serviceAccountName || 'workflow-executor',
      eventSourceName: props.eventSourceName || 'github',
      sensorName: props.sensorName || 'aphex-pipeline-sensor',
      workflowTemplateName: props.workflowTemplateName || 'aphex-pipeline-template',
      workflowNamePrefix: props.workflowNamePrefix || 'aphex-pipeline-',
      argoWorkflowsVersion: props.argoWorkflowsVersion || '0.41.0',
      argoEventsVersion: props.argoEventsVersion || '2.4.0',
      minNodes: props.minNodes || 2,
      maxNodes: props.maxNodes || 10,
      desiredNodes: props.desiredNodes || 3,
      nodeInstanceTypes: props.nodeInstanceTypes || [
        new ec2.InstanceType('t3.medium'),
        new ec2.InstanceType('t3.large'),
      ],
      artifactRetentionDays: props.artifactRetentionDays || 90,
      githubTokenSecretK8sName: 'github-access',
      githubWebhookSecretK8sName: 'github-webhook-secret',
    };

    // Parse aphex-config.yaml
    const configPath = props.configPath || path.join(__dirname, '../../aphex-config.yaml');
    const aphexConfig = ConfigParser.parse(configPath);

    // Create or use existing VPC
    const vpc = props.vpc || new ec2.Vpc(this, 'AphexPipelineVpc', {
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
      version: config.clusterVersion,
      vpc,
      vpcSubnets: [{ subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS }],
      defaultCapacity: 0, // We'll add managed node groups separately
      clusterName: config.clusterName,
      kubectlLayer,
    });

    // Add managed node group with autoscaling
    this.cluster.addNodegroupCapacity('AphexPipelineNodeGroup', {
      instanceTypes: config.nodeInstanceTypes,
      minSize: config.minNodes,
      maxSize: config.maxNodes,
      desiredSize: config.desiredNodes,
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
        name: config.argoNamespace,
      },
    });

    // Install Argo Workflows via Helm
    const argoWorkflows = this.cluster.addHelmChart('ArgoWorkflows', {
      chart: 'argo-workflows',
      repository: 'https://argoproj.github.io/argo-helm',
      namespace: config.argoNamespace,
      release: 'argo-workflows',
      version: config.argoWorkflowsVersion,
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
        name: config.argoEventsNamespace,
      },
    });

    // Install Argo Events via Helm
    const argoEvents = this.cluster.addHelmChart('ArgoEvents', {
      chart: 'argo-events',
      repository: 'https://argoproj.github.io/argo-helm',
      namespace: config.argoEventsNamespace,
      release: 'argo-events',
      version: config.argoEventsVersion,
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
        namespace: config.argoEventsNamespace,
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
      name: config.serviceAccountName,
      namespace: config.argoNamespace,
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
        ],
        resources: ['*'],
      })
    );

    // Cross-account IAM role assumption for deploying to different AWS accounts
    // This allows the workflow to assume roles in target accounts for cross-account deployments
    workflowServiceAccount.addToPrincipalPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          'sts:AssumeRole',
          'sts:GetCallerIdentity',
        ],
        resources: ['*'], // Allows assuming any role - can be restricted to specific role ARN patterns
      })
    );

    // IAM access for role management
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
      bucketName: props.artifactBucketName || `aphex-pipeline-artifacts-${this.account}-${this.region}`,
      encryption: s3.BucketEncryption.S3_MANAGED,
      versioned: true,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      lifecycleRules: [
        {
          id: 'DeleteOldArtifacts',
          enabled: true,
          expiration: cdk.Duration.days(config.artifactRetentionDays),
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
      config.serviceAccountName
    );
    const workflowTemplate = workflowGenerator.generate();

    // Apply WorkflowTemplate to the cluster
    const workflowTemplateManifest = this.cluster.addManifest('AphexPipelineWorkflowTemplate', workflowTemplate);
    workflowTemplateManifest.node.addDependency(argoWorkflows);
    workflowTemplateManifest.node.addDependency(workflowServiceAccount);

    // Create GitHub secrets in Kubernetes
    const githubSecrets = this.createGitHubSecrets(
      props.githubTokenSecretName,
      props.githubWebhookSecretName,
      config.argoEventsNamespace,
      config.githubTokenSecretK8sName,
      config.githubWebhookSecretK8sName
    );
    githubSecrets.node.addDependency(argoEventsNamespace);

    // Deploy EventSource from template
    const eventSource = this.deployEventSource(
      props,
      config,
      props.eventSourceTemplatePath
    );
    eventSource.node.addDependency(eventBus);
    eventSource.node.addDependency(githubSecrets);

    // Deploy Sensor from template
    const sensor = this.deploySensor(
      props,
      config,
      props.sensorTemplatePath
    );
    sensor.node.addDependency(eventSource);
    sensor.node.addDependency(workflowTemplateManifest);

    // Deploy logging configuration from template
    const loggingConfig = this.deployLoggingConfig(
      config,
      this.artifactBucketName,
      this.workflowExecutionRoleArn,
      props.loggingConfigTemplatePath
    );
    loggingConfig.node.addDependency(argoWorkflows);
    loggingConfig.node.addDependency(workflowServiceAccount);

    // Set URLs (LoadBalancer DNS will be available after deployment)
    this.argoWorkflowsUrl = `http://<argo-workflows-server-LoadBalancer>:2746`;
    this.argoEventsWebhookUrl = `http://<${config.eventSourceName}-eventsource-svc-LoadBalancer>:12000/push`;

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

    new cdk.CfnOutput(this, 'GitHubWebhookInstructions', {
      value: `Configure webhook at: https://github.com/${props.githubOwner}/${props.githubRepo}/settings/hooks/new`,
      description: 'GitHub Webhook Configuration URL',
    });
  }

  /**
   * Create GitHub secrets in Kubernetes from AWS Secrets Manager
   */
  private createGitHubSecrets(
    awsTokenSecretName: string,
    awsWebhookSecretName: string | undefined,
    namespace: string,
    k8sTokenSecretName: string,
    k8sWebhookSecretName: string
  ): cdk.aws_eks.KubernetesManifest {
    // Get GitHub token from AWS Secrets Manager
    const githubToken = secretsmanager.Secret.fromSecretNameV2(
      this,
      'GitHubTokenSecret',
      awsTokenSecretName
    );

    // Create Kubernetes secret for GitHub token
    const tokenSecret: any = {
      apiVersion: 'v1',
      kind: 'Secret',
      metadata: {
        name: k8sTokenSecretName,
        namespace: namespace,
      },
      type: 'Opaque',
      stringData: {
        token: githubToken.secretValueFromJson('token').unsafeUnwrap(),
      },
    };

    // If webhook secret is provided, create it too
    let webhookSecret: any = null;
    if (awsWebhookSecretName) {
      const githubWebhookSecret = secretsmanager.Secret.fromSecretNameV2(
        this,
        'GitHubWebhookSecret',
        awsWebhookSecretName
      );

      webhookSecret = {
        apiVersion: 'v1',
        kind: 'Secret',
        metadata: {
          name: k8sWebhookSecretName,
          namespace: namespace,
        },
        type: 'Opaque',
        stringData: {
          secret: githubWebhookSecret.secretValueFromJson('secret').unsafeUnwrap(),
        },
      };
    }

    // Apply secrets to cluster
    const manifests = webhookSecret ? [tokenSecret, webhookSecret] : [tokenSecret];
    return this.cluster.addManifest('GitHubSecrets', ...manifests);
  }

  /**
   * Deploy EventSource from template
   */
  private deployEventSource(
    props: AphexPipelineStackProps,
    config: any,
    customTemplatePath?: string
  ): cdk.aws_eks.KubernetesManifest {
    // Read template
    // When installed as npm package, templates are in dist/.argo/
    // When running from source, templates are in ../../.argo/
    const templatePath = customTemplatePath || 
      path.join(__dirname, '../.argo/eventsource-github.yaml');
    const template = fs.readFileSync(templatePath, 'utf8');

    // Substitute variables
    const processedYaml = template
      .replace(/\$\{EVENT_SOURCE_NAME\}/g, config.eventSourceName)
      .replace(/\$\{ARGO_EVENTS_NAMESPACE\}/g, config.argoEventsNamespace)
      .replace(/\$\{GITHUB_OWNER\}/g, props.githubOwner)
      .replace(/\$\{GITHUB_REPO\}/g, props.githubRepo)
      .replace(/\$\{GITHUB_TOKEN_SECRET_NAME\}/g, config.githubTokenSecretK8sName)
      .replace(/\$\{GITHUB_WEBHOOK_SECRET_NAME\}/g, config.githubWebhookSecretK8sName);

    // Parse and apply
    const manifest = jsyaml.load(processedYaml) as Record<string, any>;
    return this.cluster.addManifest('GitHubEventSource', manifest);
  }

  /**
   * Deploy Sensor from template
   */
  private deploySensor(
    props: AphexPipelineStackProps,
    config: any,
    customTemplatePath?: string
  ): cdk.aws_eks.KubernetesManifest {
    // Read template
    // When installed as npm package, templates are in dist/.argo/
    // When running from source, templates are in ../../.argo/
    const templatePath = customTemplatePath || 
      path.join(__dirname, '../.argo/sensor-aphex-pipeline.yaml');
    const template = fs.readFileSync(templatePath, 'utf8');

    // Substitute variables
    const githubBranchRef = `refs/heads/${config.githubBranch}`;
    const processedYaml = template
      .replace(/\$\{SENSOR_NAME\}/g, config.sensorName)
      .replace(/\$\{ARGO_EVENTS_NAMESPACE\}/g, config.argoEventsNamespace)
      .replace(/\$\{EVENT_SOURCE_NAME\}/g, config.eventSourceName)
      .replace(/\$\{GITHUB_BRANCH_REF\}/g, githubBranchRef)
      .replace(/\$\{WORKFLOW_TEMPLATE_NAME\}/g, config.workflowTemplateName)
      .replace(/\$\{WORKFLOW_NAME_PREFIX\}/g, config.workflowNamePrefix)
      .replace(/\$\{ARGO_NAMESPACE\}/g, config.argoNamespace);

    // Parse and apply
    const manifest = jsyaml.load(processedYaml) as Record<string, any>;
    return this.cluster.addManifest('AphexPipelineSensor', manifest);
  }

  /**
   * Deploy logging configuration from template
   */
  private deployLoggingConfig(
    config: any,
    artifactBucket: string,
    roleArn: string,
    customTemplatePath?: string
  ): cdk.aws_eks.KubernetesManifest {
    // Read template
    // When installed as npm package, templates are in dist/.argo/
    // When running from source, templates are in ../../.argo/
    const templatePath = customTemplatePath || 
      path.join(__dirname, '../.argo/logging-config.yaml');
    const template = fs.readFileSync(templatePath, 'utf8');

    // Substitute variables
    const processedYaml = template
      .replace(/\$\{ARGO_NAMESPACE\}/g, config.argoNamespace)
      .replace(/\$\{ARTIFACT_BUCKET\}/g, artifactBucket)
      .replace(/\$\{WORKFLOW_EXECUTION_ROLE_ARN\}/g, roleArn)
      .replace(/\$\{SERVICE_ACCOUNT_NAME\}/g, config.serviceAccountName);

    // Parse all documents (logging-config.yaml has multiple YAML documents)
    const manifests = jsyaml.loadAll(processedYaml) as Record<string, any>[];

    // Apply all manifests
    return this.cluster.addManifest('LoggingConfig', ...manifests);
  }
}
