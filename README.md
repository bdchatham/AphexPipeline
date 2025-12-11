# AphexPipeline

A self-modifying CDK deployment platform built on Amazon EKS, Argo Workflows, and Argo Events.

## Overview

AphexPipeline is a generic, reusable CI/CD platform that:
- Automatically triggers on code changes via GitHub webhooks
- Synthesizes and deploys CDK stacks just-in-time at each stage
- Dynamically modifies its own workflow topology based on configuration
- Supports multi-environment, multi-account deployments
- Provides comprehensive logging and monitoring

## Project Structure

```
.
├── pipeline-infra/          # CDK infrastructure for the pipeline itself
│   ├── bin/                 # CDK app entry point
│   ├── lib/                 # CDK stack definitions
│   └── test/                # Infrastructure tests
├── pipeline-scripts/        # Python scripts for workflow generation
│   └── tests/               # Script tests
├── .argo/                   # Argo Workflows and Events configurations
├── aphex-config.yaml        # Pipeline configuration
└── aphex-config.schema.json # Configuration schema
```

## Prerequisites

- AWS CLI configured with appropriate credentials
- Node.js 18+ and npm
- Python 3.9+
- AWS CDK CLI (`npm install -g aws-cdk`)
- kubectl (for EKS cluster management)

## Getting Started

### 1. Install Dependencies

```bash
# Install CDK dependencies
cd pipeline-infra
npm install
cd ..

# Install Python dependencies
cd pipeline-scripts
pip install -r requirements.txt
cd ..
```

### 2. Configure

Edit `aphex-config.yaml` to define your environments and build process.

### 3. Bootstrap

See the design document for detailed bootstrap instructions.

## Cross-Account Deployments

AphexPipeline supports deploying to multiple AWS accounts using AWS CDK's native bootstrap pattern.

### Setting Up Cross-Account Access (Recommended: CDK Bootstrap)

AphexPipeline uses CDK's built-in cross-account deployment mechanism, which is the AWS-recommended approach.

1. **Bootstrap the pipeline account** (if not already done):
   ```bash
   cdk bootstrap aws://PIPELINE_ACCOUNT/REGION
   ```

2. **Bootstrap each target account with trust to the pipeline account**:
   ```bash
   cdk bootstrap aws://TARGET_ACCOUNT/TARGET_REGION \
     --trust PIPELINE_ACCOUNT \
     --cloudformation-execution-policies 'arn:aws:iam::aws:policy/AdministratorAccess'
   ```
   
   This creates the CDK toolkit stack with deployment roles that trust your pipeline account.

3. **In your aphex-config.yaml**, specify the target account ID:
   ```yaml
   environments:
     - name: production
       region: us-east-1
       account: "123456789012"  # Target account ID
       stacks:
         - name: MyAppStack
           path: lib
   ```

The pipeline will automatically:
- Detect when the target account differs from the pipeline account
- Assume the cross-account role
- Use CDK's bootstrap deployment role (`cdk-hnb659fds-deploy-role-{account}-{region}`)

### Alternative: Custom Cross-Account Role

If you prefer not to use CDK bootstrap, you can create a custom IAM role:

1. **In each target account**, create an IAM role named `AphexPipelineCrossAccountRole` with:
   - Trust relationship allowing the pipeline account to assume it
   - Permissions for CloudFormation, CDK, and other required AWS services

2. **Example trust policy** (replace `<PIPELINE_ACCOUNT_ID>` with your pipeline account):
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Principal": {
           "AWS": "arn:aws:iam::<PIPELINE_ACCOUNT_ID>:role/AphexPipelineWorkflowExecutionRole"
         },
         "Action": "sts:AssumeRole"
       }
     ]
   }
   ```

Note: The CDK bootstrap approach is recommended as it follows AWS best practices and integrates seamlessly with CDK's deployment workflow.

## Development

### Running Tests

```bash
# CDK infrastructure tests
cd pipeline-infra
npm test

# Python script tests
cd pipeline-scripts
pytest
```

### Building

```bash
# Compile TypeScript
cd pipeline-infra
npm run build
```

## Documentation

- [Requirements](.kiro/specs/aphex-pipeline/requirements.md)
- [Design](.kiro/specs/aphex-pipeline/design.md)
- [Tasks](.kiro/specs/aphex-pipeline/tasks.md)

## License

MIT
