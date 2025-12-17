import * as cdk from 'aws-cdk-lib';
import * as eks from 'aws-cdk-lib/aws-eks';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';
import { Construct } from 'constructs';
import * as path from 'path';
import * as fs from 'fs';
import * as crypto from 'crypto';
import * as jsyaml from 'js-yaml';
import { KubectlV30Layer } from '@aws-cdk/lambda-layer-kubectl-v30';
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
   * AWS Secrets Manager secret name for GitHub webhook validation (legacy mode)
   * 
   * **Recommended: Leave undefined** to use per-pipeline webhook secrets (default behavior).
   * Each pipeline will generate a unique secret for better security isolation.
   * 
   * If provided, the construct will use the secret from AWS Secrets Manager instead.
   * This is useful for backward compatibility with existing deployments.
   * 
   * @default undefined - generates unique secret per pipeline
   * @example 'github-webhook-secret' (legacy shared secret)
   */
  githubWebhookSecretName?: string;
  
  // ===== EKS Cluster Reference =====
  
  /**
   * Name of the existing AphexCluster to reference
   * Used to discover cluster via CloudFormation exports
   * The cluster must have been deployed via arbiter-pipeline-infrastructure
   * @example 'company-pipelines'
   */
  clusterName: string;
  
  /**
   * CloudFormation export prefix for cluster resources
   * Allows the construct to work with different cluster export naming conventions
   * @default 'AphexCluster-{clusterName}-'
   * @example 'ArbiterCluster-' or 'MyCluster-prod-'
   */
  clusterExportPrefix?: string;
  
  /**
   * ARN of a role that has permission to assume the kubectl role
   * If provided, the kubectl provider will use this role for Kubernetes operations
   * This is useful when the kubectl role has restricted trust policies
   * @example 'arn:aws:iam::123456789012:role/pipeline-creator'
   */
  pipelineCreatorRoleArn?: string;
  
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
   * AWS account ID where container images are stored in ECR
   * Used to construct ECR image URIs: {account}.dkr.ecr.{region}.amazonaws.com/{repository}:{tag}
   * @default Stack account (this.account)
   */
  containerImageAccount?: string;
  
  /**
   * AWS region where container images are stored in ECR
   * Used to construct ECR image URIs: {account}.dkr.ecr.{region}.amazonaws.com/{repository}:{tag}
   * @default 'us-east-1'
   */
  containerImageRegion?: string;
  
  /**
   * Container image version tag
   * @default 'v1.0.1'
   */
  containerImageVersion?: string;
  
  /**
   * Builder container image
   * If not provided, constructs from convention: {account}.dkr.ecr.{region}.amazonaws.com/arbiter-pipeline-builder:{version}
   * @default Convention-based ECR URI
   */
  builderImage?: string;
  
  /**
   * Deployer container image
   * If not provided, constructs from convention: {account}.dkr.ecr.{region}.amazonaws.com/arbiter-pipeline-deployer:{version}
   * @default Convention-based ECR URI
   */
  deployerImage?: string;
  
  // ===== Advanced =====
  
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
  
  /**
   * Configuration for the EventSource webhook service
   * 
   * @default { 
   *   type: 'LoadBalancer',
   *   enabled: true,
   *   port: 12000,
   *   annotations: { 'service.beta.kubernetes.io/aws-load-balancer-type': 'nlb' }
   * }
   */
  readonly webhookService?: {
    /**
     * Whether to create a service for the webhook
     * Set to false if using Ingress or other external access method
     * 
     * @default true
     */
    enabled?: boolean;
    
    /**
     * Kubernetes service type
     * 
     * - LoadBalancer: Creates external IP (AWS ELB/NLB), best for production
     * - NodePort: Exposes on node IP:port, good for on-prem or custom ingress
     * - ClusterIP: Internal only, use with Ingress controller
     * 
     * @default 'LoadBalancer'
     */
    type?: 'LoadBalancer' | 'NodePort' | 'ClusterIP';
    
    /**
     * Service annotations for cloud provider configuration
     * 
     * Common AWS annotations:
     * - 'service.beta.kubernetes.io/aws-load-balancer-type': 'nlb' | 'external'
     * - 'service.beta.kubernetes.io/aws-load-balancer-scheme': 'internet-facing' | 'internal'
     * - 'service.beta.kubernetes.io/aws-load-balancer-ssl-cert': '<cert-arn>'
     * - 'service.beta.kubernetes.io/load-balancer-source-ranges': '<cidr>' (IP whitelisting)
     * 
     * @default { 'service.beta.kubernetes.io/aws-load-balancer-type': 'nlb' }
     */
    annotations?: Record<string, string>;
    
    /**
     * Service port (must match webhook port)
     * @default 12000
     */
    port?: number;
    
    /**
     * NodePort value (only used if type is NodePort)
     * If not specified, Kubernetes assigns automatically
     * 
     * @default undefined
     */
    nodePort?: number;
    
    /**
     * Additional service labels
     * @default {}
     */
    labels?: Record<string, string>;
  };
}

export class AphexPipelineStack extends cdk.Stack {
  public readonly cluster: eks.ICluster;
  public readonly clusterName: string;
  public readonly argoWorkflowsUrl: string;
  public readonly argoEventsWebhookUrl: string;
  public readonly artifactBucketName: string;
  public readonly workflowExecutionRoleArn: string;
  public readonly workflowTemplateName: string;
  public webhookSecretValue: string;
  public readonly webhookServiceType: string;

  constructor(scope: Construct, id: string, props: AphexPipelineStackProps) {
    super(scope, id, props);

    // Validate required props
    if (!props.clusterName) {
      throw new Error('clusterName is required - must reference an existing AphexCluster');
    }
    if (!props.githubOwner || !props.githubRepo || !props.githubTokenSecretName) {
      throw new Error('githubOwner, githubRepo, and githubTokenSecretName are required');
    }

    // Set defaults
    const containerImageAccount = props.containerImageAccount || this.account;
    const containerImageRegion = props.containerImageRegion || 'us-east-1';
    const containerImageVersion = props.containerImageVersion || 'v1.0.1';
    
    // Construct convention-based ECR image URIs
    const ecrBase = `${containerImageAccount}.dkr.ecr.${containerImageRegion}.amazonaws.com`;
    const defaultBuilderImage = `${ecrBase}/arbiter-pipeline-builder:${containerImageVersion}`;
    const defaultDeployerImage = `${ecrBase}/arbiter-pipeline-deployer:${containerImageVersion}`;
    
    const config = {
      githubBranch: props.githubBranch || 'main',
      argoNamespace: props.argoNamespace || 'argo',
      argoEventsNamespace: props.argoEventsNamespace || 'argo-events',
      serviceAccountName: props.serviceAccountName || 'workflow-executor',
      eventSourceName: props.eventSourceName || 'github',
      sensorName: props.sensorName || 'aphex-pipeline-sensor',
      workflowTemplateName: props.workflowTemplateName || 'aphex-pipeline-template',
      workflowNamePrefix: props.workflowNamePrefix || 'aphex-pipeline-',
      artifactRetentionDays: props.artifactRetentionDays || 90,
      githubTokenSecretK8sName: 'github-access',
      githubWebhookSecretK8sName: `${props.eventSourceName || 'github'}-webhook-secret`,
      builderImage: props.builderImage || defaultBuilderImage,
      deployerImage: props.deployerImage || defaultDeployerImage,
    };

    // Parse aphex-config.yaml
    const configPath = props.configPath || path.join(__dirname, '../../aphex-config.yaml');
    const aphexConfig = ConfigParser.parse(configPath);

    // Import existing cluster using CloudFormation exports
    // Use custom export prefix if provided, otherwise default to AphexCluster-{clusterName}-
    const exportPrefix = props.clusterExportPrefix ?? `AphexCluster-${props.clusterName}-`;
    
    const clusterNameExport = `${exportPrefix}ClusterName`;
    const oidcProviderArnExport = `${exportPrefix}OIDCProviderArn`;
    const kubectlRoleArnExport = `${exportPrefix}KubectlRoleArn`;
    
    const importedClusterName = cdk.Fn.importValue(clusterNameExport);
    const openIdConnectProviderArn = cdk.Fn.importValue(oidcProviderArnExport);
    
    // Determine which role to use for kubectl operations
    // If pipelineCreatorRoleArn is provided, use it directly as the kubectl role
    // Otherwise, import the kubectl role from CloudFormation exports (backward compatible)
    let kubectlRoleArn: string;
    if (props.pipelineCreatorRoleArn) {
      // Validate ARN format
      const arnPattern = /^arn:aws:iam::\d{12}:role\/.+$/;
      if (!arnPattern.test(props.pipelineCreatorRoleArn)) {
        throw new Error(
          `pipelineCreatorRoleArn must be a valid IAM role ARN in the format ` +
          `arn:aws:iam::ACCOUNT_ID:role/ROLE_NAME, got: ${props.pipelineCreatorRoleArn}`
        );
      }
      kubectlRoleArn = props.pipelineCreatorRoleArn;
    } else {
      kubectlRoleArn = cdk.Fn.importValue(kubectlRoleArnExport);
    }
    
    // Import the cluster using the determined kubectl role
    this.cluster = eks.Cluster.fromClusterAttributes(this, 'ImportedCluster', {
      clusterName: importedClusterName,
      kubectlRoleArn: kubectlRoleArn,
      openIdConnectProvider: eks.OpenIdConnectProvider.fromOpenIdConnectProviderArn(
        this,
        'ClusterOIDCProvider',
        openIdConnectProviderArn
      ),
      // Add kubectl layer to enable Kubernetes manifest operations
      kubectlLayer: new KubectlV30Layer(this, 'KubectlLayer'),
    });

    // Store cluster name
    this.clusterName = importedClusterName;

    // Note: Argo Workflows and Argo Events are assumed to be pre-installed by aphex-cluster package
    // We verify their presence but do not install them

    // Create pipeline-specific service account for workflow execution with IRSA
    // The namespace (argo) is assumed to exist from the cluster setup
    const workflowServiceAccount = this.cluster.addServiceAccount('WorkflowExecutionServiceAccount', {
      name: config.serviceAccountName,
      namespace: config.argoNamespace,
    });

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

    // Create RBAC resources for workflow-executor ServiceAccount
    // This allows workflows to create WorkflowTaskResults for passing outputs between steps
    const workflowExecutorRBAC = this.createWorkflowExecutorRBAC(props, config);
    workflowExecutorRBAC.node.addDependency(workflowServiceAccount);

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
      config.serviceAccountName,
      config.builderImage,
      config.deployerImage,
      this.workflowExecutionRoleArn,
      config.workflowTemplateName,
      config.argoNamespace
    );
    const workflowTemplate = workflowGenerator.generate();

    // Apply WorkflowTemplate to the cluster
    // Note: Argo Workflows is assumed to be pre-installed, so no dependency needed
    const workflowTemplateManifest = this.cluster.addManifest('AphexPipelineWorkflowTemplate', workflowTemplate);
    workflowTemplateManifest.node.addDependency(workflowServiceAccount);

    // Create GitHub secrets in Kubernetes
    // Note: argo-events namespace is assumed to exist from cluster setup
    const githubSecrets = this.createGitHubSecrets(
      props.githubTokenSecretName,
      props.githubWebhookSecretName,
      config.argoEventsNamespace,
      config.githubTokenSecretK8sName,
      config.githubWebhookSecretK8sName
    );

    // Deploy EventSource from template
    // Note: EventBus is assumed to exist from cluster setup
    const eventSource = this.deployEventSource(
      props,
      config,
      props.eventSourceTemplatePath
    );
    eventSource.node.addDependency(githubSecrets);
    
    // Create Kubernetes Service for EventSource webhook
    const webhookService = this.createEventSourceService(props, config);
    if (webhookService) {
      webhookService.node.addDependency(eventSource);
    }

    // Create RBAC resources for Sensor
    const sensorRBAC = this.createSensorRBAC(props, config);
    
    // Deploy Sensor from template
    const sensor = this.deploySensor(
      props,
      config,
      props.sensorTemplatePath
    );
    sensor.node.addDependency(eventSource);
    sensor.node.addDependency(workflowTemplateManifest);
    sensor.node.addDependency(sensorRBAC);

    // Deploy logging configuration from template
    const loggingConfig = this.deployLoggingConfig(
      config,
      this.artifactBucketName,
      this.workflowExecutionRoleArn,
      props.loggingConfigTemplatePath
    );
    loggingConfig.node.addDependency(workflowServiceAccount);

    // Set URLs (LoadBalancer DNS will be available after deployment)
    this.argoWorkflowsUrl = `http://<argo-workflows-server-LoadBalancer>:2746`;
    
    // Determine webhook URL based on service configuration
    const serviceConfig = {
      enabled: true,
      type: 'LoadBalancer' as const,
      port: 12000,
      annotations: {
        'service.beta.kubernetes.io/aws-load-balancer-type': 'nlb',
      },
      ...props.webhookService,
    };
    
    this.webhookServiceType = serviceConfig.enabled ? serviceConfig.type : 'disabled';
    
    if (serviceConfig.enabled) {
      const serviceName = `${config.eventSourceName}-eventsource-svc`;
      if (serviceConfig.type === 'LoadBalancer') {
        this.argoEventsWebhookUrl = `http://<${serviceName}-LoadBalancer-DNS>:${serviceConfig.port}/push`;
      } else if (serviceConfig.type === 'NodePort') {
        const nodePortValue = serviceConfig.nodePort || '<assigned-port>';
        this.argoEventsWebhookUrl = `http://<node-ip>:${nodePortValue}/push`;
      } else {
        // ClusterIP
        this.argoEventsWebhookUrl = `http://${serviceName}.${config.argoEventsNamespace}.svc.cluster.local:${serviceConfig.port}/push`;
      }
    } else {
      this.argoEventsWebhookUrl = 'Service disabled - configure external access manually';
    }
    
    this.workflowTemplateName = config.workflowTemplateName;

    // Stack outputs - pipeline-specific only
    new cdk.CfnOutput(this, 'ArgoEventsWebhookUrl', {
      value: this.argoEventsWebhookUrl || 'To be configured after EventSource deployment',
      description: 'Argo Events Webhook URL for GitHub integration',
      exportName: 'AphexPipelineWebhookUrl',
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

    new cdk.CfnOutput(this, 'WorkflowTemplateName', {
      value: this.workflowTemplateName,
      description: 'Argo WorkflowTemplate name',
      exportName: 'AphexPipelineWorkflowTemplateName',
    });

    new cdk.CfnOutput(this, 'WebhookSecretValue', {
      value: this.webhookSecretValue,
      description: 'GitHub webhook secret - configure this in your repository webhook settings',
    });
    
    new cdk.CfnOutput(this, 'WebhookSecretName', {
      value: config.githubWebhookSecretK8sName,
      description: 'Kubernetes secret name containing the webhook secret',
    });
    
    new cdk.CfnOutput(this, 'SensorServiceAccountName', {
      value: `${config.sensorName}-sa`,
      description: 'ServiceAccount used by the Sensor to create workflows',
    });

    new cdk.CfnOutput(this, 'GitHubWebhookInstructions', {
      value: `Configure webhook at: https://github.com/${props.githubOwner}/${props.githubRepo}/settings/hooks/new with secret from WebhookSecretValue output`,
      description: 'GitHub Webhook Configuration Instructions',
    });
    
    new cdk.CfnOutput(this, 'WebhookServiceType', {
      value: this.webhookServiceType,
      description: 'Type of Kubernetes service created for webhook (LoadBalancer, NodePort, ClusterIP, or disabled)',
    });
    
    if (serviceConfig.enabled && serviceConfig.type === 'LoadBalancer') {
      new cdk.CfnOutput(this, 'WebhookServiceName', {
        value: `${config.eventSourceName}-eventsource-svc`,
        description: 'Kubernetes service name - use "kubectl get svc -n argo-events <name>" to get LoadBalancer DNS',
      });
    }
  }

  /**
   * Create GitHub secrets in Kubernetes
   * 
   * Creates two secrets:
   * 1. GitHub token (from AWS Secrets Manager)
   * 2. Webhook secret (generated per-pipeline for security isolation)
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

    // Generate or import webhook secret
    let webhookSecret: any;
    let webhookSecretValue: string;
    
    if (awsWebhookSecretName) {
      // Legacy mode: Use provided AWS Secrets Manager secret
      const githubWebhookSecret = secretsmanager.Secret.fromSecretNameV2(
        this,
        'GitHubWebhookSecret',
        awsWebhookSecretName
      );
      
      webhookSecretValue = githubWebhookSecret.secretValueFromJson('secret').unsafeUnwrap();
    } else {
      // Per-pipeline mode: Generate unique secret for this pipeline
      webhookSecretValue = crypto.randomBytes(32).toString('hex');
    }
    
    // Store the webhook secret value for stack outputs
    this.webhookSecretValue = webhookSecretValue;
    
    // Create Kubernetes secret for webhook
    webhookSecret = {
      apiVersion: 'v1',
      kind: 'Secret',
      metadata: {
        name: k8sWebhookSecretName,
        namespace: namespace,
        labels: {
          'app.kubernetes.io/managed-by': 'aphex-pipeline',
          'app.kubernetes.io/instance': this.stackName,
        },
      },
      type: 'Opaque',
      stringData: {
        secret: webhookSecretValue,
      },
    };

    // Apply secrets to cluster
    return this.cluster.addManifest('GitHubSecrets', tokenSecret, webhookSecret);
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
    // Try multiple paths to support both development and packaged scenarios
    let templatePath = customTemplatePath;
    if (!templatePath) {
      // When installed as npm package: dist/lib/*.js -> dist/.argo/
      const packagedPath = path.join(__dirname, '../.argo/eventsource-github.yaml');
      // When running from source: lib/*.ts -> ../.argo/
      const sourcePath = path.join(__dirname, '../../.argo/eventsource-github.yaml');
      
      templatePath = fs.existsSync(packagedPath) ? packagedPath : sourcePath;
    }
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
   * Create RBAC resources for Sensor (ServiceAccount, Role, RoleBinding)
   */
  private createSensorRBAC(
    props: AphexPipelineStackProps,
    config: any
  ): cdk.aws_eks.KubernetesManifest {
    const sensorServiceAccountName = `${config.sensorName}-sa`;
    const sensorRoleName = `${config.sensorName}-role`;
    const sensorRoleBindingName = `${config.sensorName}-rolebinding`;
    
    // Create ServiceAccount, Role, and RoleBinding in a single manifest
    const rbacManifests = [
      // ServiceAccount
      {
        apiVersion: 'v1',
        kind: 'ServiceAccount',
        metadata: {
          name: sensorServiceAccountName,
          namespace: config.argoNamespace,
          labels: {
            'app.kubernetes.io/name': config.sensorName,
            'app.kubernetes.io/component': 'sensor',
            'app.kubernetes.io/managed-by': 'aphex-pipeline',
            'app.kubernetes.io/instance': config.workflowTemplateName,
          },
        },
      },
      // Role
      {
        apiVersion: 'rbac.authorization.k8s.io/v1',
        kind: 'Role',
        metadata: {
          name: sensorRoleName,
          namespace: config.argoNamespace,
          labels: {
            'app.kubernetes.io/name': config.sensorName,
            'app.kubernetes.io/component': 'sensor',
            'app.kubernetes.io/managed-by': 'aphex-pipeline',
          },
        },
        rules: [
          {
            apiGroups: ['argoproj.io'],
            resources: ['workflows', 'workflowtemplates'],
            verbs: ['create', 'get', 'list', 'watch'],
          },
          {
            apiGroups: [''],
            resources: ['pods', 'pods/log'],
            verbs: ['get', 'list', 'watch'],
          },
        ],
      },
      // RoleBinding
      {
        apiVersion: 'rbac.authorization.k8s.io/v1',
        kind: 'RoleBinding',
        metadata: {
          name: sensorRoleBindingName,
          namespace: config.argoNamespace,
          labels: {
            'app.kubernetes.io/name': config.sensorName,
            'app.kubernetes.io/component': 'sensor',
            'app.kubernetes.io/managed-by': 'aphex-pipeline',
          },
        },
        roleRef: {
          apiGroup: 'rbac.authorization.k8s.io',
          kind: 'Role',
          name: sensorRoleName,
        },
        subjects: [{
          kind: 'ServiceAccount',
          name: sensorServiceAccountName,
          namespace: config.argoNamespace,
        }],
      },
    ];
    
    return this.cluster.addManifest('SensorRBAC', ...rbacManifests);
  }

  /**
   * Create RBAC resources for workflow-executor ServiceAccount
   * Grants permissions to create WorkflowTaskResults for passing outputs between workflow steps
   */
  private createWorkflowExecutorRBAC(
    props: AphexPipelineStackProps,
    config: any
  ): cdk.aws_eks.KubernetesManifest {
    const roleName = `${config.serviceAccountName}-role`;
    const roleBindingName = `${config.serviceAccountName}-rolebinding`;
    
    // Create Role and RoleBinding for workflow-executor
    const rbacManifests = [
      // Role
      {
        apiVersion: 'rbac.authorization.k8s.io/v1',
        kind: 'Role',
        metadata: {
          name: roleName,
          namespace: config.argoNamespace,
          labels: {
            'app.kubernetes.io/name': config.serviceAccountName,
            'app.kubernetes.io/component': 'workflow-executor',
            'app.kubernetes.io/managed-by': 'aphex-pipeline',
            'app.kubernetes.io/instance': config.workflowTemplateName,
          },
        },
        rules: [
          {
            apiGroups: ['argoproj.io'],
            resources: ['workflowtaskresults'],
            verbs: ['create', 'get', 'list', 'watch', 'update', 'patch', 'delete'],
          },
        ],
      },
      // RoleBinding
      {
        apiVersion: 'rbac.authorization.k8s.io/v1',
        kind: 'RoleBinding',
        metadata: {
          name: roleBindingName,
          namespace: config.argoNamespace,
          labels: {
            'app.kubernetes.io/name': config.serviceAccountName,
            'app.kubernetes.io/component': 'workflow-executor',
            'app.kubernetes.io/managed-by': 'aphex-pipeline',
            'app.kubernetes.io/instance': config.workflowTemplateName,
          },
        },
        roleRef: {
          apiGroup: 'rbac.authorization.k8s.io',
          kind: 'Role',
          name: roleName,
        },
        subjects: [{
          kind: 'ServiceAccount',
          name: config.serviceAccountName,
          namespace: config.argoNamespace,
        }],
      },
    ];
    
    return this.cluster.addManifest('WorkflowExecutorRBAC', ...rbacManifests);
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
    // Try multiple paths to support both development and packaged scenarios
    let templatePath = customTemplatePath;
    if (!templatePath) {
      // When installed as npm package: dist/lib/*.js -> dist/.argo/
      const packagedPath = path.join(__dirname, '../.argo/sensor-aphex-pipeline.yaml');
      // When running from source: lib/*.ts -> ../.argo/
      const sourcePath = path.join(__dirname, '../../.argo/sensor-aphex-pipeline.yaml');
      
      templatePath = fs.existsSync(packagedPath) ? packagedPath : sourcePath;
    }
    const template = fs.readFileSync(templatePath, 'utf8');

    // Substitute variables
    const githubBranchRef = `refs/heads/${config.githubBranch}`;
    const sensorServiceAccountName = `${config.sensorName}-sa`;
    const processedYaml = template
      .replace(/\$\{SENSOR_NAME\}/g, config.sensorName)
      .replace(/\$\{ARGO_EVENTS_NAMESPACE\}/g, config.argoEventsNamespace)
      .replace(/\$\{EVENT_SOURCE_NAME\}/g, config.eventSourceName)
      .replace(/\$\{GITHUB_BRANCH_REF\}/g, githubBranchRef)
      .replace(/\$\{SENSOR_SERVICE_ACCOUNT_NAME\}/g, sensorServiceAccountName)
      .replace(/\$\{WORKFLOW_TEMPLATE_NAME\}/g, config.workflowTemplateName)
      .replace(/\$\{WORKFLOW_NAME_PREFIX\}/g, config.workflowNamePrefix)
      .replace(/\$\{ARGO_NAMESPACE\}/g, config.argoNamespace);

    // Parse and apply
    const manifest = jsyaml.load(processedYaml) as Record<string, any>;
    return this.cluster.addManifest('AphexPipelineSensor', manifest);
  }

  /**
   * Create Kubernetes Service for EventSource webhook
   */
  private createEventSourceService(
    props: AphexPipelineStackProps,
    config: any
  ): cdk.aws_eks.KubernetesManifest | null {
    // Default configuration
    const serviceConfig = {
      enabled: true,
      type: 'LoadBalancer' as const,
      port: 12000,
      annotations: {
        'service.beta.kubernetes.io/aws-load-balancer-type': 'nlb',
      },
      labels: {},
      ...props.webhookService,
    };
    
    if (!serviceConfig.enabled) {
      return null; // User disabled service creation
    }
    
    const serviceName = `${config.eventSourceName}-eventsource-svc`;
    
    // Build service manifest
    const serviceManifest: any = {
      apiVersion: 'v1',
      kind: 'Service',
      metadata: {
        name: serviceName,
        namespace: config.argoEventsNamespace,
        labels: {
          'app.kubernetes.io/name': config.eventSourceName,
          'app.kubernetes.io/component': 'eventsource-webhook',
          'app.kubernetes.io/managed-by': 'aphex-pipeline',
          'app.kubernetes.io/instance': this.stackName,
          ...serviceConfig.labels,
        },
        annotations: serviceConfig.annotations,
      },
      spec: {
        type: serviceConfig.type,
        ports: [{
          name: 'webhook',
          port: serviceConfig.port,
          targetPort: 12000, // EventSource always listens on 12000
          protocol: 'TCP',
        }],
        selector: {
          'eventsource-name': config.eventSourceName,
        },
      },
    };
    
    // Add nodePort if specified and type is NodePort
    if (serviceConfig.type === 'NodePort' && serviceConfig.nodePort) {
      serviceManifest.spec.ports[0].nodePort = serviceConfig.nodePort;
    }
    
    return this.cluster.addManifest('EventSourceWebhookService', serviceManifest);
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
    // Try multiple paths to support both development and packaged scenarios
    let templatePath = customTemplatePath;
    if (!templatePath) {
      // When installed as npm package: dist/lib/*.js -> dist/.argo/
      const packagedPath = path.join(__dirname, '../.argo/logging-config.yaml');
      // When running from source: lib/*.ts -> ../.argo/
      const sourcePath = path.join(__dirname, '../../.argo/logging-config.yaml');
      
      templatePath = fs.existsSync(packagedPath) ? packagedPath : sourcePath;
    }
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
