# AphexPipeline

A self-modifying CDK deployment platform built on Amazon EKS, Argo Workflows, and Argo Events.

## Features

- **Event-Driven**: Automatically triggers on code changes via GitHub webhooks
- **Just-in-Time Synthesis**: Synthesizes CDK stacks immediately before deployment
- **Self-Modifying**: Dynamically updates workflow topology based on configuration
- **Multi-Environment**: Deploy to dev, staging, prod in sequence
- **Multi-Account**: Cross-account deployments using AWS best practices
- **Batteries Included**: Everything orchestrated automatically

## Installation

```bash
npm install @bdchatham/AphexPipeline
```

## Prerequisites

- **Existing EKS cluster** with Argo Workflows and Argo Events installed
  - Typically deployed using the `aphex-cluster` package
  - Cluster must export its name via CloudFormation (default: "AphexCluster-ClusterName")
- AWS account with appropriate permissions
- AWS CDK CLI: `npm install -g aws-cdk`
- kubectl configured for cluster access
- GitHub repository with admin access
- GitHub token stored in AWS Secrets Manager

## Quick Start

### 1. Deploy EKS Cluster (if not already done)

```bash
# Use the aphex-cluster package to deploy the shared cluster infrastructure
npm install @bdchatham/aphex-cluster
# Follow aphex-cluster documentation to deploy cluster
```

### 2. Create GitHub Token Secret

```bash
aws secretsmanager create-secret \
  --name github-token \
  --secret-string '{"token":"ghp_your_token_here"}'
```

### 3. Use in Your CDK App

```typescript
import { AphexPipelineStack } from '@bdchatham/AphexPipeline';
import * as cdk from 'aws-cdk-lib';

const app = new cdk.App();

new AphexPipelineStack(app, 'MyPipeline', {
  env: { 
    account: '123456789012', 
    region: 'us-east-1' 
  },
  
  // Required: GitHub configuration
  githubOwner: 'my-org',
  githubRepo: 'my-repo',
  githubTokenSecretName: 'github-token',
  
  // Optional: Cluster reference (defaults to CloudFormation export lookup)
  // clusterExportName: 'AphexCluster-ClusterName', // default
  
  // Optional: Other configuration
  githubBranch: 'main',
  workflowTemplateName: 'my-app-pipeline-template',
});

app.synth();
```

### 3. Create aphex-config.yaml

```yaml
version: "1.0"

build:
  commands:
    - npm install
    - npm run build
    - npm test

environments:
  - name: dev
    region: us-east-1
    account: "123456789012"
    stacks:
      - name: MyAppStack
        path: lib/my-app-stack.ts
```

### 4. Verify Cluster Prerequisites

```bash
# Configure kubectl for your cluster
aws eks update-kubeconfig --name <cluster-name> --region us-east-1

# Verify Argo Workflows is installed
kubectl get pods -n argo

# Verify Argo Events is installed
kubectl get pods -n argo-events
```

### 5. Deploy Pipeline

```bash
cdk deploy MyPipeline
```

## Configuration Options

### Required Parameters

- `githubOwner` - GitHub organization or user
- `githubRepo` - Repository name
- `githubTokenSecretName` - AWS Secrets Manager secret name

### Optional Parameters

**Cluster Reference**:
- `clusterName` - Name of the existing cluster (required)
- `clusterExportPrefix` - CloudFormation export prefix for cluster resources (default: `'AphexCluster-{clusterName}-'`)
  - Use this to work with different cluster export naming conventions
  - Example: `'ArbiterCluster-'` for Arbiter clusters
  - Example: `'MyCluster-prod-'` for custom naming
- `pipelineCreatorRoleArn` - ARN of a role that can assume the kubectl role (optional)
  - Use this when the kubectl role has restricted trust policies
  - The role should have permission to assume the cluster's kubectl role
  - Example: `'arn:aws:iam::123456789012:role/pipeline-creator'`

**GitHub**:
- `githubBranch` - Branch to trigger on (default: `'main'`)
- `githubWebhookSecretName` - Webhook validation secret

**Storage**:
- `artifactBucketName` - S3 bucket name (default: auto-generated)
- `artifactRetentionDays` - Retention period (default: `90`)

**Argo**:
- `argoNamespace` - Argo Workflows namespace (default: `'argo'`)
- `argoEventsNamespace` - Argo Events namespace (default: `'argo-events'`)

**Naming** (important for multi-pipeline deployments):
- `eventSourceName` - EventSource name (default: `'github'`)
- `sensorName` - Sensor name (default: `'aphex-pipeline-sensor'`)
- `workflowTemplateName` - Template name (default: `'aphex-pipeline-template'`)
- `serviceAccountName` - Service account (default: `'workflow-executor'`)
- `workflowNamePrefix` - Workflow name prefix (default: `'aphex-pipeline-'`)

**Advanced**:
- `builderImage` - Custom builder container image
- `deployerImage` - Custom deployer container image
- `configPath` - Path to aphex-config.yaml (default: `'../aphex-config.yaml'`)

## What Gets Created

When you deploy AphexPipelineStack, it creates **pipeline-specific resources** on your existing cluster:

**Pipeline Resources**:
- ✅ WorkflowTemplate (pipeline topology)
- ✅ EventSource (GitHub webhook receiver)
- ✅ Sensor (workflow trigger)
- ✅ Service account with IRSA
- ✅ IAM roles and policies
- ✅ S3 bucket for artifacts
- ✅ GitHub secrets in Kubernetes
- ✅ Logging configuration

**Shared Cluster Resources** (managed separately by aphex-cluster):
- ℹ️ EKS cluster (pre-existing)
- ℹ️ Argo Workflows (pre-installed)
- ℹ️ Argo Events (pre-installed)
- ℹ️ EventBus (pre-existing)

**Key Benefits**:
- Multiple pipelines can share the same cluster
- Destroying a pipeline doesn't affect the cluster
- Cost-efficient multi-tenancy

## Examples

See the [examples/](examples/) directory for complete working examples:

### Single Pipeline

Minimal configuration for deploying one pipeline:

```typescript
new AphexPipelineStack(app, 'MyPipeline', {
  env: { account: '123456789012', region: 'us-east-1' },
  githubOwner: 'my-org',
  githubRepo: 'my-app',
  githubTokenSecretName: 'github-token',
  // All other parameters use defaults
});
```

See [examples/single-pipeline-example.ts](examples/single-pipeline-example.ts)

### Multiple Pipelines on Same Cluster

Deploy multiple pipelines with proper resource isolation:

```typescript
// Frontend pipeline
new AphexPipelineStack(app, 'FrontendPipeline', {
  githubRepo: 'frontend',
  workflowTemplateName: 'frontend-pipeline-template',
  eventSourceName: 'frontend-github',
  sensorName: 'frontend-pipeline-sensor',
});

// Backend pipeline
new AphexPipelineStack(app, 'BackendPipeline', {
  githubRepo: 'backend',
  workflowTemplateName: 'backend-pipeline-template',
  eventSourceName: 'backend-github',
  sensorName: 'backend-pipeline-sensor',
});
```

See [examples/multi-pipeline-example.ts](examples/multi-pipeline-example.ts)

### Using with Arbiter Cluster

Reference an Arbiter cluster with custom export prefix:

```typescript
new AphexPipelineStack(app, 'MyPipeline', {
  env: { account: '123456789012', region: 'us-east-1' },
  clusterName: 'arbiter-pipeline-cluster',
  clusterExportPrefix: 'ArbiterCluster-',  // Override default naming
  githubOwner: 'my-org',
  githubRepo: 'my-app',
  githubTokenSecretName: 'github-token',
});
```

This allows the construct to work with clusters that use different CloudFormation export naming conventions.

### Using with Pipeline Creator Role

For clusters with restricted kubectl role trust policies, use a pipeline creator role:

```typescript
// Import the pipeline creator role ARN from cluster exports
const pipelineCreatorRoleArn = cdk.Fn.importValue('ArbiterCluster-PipelineCreatorRoleArn');

new AphexPipelineStack(app, 'MyPipeline', {
  env: { account: '123456789012', region: 'us-east-1' },
  clusterName: 'arbiter-pipeline-cluster',
  clusterExportPrefix: 'ArbiterCluster-',
  pipelineCreatorRoleArn: pipelineCreatorRoleArn,  // Use intermediary role
  githubOwner: 'my-org',
  githubRepo: 'my-app',
  githubTokenSecretName: 'github-token',
});
```

The pipeline creator role should:
- Have permission to assume the cluster's kubectl role
- Trust the Lambda service principal (for CDK custom resources)
- Be exported by the cluster stack for discovery

### Custom Cluster Reference

Reference a cluster with a custom export name:

```typescript
new AphexPipelineStack(app, 'MyPipeline', {
  // ... other props
  clusterExportName: 'MyCompany-EKS-ClusterName',
});
```

See [examples/custom-cluster-reference-example.ts](examples/custom-cluster-reference-example.ts)

## Documentation

- [Complete Documentation](https://github.com/bdchatham/aphex-pipeline)
- [Quick Start Guide](https://github.com/bdchatham/aphex-pipeline/blob/main/.kiro/docs/quick-start-example.md)
- [Library Usage](https://github.com/bdchatham/aphex-pipeline/blob/main/.kiro/docs/library-usage.md)
- [Architecture](https://github.com/bdchatham/aphex-pipeline/blob/main/.kiro/docs/architecture.md)
- [API Reference](https://github.com/bdchatham/aphex-pipeline/blob/main/.kiro/docs/api.md)
- [Operations Guide](https://github.com/bdchatham/aphex-pipeline/blob/main/.kiro/docs/operations.md)

## Support

- [GitHub Issues](https://github.com/bdchatham/aphex-pipeline/issues)
- [FAQ](https://github.com/bdchatham/aphex-pipeline/blob/main/.kiro/docs/faq.md)

## License

MIT

## Contributing

Contributions welcome! Please read our contributing guidelines.
