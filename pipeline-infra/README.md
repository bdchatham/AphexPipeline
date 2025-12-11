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

- AWS account with appropriate permissions
- AWS CDK CLI: `npm install -g aws-cdk`
- GitHub repository with admin access
- GitHub token stored in AWS Secrets Manager

## Quick Start

### 1. Create GitHub Token Secret

```bash
aws secretsmanager create-secret \
  --name github-token \
  --secret-string '{"token":"ghp_your_token_here"}'
```

### 2. Use in Your CDK App

```typescript
import { AphexPipelineStack } from '@bdchatham/AphexPipeline';
import * as cdk from 'aws-cdk-lib';

const app = new cdk.App();

new AphexPipelineStack(app, 'MyPipeline', {
  env: { 
    account: '123456789012', 
    region: 'us-east-1' 
  },
  
  // Required
  githubOwner: 'my-org',
  githubRepo: 'my-repo',
  githubTokenSecretName: 'github-token',
  
  // Optional
  githubBranch: 'main',
  clusterName: 'my-pipeline',
  minNodes: 3,
  maxNodes: 20,
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

### 4. Deploy

```bash
cdk deploy MyPipeline
```

## Configuration Options

### Required Parameters

- `githubOwner` - GitHub organization or user
- `githubRepo` - Repository name
- `githubTokenSecretName` - AWS Secrets Manager secret name

### Optional Parameters

**GitHub**:
- `githubBranch` - Branch to trigger on (default: `'main'`)
- `githubWebhookSecretName` - Webhook validation secret

**EKS Cluster**:
- `clusterName` - Cluster name (default: `'aphex-pipeline-cluster'`)
- `clusterVersion` - Kubernetes version (default: `V1_28`)
- `nodeInstanceTypes` - Instance types (default: `[t3.medium, t3.large]`)
- `minNodes` - Minimum nodes (default: `2`)
- `maxNodes` - Maximum nodes (default: `10`)
- `desiredNodes` - Desired nodes (default: `3`)

**Storage**:
- `artifactBucketName` - S3 bucket name
- `artifactRetentionDays` - Retention period (default: `90`)

**Argo**:
- `argoWorkflowsVersion` - Helm chart version (default: `'0.41.0'`)
- `argoEventsVersion` - Helm chart version (default: `'2.4.0'`)
- `argoNamespace` - Namespace (default: `'argo'`)
- `argoEventsNamespace` - Namespace (default: `'argo-events'`)

**Naming**:
- `eventSourceName` - EventSource name (default: `'github'`)
- `sensorName` - Sensor name (default: `'aphex-pipeline-sensor'`)
- `workflowTemplateName` - Template name (default: `'aphex-pipeline-template'`)
- `serviceAccountName` - Service account (default: `'workflow-executor'`)

**Advanced**:
- `vpc` - Use existing VPC
- `builderImage` - Custom builder container image
- `deployerImage` - Custom deployer container image

## What Gets Created

When you deploy AphexPipelineStack, it automatically creates:

- ✅ VPC with public and private subnets
- ✅ EKS cluster with managed node groups
- ✅ Argo Workflows (via Helm)
- ✅ Argo Events (via Helm)
- ✅ EventBus for Argo Events
- ✅ Service account with IRSA
- ✅ IAM roles and policies
- ✅ S3 bucket for artifacts
- ✅ GitHub secrets in Kubernetes
- ✅ EventSource for GitHub webhooks
- ✅ Sensor for workflow triggering
- ✅ Logging configuration
- ✅ WorkflowTemplate from config

## Examples

### Use Existing VPC

```typescript
import * as ec2 from 'aws-cdk-lib/aws-ec2';

const vpc = ec2.Vpc.fromLookup(this, 'ExistingVpc', {
  vpcId: 'vpc-12345678',
});

new AphexPipelineStack(app, 'MyPipeline', {
  // ... other props
  vpc: vpc,
});
```

### Custom Container Images

```typescript
new AphexPipelineStack(app, 'MyPipeline', {
  // ... other props
  builderImage: '123456789012.dkr.ecr.us-east-1.amazonaws.com/builder:latest',
  deployerImage: '123456789012.dkr.ecr.us-east-1.amazonaws.com/deployer:latest',
});
```

### Multiple Pipelines

```typescript
new AphexPipelineStack(app, 'FrontendPipeline', {
  // ... props for frontend
  githubRepo: 'frontend',
  clusterName: 'frontend-pipeline',
});

new AphexPipelineStack(app, 'BackendPipeline', {
  // ... props for backend
  githubRepo: 'backend',
  clusterName: 'backend-pipeline',
});
```

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
