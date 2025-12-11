# AphexPipeline Container Images

This directory contains the Dockerfiles and build scripts for the AphexPipeline container images.

## Container Images

### Builder Image (`aphex-pipeline/builder`)

Used in the **Build Stage** to execute user-defined build commands and package artifacts.

**Includes:**
- Node.js 20 (with npm)
- Python 3 (with pip)
- Git
- AWS CLI v2
- AWS CDK CLI
- Build tools (gcc, g++, make)
- Common Python packages (PyYAML, boto3, requests)

**Use cases:**
- Cloning repository at specific commit
- Running npm/yarn build commands
- Running Python build scripts
- Packaging artifacts
- Uploading artifacts to S3

### Deployer Image (`aphex-pipeline/deployer`)

Used in the **Pipeline Deployment Stage** and **Environment Stages** to synthesize and deploy CDK stacks.

**Includes:**
- Node.js 20 (with npm)
- Python 3 (with pip)
- Git
- AWS CLI v2
- AWS CDK CLI
- kubectl (for applying WorkflowTemplates)
- Build tools (needed for CDK synthesis)
- Python packages (PyYAML, boto3, jsonschema, requests)

**Use cases:**
- Cloning repository at specific commit
- Synthesizing CDK stacks just-in-time
- Deploying CDK stacks via CloudFormation
- Generating WorkflowTemplates from configuration
- Applying WorkflowTemplates to Argo
- Downloading artifacts from S3
- Capturing CloudFormation stack outputs

## Building Images

### Local Build

Build both images locally:

```bash
./build.sh
```

Build with a specific tag:

```bash
./build.sh --tag v1.0.0
```

Build only one image:

```bash
./build.sh --builder-only
./build.sh --deployer-only
```

### Build and Push to ECR

Build and push to Amazon ECR:

```bash
./build.sh --push --account 123456789012 --region us-east-1
```

Build, tag, and push:

```bash
./build.sh --push --account 123456789012 --region us-east-1 --tag v1.0.0
```

The build script will:
1. Build the Docker images
2. Log in to ECR
3. Create ECR repositories if they don't exist (with encryption and scanning enabled)
4. Push the images to ECR

## Image Naming Convention

**Local images:**
- `aphex-pipeline/builder:latest`
- `aphex-pipeline/deployer:latest`

**ECR images:**
- `<account>.dkr.ecr.<region>.amazonaws.com/aphex-pipeline/builder:<tag>`
- `<account>.dkr.ecr.<region>.amazonaws.com/aphex-pipeline/deployer:<tag>`

## Using Images in Argo Workflows

Update your WorkflowTemplate to reference the ECR images:

```yaml
containers:
  - name: build
    image: 123456789012.dkr.ecr.us-east-1.amazonaws.com/aphex-pipeline/builder:latest
    
  - name: deploy
    image: 123456789012.dkr.ecr.us-east-1.amazonaws.com/aphex-pipeline/deployer:latest
```

## Image Updates

When you update the Dockerfiles:

1. Build and test locally:
   ```bash
   ./build.sh
   docker run -it aphex-pipeline/builder:latest bash
   ```

2. Push to ECR with a new version tag:
   ```bash
   ./build.sh --push --account 123456789012 --tag v1.1.0
   ```

3. Update the WorkflowTemplate to use the new tag

4. Optionally update the `latest` tag:
   ```bash
   ./build.sh --push --account 123456789012 --tag latest
   ```

## IAM Permissions Required

To push images to ECR, you need the following IAM permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken",
        "ecr:CreateRepository",
        "ecr:DescribeRepositories",
        "ecr:PutImage",
        "ecr:InitiateLayerUpload",
        "ecr:UploadLayerPart",
        "ecr:CompleteLayerUpload",
        "ecr:BatchCheckLayerAvailability"
      ],
      "Resource": "*"
    }
  ]
}
```

## Troubleshooting

### Build fails with "no space left on device"

Clean up Docker images and build cache:

```bash
docker system prune -a
```

### Push fails with authentication error

Ensure your AWS credentials are configured:

```bash
aws configure
aws sts get-caller-identity
```

### Image is too large

Check image size:

```bash
docker images | grep aphex-pipeline
```

Optimize by:
- Combining RUN commands
- Removing unnecessary packages
- Using multi-stage builds if needed

### kubectl version mismatch

Update the `KUBECTL_VERSION` in `deployer/Dockerfile` to match your EKS cluster version.

## Security Considerations

1. **Image Scanning**: ECR repositories are created with `scanOnPush=true` to automatically scan for vulnerabilities
2. **Encryption**: ECR repositories use AES256 encryption at rest
3. **Base Images**: Using official Node.js images from Docker Hub
4. **Updates**: Regularly update base images and dependencies to get security patches
5. **Secrets**: Never include secrets in the images - use IRSA and Kubernetes secrets instead

## Development

To test changes to the Dockerfiles:

```bash
# Build locally
./build.sh --builder-only

# Run interactively
docker run -it aphex-pipeline/builder:latest bash

# Test commands
node --version
npm --version
python --version
aws --version
cdk --version
git --version
```
