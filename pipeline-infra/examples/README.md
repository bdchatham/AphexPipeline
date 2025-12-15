# AphexPipeline Examples

This directory contains example CDK applications demonstrating different ways to use AphexPipeline.

> **Note**: These are standalone example files meant to be copied to your own project. They may show TypeScript errors in this directory because they're not included in the main tsconfig.json, but they will work correctly when copied to your project's `bin/` directory and compiled with your project's TypeScript configuration.

## Prerequisites

All examples assume you have:

1. **An existing EKS cluster** with Argo Workflows and Argo Events installed
   - Typically deployed using the `aphex-cluster` package
   - Cluster must export its name via CloudFormation (default: "AphexCluster-ClusterName")

2. **AWS CLI configured** with appropriate credentials
   ```bash
   aws configure
   ```

3. **CDK CLI installed**
   ```bash
   npm install -g aws-cdk
   ```

4. **GitHub token** stored in AWS Secrets Manager
   ```bash
   aws secretsmanager create-secret \
     --name github-token \
     --secret-string '{"token":"ghp_your_token_here"}'
   ```

## Examples

### 1. Single Pipeline Example

**File**: `single-pipeline-example.ts`

The simplest configuration - deploy one pipeline with minimal parameters.

**Use when**:
- You have one application to deploy
- You want to use all default settings
- You're just getting started

**Deploy**:
```bash
cd pipeline-infra
npm install
cdk deploy -a "npx ts-node examples/single-pipeline-example.ts"
```

### 2. Multi-Pipeline Example

**File**: `multi-pipeline-example.ts`

Deploy multiple pipelines to the same cluster with proper resource isolation.

**Use when**:
- You have multiple applications (frontend, backend, data processing, etc.)
- You want to share cluster infrastructure to reduce costs
- You need to demonstrate resource isolation

**Features**:
- Three separate pipelines on one cluster
- Unique naming conventions to prevent conflicts
- Separate S3 buckets for each pipeline
- Independent service accounts with IRSA

**Deploy**:
```bash
cd pipeline-infra
npm install

# Deploy all pipelines
cdk deploy --all -a "npx ts-node examples/multi-pipeline-example.ts"

# Deploy specific pipeline
cdk deploy FrontendPipeline -a "npx ts-node examples/multi-pipeline-example.ts"
```

**Verify isolation**:
```bash
# List all WorkflowTemplates (should see all three)
kubectl get workflowtemplate -n argo

# List all EventSources (should see all three)
kubectl get eventsource -n argo-events

# List all Sensors (should see all three)
kubectl get sensor -n argo-events
```

### 3. Custom Cluster Reference Example

**File**: `custom-cluster-reference-example.ts`

Reference clusters with custom export names or deploy to multiple clusters.

**Use when**:
- Your cluster uses a non-default export name
- You have separate prod/dev clusters
- You're deploying to multiple regions

**Features**:
- Custom CloudFormation export names
- Environment-based cluster selection (prod vs dev)
- Multi-region deployment pattern

**Deploy**:
```bash
cd pipeline-infra
npm install

# Deploy to production cluster
ENVIRONMENT=production cdk deploy ProdPipeline \
  -a "npx ts-node examples/custom-cluster-reference-example.ts"

# Deploy to development cluster
ENVIRONMENT=development cdk deploy DevPipeline \
  -a "npx ts-node examples/custom-cluster-reference-example.ts"
```

## Common Patterns

### Finding Your Cluster Export Name

If you're not sure what export name your cluster uses:

```bash
# List all CloudFormation exports
aws cloudformation list-exports --region us-east-1

# Filter for cluster-related exports
aws cloudformation list-exports --region us-east-1 \
  --query 'Exports[?contains(Name, `Cluster`)].{Name:Name,Value:Value}'
```

Look for exports like:
- `AphexCluster-ClusterName` (default from aphex-cluster package)
- `MyCluster-ClusterName` (custom naming)
- `EKSCluster-Name` (alternative naming)

### Required Cluster Exports

Your cluster stack must export:
1. **Cluster name** (e.g., "AphexCluster-ClusterName")
2. **OIDC provider ARN** (e.g., "AphexCluster-OIDCProviderArn")
3. **Kubectl role ARN** (e.g., "AphexCluster-KubectlRoleArn")

### Customizing Resource Names

To avoid conflicts when deploying multiple pipelines:

```typescript
new AphexPipelineStack(app, 'MyPipeline', {
  // ... other props
  
  // Unique names for this pipeline
  workflowTemplateName: 'my-app-pipeline-template',
  eventSourceName: 'my-app-github',
  sensorName: 'my-app-pipeline-sensor',
  serviceAccountName: 'my-app-workflow-executor',
  workflowNamePrefix: 'my-app-',
});
```

### Using Environment Variables

Make your examples configurable via environment variables:

```typescript
new AphexPipelineStack(app, 'MyPipeline', {
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION || 'us-east-1',
  },
  
  githubOwner: process.env.GITHUB_OWNER || 'my-org',
  githubRepo: process.env.GITHUB_REPO || 'my-repo',
  githubTokenSecretName: process.env.GITHUB_TOKEN_SECRET || 'github-token',
  githubBranch: process.env.GITHUB_BRANCH || 'main',
});
```

Then deploy with:
```bash
GITHUB_OWNER=my-org GITHUB_REPO=my-app cdk deploy
```

## After Deployment

### 1. Verify Resources

```bash
# Check WorkflowTemplate
kubectl get workflowtemplate -n argo

# Check EventSource
kubectl get eventsource -n argo-events

# Check Sensor
kubectl get sensor -n argo-events

# Check Service Account
kubectl get serviceaccount -n argo
```

### 2. Get Stack Outputs

```bash
# Get webhook URL
aws cloudformation describe-stacks \
  --stack-name MyPipeline \
  --query 'Stacks[0].Outputs[?OutputKey==`ArgoEventsWebhookUrl`].OutputValue' \
  --output text

# Get artifact bucket
aws cloudformation describe-stacks \
  --stack-name MyPipeline \
  --query 'Stacks[0].Outputs[?OutputKey==`ArtifactBucketName`].OutputValue' \
  --output text
```

### 3. Configure GitHub Webhook

1. Go to your GitHub repository settings
2. Navigate to Webhooks → Add webhook
3. Use the webhook URL from stack outputs
4. Content type: `application/json`
5. Events: Push events, Pull request events
6. Save webhook

### 4. Trigger First Workflow

```bash
# Make an empty commit to trigger the pipeline
git commit --allow-empty -m "Test pipeline"
git push origin main
```

### 5. Monitor Workflow

```bash
# Port-forward to Argo UI
kubectl port-forward -n argo svc/argo-server 2746:2746

# Open browser to http://localhost:2746
```

## Troubleshooting

### Pipeline Not Deploying

**Error**: "Export AphexCluster-ClusterName not found"

**Solution**: Verify your cluster exports the cluster name:
```bash
aws cloudformation list-exports --query 'Exports[?Name==`AphexCluster-ClusterName`]'
```

If not found, either:
- Update your cluster stack to export the cluster name
- Use `clusterExportName` prop to specify the correct export name

### Workflow Not Triggering

**Check**:
1. GitHub webhook is configured correctly
2. EventSource pod is running: `kubectl get pods -n argo-events`
3. Sensor pod is running: `kubectl get pods -n argo-events`
4. Check EventSource logs: `kubectl logs -n argo-events -l eventsource-name=github`

### Resource Name Conflicts

**Error**: "WorkflowTemplate already exists"

**Solution**: Use unique resource names for each pipeline:
```typescript
workflowTemplateName: 'my-unique-pipeline-template',
eventSourceName: 'my-unique-github',
sensorName: 'my-unique-pipeline-sensor',
```

## Next Steps

- Read the [Architecture Documentation](../../.kiro/docs/architecture.md)
- Review the [Operations Guide](../../.kiro/docs/operations.md)
- Check the [API Reference](../../.kiro/docs/api.md)
- See [Troubleshooting Guide](../../.kiro/docs/troubleshooting.md)

## Support

- [GitHub Issues](https://github.com/bdchatham/aphex-pipeline/issues)
- [Documentation](https://github.com/bdchatham/aphex-pipeline)
