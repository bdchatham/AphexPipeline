# Container Images

## Overview

AphexPipeline uses container images to execute workflow steps. The construct employs a convention-based approach to construct ECR image URIs, making it easy to use images from your own ECR repositories.

**Source**
- `pipeline-infra/lib/aphex-pipeline-stack.ts` (lines 168-295)
- `pipeline-infra/lib/workflow-template-generator.ts`

## Convention-Based URIs

### Default Behavior

By default, images are constructed using the stack's account and a default region:

```
{account}.dkr.ecr.{region}.amazonaws.com/{repository}:{version}
```

**Defaults:**
- `account`: Stack account (from `env.account`)
- `region`: `us-east-1`
- `version`: `v1.0.1`

**Repositories:**
- Builder: `arbiter-pipeline-builder`
- Deployer: `arbiter-pipeline-deployer`

### Example

```typescript
new AphexPipelineStack(app, 'MyPipeline', {
  env: { account: '123456789012', region: 'us-east-1' },
  // ... other props
});
```

**Resulting URIs:**
- Builder: `123456789012.dkr.ecr.us-east-1.amazonaws.com/arbiter-pipeline-builder:v1.0.1`
- Deployer: `123456789012.dkr.ecr.us-east-1.amazonaws.com/arbiter-pipeline-deployer:v1.0.1`

## Configuration Options

### Custom ECR Account

Use images from a different AWS account:

```typescript
new AphexPipelineStack(app, 'MyPipeline', {
  // ... other props
  containerImageAccount: '987654321098',
});
```

**Result:** `987654321098.dkr.ecr.us-east-1.amazonaws.com/arbiter-pipeline-builder:v1.0.1`

### Custom ECR Region

Use images from a different AWS region:

```typescript
new AphexPipelineStack(app, 'MyPipeline', {
  // ... other props
  containerImageRegion: 'us-west-2',
});
```

**Result:** `123456789012.dkr.ecr.us-west-2.amazonaws.com/arbiter-pipeline-builder:v1.0.1`

### Custom Version

Use a different image version:

```typescript
new AphexPipelineStack(app, 'MyPipeline', {
  // ... other props
  containerImageVersion: 'v2.0.0',
});
```

**Result:** `123456789012.dkr.ecr.us-east-1.amazonaws.com/arbiter-pipeline-builder:v2.0.0`

### Combined Configuration

```typescript
new AphexPipelineStack(app, 'MyPipeline', {
  // ... other props
  containerImageAccount: '987654321098',
  containerImageRegion: 'eu-west-1',
  containerImageVersion: 'v2.1.0',
});
```

**Result:** `987654321098.dkr.ecr.eu-west-1.amazonaws.com/arbiter-pipeline-builder:v2.1.0`

## Custom Images

### Override Convention

For complete control, specify full image URIs:

```typescript
new AphexPipelineStack(app, 'MyPipeline', {
  // ... other props
  builderImage: 'my-registry.io/custom-builder:latest',
  deployerImage: 'my-registry.io/custom-deployer:latest',
});
```

This bypasses the convention-based URI construction entirely.

### Use Cases

**Custom registries:**
- Docker Hub: `myorg/builder:v1.0.0`
- GitHub Container Registry: `ghcr.io/myorg/builder:v1.0.0`
- Private registry: `registry.company.com/builder:v1.0.0`

**Custom repository names:**
- Different naming: `123456789012.dkr.ecr.us-east-1.amazonaws.com/my-custom-builder:v1.0.0`

## ECR Authentication

### Automatic IRSA Configuration

The workflow ServiceAccount is automatically configured with ECR pull permissions via IRSA:

```json
{
  "Effect": "Allow",
  "Action": [
    "ecr:GetAuthorizationToken",
    "ecr:BatchCheckLayerAvailability",
    "ecr:GetDownloadUrlForLayer",
    "ecr:BatchGetImage"
  ],
  "Resource": "*"
}
```

**Source:** `pipeline-infra/lib/aphex-pipeline-stack.ts` (lines 420-430)

### No Additional Configuration

- No secrets needed
- No manual authentication
- Works across accounts (with proper ECR permissions)
- Automatic credential rotation

## Image Requirements

### Builder Image

**Purpose:** Execute build commands and package artifacts

**Required tools:**
- `git` - Clone repository
- `aws` CLI - Upload artifacts to S3
- Build tools (npm, pip, etc.) - Execute build commands

**Environment variables:**
- `AWS_ROLE_ARN` - IRSA role for AWS access
- `AWS_WEB_IDENTITY_TOKEN_FILE` - IRSA token path
- `ARTIFACT_BUCKET` - S3 bucket for artifacts

### Deployer Image

**Purpose:** Deploy CDK stacks and execute tests

**Required tools:**
- `git` - Clone repository
- `aws` CLI - AWS operations
- `cdk` CLI - CDK synthesis and deployment
- `npm` - Install dependencies

**Environment variables:**
- `AWS_ROLE_ARN` - IRSA role for AWS access
- `AWS_WEB_IDENTITY_TOKEN_FILE` - IRSA token path
- `AWS_REGION` - Target region
- `AWS_ACCOUNT` - Target account

## Troubleshooting

### ImagePullBackOff Error

**Symptom:**
```
Failed to pull image: rpc error: code = Unknown desc = Error response from daemon: 
pull access denied for {image}, repository does not exist or may require 'docker login'
```

**Causes:**
1. Image doesn't exist in ECR
2. Wrong account/region/version
3. Missing ECR permissions

**Solutions:**

**Verify image exists:**
```bash
aws ecr describe-images \
  --repository-name arbiter-pipeline-builder \
  --region us-east-1
```

**Check configuration:**
```typescript
// Verify these match your ECR setup
containerImageAccount: '123456789012',
containerImageRegion: 'us-east-1',
containerImageVersion: 'v1.0.0',
```

**Verify ECR permissions:**
```bash
# Check if ServiceAccount role has ECR permissions
kubectl describe serviceaccount workflow-executor -n argo
```

### Wrong Image Version

**Symptom:** Workflow fails with unexpected errors or missing tools

**Solution:** Update version:
```typescript
containerImageVersion: 'v2.0.0',  // Use correct version
```

### Cross-Account Access

**Symptom:** ImagePullBackOff when using images from different account

**Solution:** Configure ECR repository policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowCrossAccountPull",
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::TARGET_ACCOUNT:root"
      },
      "Action": [
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage",
        "ecr:BatchCheckLayerAvailability"
      ]
    }
  ]
}
```

## Best Practices

### Version Pinning

**Recommended:** Pin to specific versions
```typescript
containerImageVersion: 'v1.2.3',  // ✅ Specific version
```

**Avoid:** Using `latest` tag
```typescript
containerImageVersion: 'latest',  // ❌ Unpredictable
```

### Centralized Images

**Recommended:** Use a central ECR account for images
```typescript
containerImageAccount: '111111111111',  // Central account
```

**Benefits:**
- Single source of truth
- Easier updates
- Consistent across pipelines

### Testing New Images

**Process:**
1. Build and push new image version
2. Deploy test pipeline with new version
3. Verify workflow succeeds
4. Update production pipelines

```typescript
// Test pipeline
containerImageVersion: 'v2.0.0-beta',

// Production pipeline (after testing)
containerImageVersion: 'v2.0.0',
```

## Related Documentation

- [Architecture](architecture.md) - System design
- [Operations](operations.md) - Deployment procedures
- [API Reference](api.md) - Configuration properties
