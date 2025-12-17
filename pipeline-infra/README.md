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

### 6. Configure GitHub Webhook

After deployment, get the webhook secret from stack outputs:

```bash
aws cloudformation describe-stacks \
  --stack-name MyPipeline \
  --query 'Stacks[0].Outputs[?OutputKey==`WebhookSecretValue`].OutputValue' \
  --output text
```

Then configure the webhook in GitHub:
1. Go to your repository settings → Webhooks → Add webhook
2. Set Payload URL to the webhook URL from stack outputs
3. Set Content type to `application/json`
4. Set Secret to the value from the command above
5. Select events: Push events, Pull requests
6. Click "Add webhook"

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
- `githubWebhookSecretName` - (Optional) AWS Secrets Manager secret name for webhook validation
  - If not provided, a unique secret is generated automatically per pipeline (recommended)
  - If provided, uses the secret from AWS Secrets Manager (legacy mode)

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

**Webhook Service**:
- `webhookService` - Configuration for the EventSource webhook Kubernetes service
  - `enabled` - Whether to create a service (default: `true`)
  - `type` - Service type: `'LoadBalancer'`, `'NodePort'`, or `'ClusterIP'` (default: `'LoadBalancer'`)
  - `port` - Service port (default: `12000`)
  - `nodePort` - NodePort value when type is NodePort (default: auto-assigned)
  - `annotations` - Service annotations for cloud provider configuration (default: `{ 'service.beta.kubernetes.io/aws-load-balancer-type': 'nlb' }`)
  - `labels` - Additional service labels (default: `{}`)

**Advanced**:
- `builderImage` - Custom builder container image
- `deployerImage` - Custom deployer container image
- `configPath` - Path to aphex-config.yaml (default: `'../aphex-config.yaml'`)

## Webhook Service Configuration

The construct automatically creates a Kubernetes Service for the EventSource webhook with intelligent defaults for production use.

### Default Configuration (LoadBalancer with NLB)

By default, the construct creates an AWS Network Load Balancer:

```typescript
new AphexPipelineStack(app, 'MyPipeline', {
  // ... other props
  // Uses default: LoadBalancer with NLB
});
```

**Result:**
- Creates AWS NLB (~$16/month)
- Webhook URL: `http://<nlb-dns>:12000/push`
- Internet-facing, production-ready
- Best for: Single pipeline or 1-5 pipelines

### NodePort Configuration (Cost-Effective)

For cost-conscious deployments or custom routing:

```typescript
new AphexPipelineStack(app, 'MyPipeline', {
  // ... other props
  webhookService: {
    type: 'NodePort',
    nodePort: 30000, // Optional: specify port
  },
});
```

**Result:**
- No LoadBalancer cost
- Access via: `http://<node-ip>:30000/push`
- Requires external routing (Ingress, API Gateway, etc.)
- Best for: On-premise, hybrid cloud, or custom setups

### ClusterIP Configuration (Internal Only)

For use with Ingress controllers:

```typescript
new AphexPipelineStack(app, 'MyPipeline', {
  // ... other props
  webhookService: {
    type: 'ClusterIP',
  },
});
```

**Result:**
- Internal service only
- URL: `http://<service-name>.argo-events.svc.cluster.local:12000/push`
- Use with Ingress for HTTPS and path-based routing
- Best for: Multiple pipelines sharing one Ingress

### Custom Annotations

Configure AWS-specific features:

```typescript
new AphexPipelineStack(app, 'MyPipeline', {
  // ... other props
  webhookService: {
    type: 'LoadBalancer',
    annotations: {
      'service.beta.kubernetes.io/aws-load-balancer-type': 'nlb',
      'service.beta.kubernetes.io/aws-load-balancer-scheme': 'internal', // Internal LB
      'service.beta.kubernetes.io/load-balancer-source-ranges': '192.30.252.0/22', // GitHub IPs
    },
  },
});
```

### Disable Service Creation

For advanced scenarios where you manage external access manually:

```typescript
new AphexPipelineStack(app, 'MyPipeline', {
  // ... other props
  webhookService: {
    enabled: false,
  },
});
```

## Security: Per-Pipeline Webhook Secrets

Each pipeline automatically generates a **unique webhook secret** for GitHub webhook validation with **unique Kubernetes secret names** to prevent conflicts.

### Why This Matters

- **Isolation**: Each pipeline has its own secret - compromising one doesn't affect others
- **Blast Radius**: If a secret is compromised, only that pipeline is affected
- **Audit Trail**: Know exactly which repository triggered which pipeline
- **No Conflicts**: Multiple pipelines can coexist in the same namespace
- **Best Practice**: Follows GitHub's security recommendations for webhook validation

### How It Works

1. **Deployment**: CDK generates a random 64-character hex secret
2. **Unique Naming**: Secret is named `<eventSourceName>-webhook-secret` (e.g., `app1-github-webhook-secret`)
3. **Storage**: Secret is stored in Kubernetes and output in CloudFormation
4. **GitHub Config**: You configure this secret in your GitHub webhook settings
5. **Validation**: GitHub signs each webhook with the secret; Argo Events validates it

### Multiple Pipelines Example

```typescript
// Pipeline 1
new AphexPipelineStack(app, 'Pipeline1', {
  eventSourceName: 'app1-github',
  // ... other props
});
// Creates secret: app1-github-webhook-secret

// Pipeline 2
new AphexPipelineStack(app, 'Pipeline2', {
  eventSourceName: 'app2-github',
  // ... other props
});
// Creates secret: app2-github-webhook-secret

// No conflicts! ✅
```

### Legacy Mode

If you provide `githubWebhookSecretName` (AWS Secrets Manager secret), the construct will use that instead of generating a new secret. This maintains backward compatibility with existing deployments.

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

## Troubleshooting

### Permission Error: "is not authorized to perform: sts:AssumeRole"

**Error Message:**
```
User: arn:aws:sts::ACCOUNT:assumed-role/HandlerServiceRole/... 
is not authorized to perform: sts:AssumeRole 
on resource: arn:aws:iam::ACCOUNT:role/kubectl-role
```

**Cause:** The kubectl Lambda cannot assume the kubectl role because the kubectl role's trust policy doesn't allow it.

**Solution 1: Use Pipeline Creator Role (Recommended)**

Add the `pipelineCreatorRoleArn` parameter to your stack:

```typescript
new AphexPipelineStack(app, 'MyPipeline', {
  // ... other props
  pipelineCreatorRoleArn: 'arn:aws:iam::123456789012:role/pipeline-creator',
});
```

The pipeline creator role should:
1. Trust the Lambda service principal
2. Have permission to assume the kubectl role
3. Be configured in your cluster stack

**Solution 2: Update Kubectl Role Trust Policy**

If you control the cluster stack, update the kubectl role to trust Lambda:

```typescript
// In your cluster stack
kubectlRole.assumeRolePolicy?.addStatements(
  new iam.PolicyStatement({
    effect: iam.Effect.ALLOW,
    principals: [new iam.ServicePrincipal('lambda.amazonaws.com')],
    actions: ['sts:AssumeRole'],
  })
);
```

**Note:** Solution 1 is more secure as it limits which Lambdas can assume the kubectl role.

### Invalid ARN Format Error

**Error Message:**
```
pipelineCreatorRoleArn must be a valid IAM role ARN in the format 
arn:aws:iam::ACCOUNT_ID:role/ROLE_NAME
```

**Cause:** The provided ARN is not in the correct format.

**Solution:** Ensure the ARN follows the pattern `arn:aws:iam::123456789012:role/role-name`

Common mistakes:
- Using a user ARN instead of role ARN: `arn:aws:iam::123456789012:user/...` ❌
- Missing account ID: `arn:aws:iam:::role/...` ❌
- Wrong service: `arn:aws:eks::123456789012:role/...` ❌

### CloudFormation Export Not Found

**Error Message:**
```
Export AphexCluster-CLUSTER_NAME-KubectlRoleArn cannot be found
```

**Cause:** The cluster stack doesn't export the kubectl role ARN, or the export name doesn't match.

**Solution 1:** Use the pipeline creator role instead:
```typescript
pipelineCreatorRoleArn: 'arn:aws:iam::123456789012:role/pipeline-creator',
```

**Solution 2:** Verify the cluster export name:
```bash
aws cloudformation list-exports --query "Exports[?Name=='AphexCluster-CLUSTER_NAME-KubectlRoleArn']"
```

**Solution 3:** Use a custom export prefix:
```typescript
clusterExportPrefix: 'ArbiterCluster-',  // Match your cluster's exports
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
