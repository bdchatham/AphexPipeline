# API Reference

## AphexPipeline Construct

The main CDK construct for creating deployment pipelines.

**Source**
- `pipeline-infra/lib/aphex-pipeline-stack.ts`

### Interface

```typescript
export interface AphexPipelineProps extends cdk.StackProps {
  // ===== Required Parameters =====
  
  /**
   * Name of existing AphexCluster to reference
   * Used to discover cluster via CloudFormation exports
   */
  clusterName: string;
  
  /**
   * GitHub repository owner (organization or user)
   */
  githubOwner: string;
  
  /**
   * GitHub repository name
   */
  githubRepo: string;
  
  /**
   * AWS Secrets Manager secret name containing GitHub token
   */
  githubTokenSecretName: string;
  
  // ===== Stack Configuration =====
  
  /**
   * CDK stacks to deploy
   */
  stacks: StackDefinition[];
  
  /**
   * Deployment environments
   */
  environments: EnvironmentDefinition[];
  
  // ===== Optional Configuration =====
  
  /**
   * GitHub branch to trigger on
   * @default 'main'
   */
  githubBranch?: string;
  
  /**
   * Build commands to execute
   * @default []
   */
  buildCommands?: string[];
  
  // ===== Container Image Overrides =====
  
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
  
  /**
   * Tester container image
   * @default 'public.ecr.aws/aphex/tester:latest'
   */
  testerImage?: string;
  
  /**
   * Validator container image
   * @default 'public.ecr.aws/aphex/validator:latest'
   */
  validatorImage?: string;
  
  // ===== Resource Naming =====
  
  /**
   * WorkflowTemplate name
   * @default 'aphex-pipeline-template'
   */
  workflowTemplateName?: string;
  
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
   * ServiceAccount name
   * @default 'workflow-executor'
   */
  serviceAccountName?: string;
  
  /**
   * Workflow name prefix
   * @default 'aphex-pipeline-'
   */
  workflowNamePrefix?: string;
  
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
   * Argo Workflows namespace
   * @default 'argo'
   */
  argoNamespace?: string;
  
  /**
   * Argo Events namespace
   * @default 'argo-events'
   */
  argoEventsNamespace?: string;
}
```

### Stack Definition

```typescript
export interface StackDefinition {
  /**
   * CDK stack name
   */
  name: string;
  
  /**
   * Path to stack file relative to repository root
   */
  path: string;
  
  /**
   * Stack dependencies (must be deployed first)
   * @default []
   */
  dependsOn?: string[];
}
```

### Environment Definition

```typescript
export interface EnvironmentDefinition {
  /**
   * Environment name (e.g., 'dev', 'staging', 'prod')
   */
  name: string;
  
  /**
   * AWS account ID
   */
  account: string;
  
  /**
   * AWS region
   */
  region: string;
  
  /**
   * Stacks to deploy in this environment
   */
  stacks: string[];
  
  /**
   * Optional post-deployment tests
   */
  tests?: TestDefinition;
  
  /**
   * Require manual approval before deployment
   * @default false
   */
  requiresApproval?: boolean;
}
```

### Test Definition

```typescript
export interface TestDefinition {
  /**
   * Test commands to execute
   */
  commands: string[];
}
```

## Usage Examples

### Minimal Configuration

```typescript
import { AphexPipeline } from 'aphex-pipeline';

new AphexPipeline(this, 'Pipeline', {
  clusterName: 'company-pipelines',
  githubOwner: 'my-org',
  githubRepo: 'my-app',
  githubTokenSecretName: 'github-token',
  stacks: [
    { name: 'AppStack', path: 'lib/app-stack.ts' },
  ],
  environments: [
    { name: 'dev', account: '111', region: 'us-east-1', stacks: ['AppStack'] },
  ],
});
```

**Source**
- `pipeline-infra/examples/single-pipeline-example.ts`

### With Build Commands

```typescript
new AphexPipeline(this, 'Pipeline', {
  clusterName: 'company-pipelines',
  githubOwner: 'my-org',
  githubRepo: 'my-app',
  githubTokenSecretName: 'github-token',
  
  buildCommands: [
    'npm install',
    'npm run build',
    'npm test',
  ],
  
  stacks: [
    { name: 'AppStack', path: 'lib/app-stack.ts' },
  ],
  
  environments: [
    { name: 'dev', account: '111', region: 'us-east-1', stacks: ['AppStack'] },
  ],
});
```

### With Stack Dependencies

```typescript
new AphexPipeline(this, 'Pipeline', {
  clusterName: 'company-pipelines',
  githubOwner: 'my-org',
  githubRepo: 'my-app',
  githubTokenSecretName: 'github-token',
  
  stacks: [
    { 
      name: 'DatabaseStack', 
      path: 'lib/database-stack.ts' 
    },
    { 
      name: 'ApiStack', 
      path: 'lib/api-stack.ts',
      dependsOn: ['DatabaseStack']  // Deployed after DatabaseStack
    },
    { 
      name: 'FrontendStack', 
      path: 'lib/frontend-stack.ts',
      dependsOn: ['ApiStack']  // Deployed after ApiStack
    },
  ],
  
  environments: [
    { 
      name: 'dev', 
      account: '111', 
      region: 'us-east-1',
      stacks: ['DatabaseStack', 'ApiStack', 'FrontendStack']
    },
  ],
});
```

### With Multiple Environments

```typescript
new AphexPipeline(this, 'Pipeline', {
  clusterName: 'company-pipelines',
  githubOwner: 'my-org',
  githubRepo: 'my-app',
  githubTokenSecretName: 'github-token',
  
  stacks: [
    { name: 'AppStack', path: 'lib/app-stack.ts' },
  ],
  
  environments: [
    {
      name: 'dev',
      account: '111111111111',
      region: 'us-east-1',
      stacks: ['AppStack'],
    },
    {
      name: 'staging',
      account: '222222222222',
      region: 'us-east-1',
      stacks: ['AppStack'],
      tests: {
        commands: ['npm run integration-test'],
      },
    },
    {
      name: 'prod',
      account: '333333333333',
      region: 'us-west-2',
      stacks: ['AppStack'],
      requiresApproval: true,
    },
  ],
});
```

### With Custom Container Images

```typescript
new AphexPipeline(this, 'Pipeline', {
  clusterName: 'company-pipelines',
  githubOwner: 'my-org',
  githubRepo: 'my-app',
  githubTokenSecretName: 'github-token',
  
  // Override default images
  builderImage: 'my-registry/custom-builder:v1.0.0',
  deployerImage: 'my-registry/custom-deployer:v1.0.0',
  
  stacks: [
    { name: 'AppStack', path: 'lib/app-stack.ts' },
  ],
  
  environments: [
    { name: 'dev', account: '111', region: 'us-east-1', stacks: ['AppStack'] },
  ],
});
```

### Multi-Pipeline Scenario

```typescript
// Frontend pipeline
new AphexPipeline(this, 'FrontendPipeline', {
  clusterName: 'company-pipelines',
  githubOwner: 'my-org',
  githubRepo: 'frontend',
  githubTokenSecretName: 'github-token',
  
  // Unique naming to avoid conflicts
  workflowTemplateName: 'frontend-pipeline-template',
  eventSourceName: 'frontend-github',
  sensorName: 'frontend-pipeline-sensor',
  serviceAccountName: 'frontend-workflow-executor',
  
  stacks: [
    { name: 'FrontendStack', path: 'lib/frontend-stack.ts' },
  ],
  
  environments: [
    { name: 'dev', account: '111', region: 'us-east-1', stacks: ['FrontendStack'] },
  ],
});

// Backend pipeline
new AphexPipeline(this, 'BackendPipeline', {
  clusterName: 'company-pipelines',
  githubOwner: 'my-org',
  githubRepo: 'backend',
  githubTokenSecretName: 'github-token',
  
  // Unique naming to avoid conflicts
  workflowTemplateName: 'backend-pipeline-template',
  eventSourceName: 'backend-github',
  sensorName: 'backend-pipeline-sensor',
  serviceAccountName: 'backend-workflow-executor',
  
  stacks: [
    { name: 'BackendStack', path: 'lib/backend-stack.ts' },
  ],
  
  environments: [
    { name: 'dev', account: '111', region: 'us-east-1', stacks: ['BackendStack'] },
  ],
});
```

**Source**
- `pipeline-infra/examples/multi-pipeline-example.ts`

## Outputs

The construct creates CloudFormation outputs:

### ArgoEventsWebhookUrl
URL for GitHub webhook configuration.

### ArtifactBucketName
S3 bucket name for build artifacts.

### WorkflowExecutionRoleArn
IAM role ARN for workflow execution (IRSA).

### WorkflowTemplateName
Name of the Argo WorkflowTemplate.

### GitHubWebhookInstructions
URL to configure GitHub webhook.

## Default Values

### Container Images
- Builder: `public.ecr.aws/aphex/builder:latest`
- Deployer: `public.ecr.aws/aphex/deployer:latest`
- Tester: `public.ecr.aws/aphex/tester:latest`
- Validator: `public.ecr.aws/aphex/validator:latest`

### Resource Names
- WorkflowTemplate: `aphex-pipeline-template`
- EventSource: `github`
- Sensor: `aphex-pipeline-sensor`
- ServiceAccount: `workflow-executor`
- Workflow prefix: `aphex-pipeline-`

### Namespaces
- Argo Workflows: `argo`
- Argo Events: `argo-events`

### Artifact Storage
- Bucket name: `aphex-pipeline-artifacts-{account}-{region}`
- Retention: 90 days

## CloudFormation Exports Required

The construct expects these exports from the cluster:

- `AphexCluster-${clusterName}-ClusterName`
- `AphexCluster-${clusterName}-OIDCProviderArn`
- `AphexCluster-${clusterName}-KubectlRoleArn`
- `AphexCluster-${clusterName}-ClusterSecurityGroupId`

These are provided by the `arbiter-pipeline-infrastructure` package.

**Source**
- `cluster_implementation_notes.md` (export naming)

## Error Handling

### Missing Cluster Exports
If CloudFormation exports don't exist, deployment fails with:
```
Export AphexCluster-{clusterName}-ClusterName not found
```

**Resolution**: Ensure cluster is deployed and exports are created.

### Invalid Configuration
If stack or environment configuration is invalid, deployment fails during CDK synthesis.

**Resolution**: Verify stack names, paths, and dependencies are correct.

### GitHub Token Missing
If GitHub token secret doesn't exist, deployment fails.

**Resolution**: Create secret in AWS Secrets Manager:
```bash
aws secretsmanager create-secret \
  --name github-token \
  --secret-string '{"token":"ghp_..."}'
```

## Related Documentation

- [Overview](overview.md) - Getting started
- [Architecture](architecture.md) - System design
- [Operations](operations.md) - Deployment procedures
- [Examples](../examples/README.md) - Code examples
