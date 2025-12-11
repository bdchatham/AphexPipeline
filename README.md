# AphexPipeline

A self-modifying CDK deployment platform built on Amazon EKS, Argo Workflows, and Argo Events.

## Overview

AphexPipeline is a generic, reusable CI/CD platform that provides automated infrastructure deployment with unique self-modification capabilities. It's designed to be application-agnostic and can deploy any CDK-based infrastructure across multiple environments and AWS accounts.

### Key Features

- **Event-Driven**: Automatically triggers on code changes via GitHub webhooks
- **Just-in-Time Synthesis**: Synthesizes CDK stacks immediately before deployment at each stage
- **Self-Modifying**: Dynamically updates its own workflow topology based on configuration changes
- **Multi-Environment**: Deploy to multiple environments (dev, staging, prod) in sequence
- **Multi-Account**: Support for cross-account deployments using AWS best practices
- **Validation First**: Comprehensive pre-flight checks before workflow execution
- **Application-Agnostic**: Works with any CDK-based infrastructure without custom logic
- **Comprehensive Monitoring**: Built-in logging, metrics, and notifications

### How It Works

1. **Push to GitHub** → Webhook triggers Argo Events
2. **Validation Stage** → Validates configuration, credentials, and tools
3. **Build Stage** → Executes build commands, packages artifacts
4. **Pipeline Deployment** → Updates pipeline infrastructure and workflow topology
5. **Environment Stages** → Deploys CDK stacks to each configured environment
6. **Test Stages** → Runs post-deployment tests (optional)

## Project Structure

```
.
├── pipeline-infra/              # CDK infrastructure for the pipeline itself
│   ├── bin/                     # CDK app entry point
│   ├── lib/                     # CDK stack definitions
│   │   ├── aphex-pipeline-stack.ts
│   │   ├── config-parser.ts
│   │   └── workflow-template-generator.ts
│   └── test/                    # Infrastructure tests
├── pipeline-scripts/            # Python scripts for pipeline stages
│   ├── build_stage.py           # Build stage logic
│   ├── config_parser.py         # Configuration parsing
│   ├── environment_deployment_stage.py  # Environment deployment
│   ├── github_event_parser.py   # GitHub webhook parsing
│   ├── monitoring.py            # Monitoring and metrics
│   ├── pipeline_deployment_stage.py  # Pipeline self-modification
│   ├── test_execution_stage.py  # Test execution
│   ├── validation.py            # Validation functions
│   ├── validation_stage.py      # Validation stage CLI
│   └── tests/                   # Property-based and unit tests
├── containers/                  # Container images for pipeline stages
│   ├── builder/                 # Builder image (build tools)
│   └── deployer/                # Deployer image (CDK, kubectl)
├── .argo/                       # Argo Workflows and Events configurations
│   ├── eventsource-github.yaml  # GitHub webhook receiver
│   └── sensor-aphex-pipeline.yaml  # Workflow trigger
├── .kiro/                       # Documentation and specifications
│   ├── docs/                    # Architecture and operations docs
│   └── specs/                   # Requirements, design, tasks
├── aphex-config.yaml            # Pipeline configuration (example)
└── aphex-config.schema.json     # Configuration JSON schema
```

## Prerequisites

- **AWS Account**: With appropriate permissions for EKS, S3, CloudFormation, IAM
- **AWS CLI**: Configured with credentials (`aws configure`)
- **Node.js**: 18+ and npm
- **Python**: 3.9+
- **AWS CDK CLI**: `npm install -g aws-cdk`
- **kubectl**: For EKS cluster management
- **GitHub Repository**: With admin access for webhook configuration

## Using as a Library

AphexPipeline is designed to be imported into your own CDK project as a reusable construct.

### Quick Start

1. **Install the package**:
   ```bash
   npm install @bdchatham/aphex-pipeline
   ```

2. **Create a GitHub token secret in AWS Secrets Manager**:
   ```bash
   aws secretsmanager create-secret \
     --name github-token \
     --secret-string '{"token":"ghp_your_token_here"}'
   ```

3. **Import and use in your CDK app**:
   ```typescript
   import { AphexPipelineStack } from 'aphex-pipeline';
   
   new AphexPipelineStack(app, 'MyPipeline', {
     env: { account: '123456789012', region: 'us-east-1' },
     
     // Required: GitHub configuration
     githubOwner: 'my-org',
     githubRepo: 'my-repo',
     githubTokenSecretName: 'github-token',
     
     // Optional: customize as needed
     githubBranch: 'main',
     clusterName: 'my-pipeline',
     minNodes: 3,
     maxNodes: 20,
   });
   ```

4. **Deploy**:
   ```bash
   cdk deploy MyPipeline
   ```

5. **Configure GitHub webhook** using the URL from stack outputs

That's it! The construct handles everything:
- Creates EKS cluster with Argo Workflows and Argo Events
- Configures GitHub EventSource and Sensor
- Sets up logging and monitoring
- Creates IAM roles and S3 buckets
- Deploys all Kubernetes manifests

See the [Library Usage Guide](.kiro/docs/library-usage.md) for detailed instructions on:

- Installation options (NPM, git submodule, local path)
- Advanced configuration and customization
- Using with existing VPC or EKS cluster
- Custom container images and templates
- Extending the stack with custom resources
- Managing multiple pipelines
- Testing your integration

**Quick example**:

```typescript
import { AphexPipelineStack } from 'aphex-pipeline';

new AphexPipelineStack(app, 'MyPipeline', {
  env: { account: '123456789012', region: 'us-east-1' },
  githubOwner: 'bdchatham',
  githubRepo: 'my-repo',
  githubTokenSecretName: 'github-token',
});
```

## Quick Start (Standalone Deployment)

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

### 2. Configure Your Pipeline

Create or edit `aphex-config.yaml`:

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
    tests:
      commands:
        - npm run integration-test

  - name: prod
    region: us-west-2
    account: "987654321098"
    stacks:
      - name: MyAppStack
        path: lib/my-app-stack.ts
```

### 3. Bootstrap AWS Accounts

Bootstrap the pipeline account and any target accounts:

```bash
# Bootstrap pipeline account
cdk bootstrap aws://PIPELINE_ACCOUNT/REGION

# Bootstrap target accounts with trust to pipeline account
cdk bootstrap aws://TARGET_ACCOUNT/TARGET_REGION \
  --trust PIPELINE_ACCOUNT \
  --cloudformation-execution-policies 'arn:aws:iam::aws:policy/AdministratorAccess'
```

### 4. Deploy Pipeline Infrastructure

```bash
cd pipeline-infra
cdk synth AphexPipelineStack
cdk deploy AphexPipelineStack
```

### 5. Configure GitHub Webhook

1. Get the webhook URL from CDK outputs
2. Go to your GitHub repository → Settings → Webhooks
3. Add webhook:
   - **Payload URL**: (from CDK outputs)
   - **Content type**: application/json
   - **Events**: Push events, Pull request events
   - **Active**: ✓

### 6. Trigger Your First Workflow

```bash
git commit --allow-empty -m "Trigger first workflow"
git push origin main
```

Monitor the workflow in the Argo Workflows UI (URL from CDK outputs).

## Configuration

### Configuration Schema

The `aphex-config.yaml` file defines your pipeline behavior. See `aphex-config.schema.json` for the complete schema.

#### Required Fields

- `version`: Configuration version (currently "1.0")
- `build`: Build configuration
  - `commands`: List of build commands to execute
- `environments`: List of deployment environments
  - `name`: Environment name
  - `region`: AWS region
  - `account`: AWS account ID (12 digits)
  - `stacks`: List of CDK stacks to deploy
    - `name`: Stack name
    - `path`: Path to stack definition

#### Optional Fields

- `environments[].tests`: Post-deployment tests
  - `commands`: List of test commands to execute

### Validation

Before workflow execution, the validation stage checks:

- **Configuration Schema**: Valid YAML matching schema
- **AWS Credentials**: Available for each environment
- **CDK Context**: Required context values present
- **Build Tools**: Required tools available in container

Run validation locally:

```bash
python pipeline-scripts/validation_stage.py \
  --config aphex-config.yaml \
  --skip-aws-validation  # For local testing
```

## Cross-Account Deployments

AphexPipeline supports deploying to multiple AWS accounts using CDK's native bootstrap pattern (recommended) or custom IAM roles.

### Option 1: CDK Bootstrap (Recommended)

This is the AWS-recommended approach and integrates seamlessly with CDK.

1. **Bootstrap target accounts with trust**:
   ```bash
   cdk bootstrap aws://TARGET_ACCOUNT/TARGET_REGION \
     --trust PIPELINE_ACCOUNT \
     --cloudformation-execution-policies 'arn:aws:iam::aws:policy/AdministratorAccess'
   ```

2. **Configure in aphex-config.yaml**:
   ```yaml
   environments:
     - name: production
       region: us-east-1
       account: "123456789012"  # Target account
       stacks:
         - name: MyAppStack
           path: lib
   ```

The pipeline automatically detects cross-account deployments and uses CDK's bootstrap roles.

### Option 2: Custom IAM Role

Create a custom role in each target account:

1. **Role name**: `AphexPipelineCrossAccountRole`
2. **Trust policy**: Allow pipeline account to assume role
3. **Permissions**: CloudFormation, CDK, required AWS services

## Development

### Running Tests

```bash
# CDK infrastructure tests
cd pipeline-infra
npm test

# Python property-based tests
cd pipeline-scripts
pytest tests/ -v

# Run specific property tests
pytest tests/test_validation_properties.py -v
```

### Building Container Images

```bash
cd containers
./build.sh builder v1.0.0
./build.sh deployer v1.0.0
```

### Local Testing

Test individual stages locally:

```bash
# Test validation
python pipeline-scripts/validation_stage.py \
  --config aphex-config.yaml \
  --skip-aws-validation

# Test configuration parsing
python -c "from config_parser import parse_config; print(parse_config('aphex-config.yaml'))"

# Test build stage (requires Docker)
docker run -it aphex-pipeline/builder:latest /bin/bash
```

## Monitoring and Operations

### Accessing Argo Workflows UI

Get the URL from CDK outputs:

```bash
aws cloudformation describe-stacks \
  --stack-name AphexPipelineStack \
  --query 'Stacks[0].Outputs[?OutputKey==`ArgoWorkflowsUrl`].OutputValue' \
  --output text
```

### Viewing Workflow Logs

```bash
# Via kubectl
kubectl logs -n argo <workflow-pod-name> -c <stage-name>

# Via Argo CLI
argo logs -n argo <workflow-name>

# Via CloudWatch
aws logs tail /aws/eks/aphex-pipeline/workflows --follow
```

### Monitoring Metrics

AphexPipeline emits CloudWatch metrics:
- Workflow success/failure count
- Workflow duration
- Stage duration
- Deployment success/failure

Create CloudWatch dashboards to visualize these metrics.

### Troubleshooting

See [Operations Guide](.kiro/docs/operations.md) for detailed troubleshooting procedures.

Common issues:
- **Workflow not triggering**: Check GitHub webhook delivery
- **Build failures**: Check build logs, verify tools available
- **Deployment failures**: Check CloudFormation events, verify IAM permissions
- **Self-modification not working**: Verify configuration is valid

## Architecture

AphexPipeline consists of:

- **EKS Cluster**: Runs Argo Workflows and Argo Events
- **Argo Workflows**: Orchestrates pipeline stages
- **Argo Events**: Receives GitHub webhooks and triggers workflows
- **S3 Bucket**: Stores build artifacts
- **IAM Roles**: IRSA for workflow execution, cross-account roles
- **CloudWatch**: Logging and monitoring

See [Architecture Documentation](.kiro/docs/architecture.md) for detailed diagrams and component descriptions.

## Documentation

### Library Usage
- [Library Usage Guide](.kiro/docs/library-usage.md) - How to import and use AphexPipeline in your CDK project

### Specifications
- [Requirements](.kiro/specs/aphex-pipeline/requirements.md) - Feature requirements and acceptance criteria
- [Design](.kiro/specs/aphex-pipeline/design.md) - System design and correctness properties
- [Tasks](.kiro/specs/aphex-pipeline/tasks.md) - Implementation task list

### Guides
- [Architecture](.kiro/docs/architecture.md) - System architecture and components
- [Operations](.kiro/docs/operations.md) - Monitoring, troubleshooting, maintenance
- [API Documentation](.kiro/docs/api.md) - API reference
- [Data Models](.kiro/docs/data-models.md) - Data structures
- [Validation Usage](pipeline-scripts/VALIDATION_USAGE.md) - Validation stage guide

## Testing

AphexPipeline uses property-based testing to verify correctness properties:

- **Property 1-25**: Universal properties that should hold across all inputs
- **Hypothesis**: Python property-based testing library
- **100+ examples per property**: Extensive test coverage

Run all tests:

```bash
cd pipeline-scripts
pytest tests/ -v
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass
6. Submit a pull request

## License

MIT License - see LICENSE file for details

## Support

For issues, questions, or contributions:
- Open an issue on GitHub
- See [Operations Guide](.kiro/docs/operations.md) for troubleshooting
- Review [Architecture Documentation](.kiro/docs/architecture.md) for system details

## Acknowledgments

Built with:
- [Argo Workflows](https://argoproj.github.io/argo-workflows/)
- [Argo Events](https://argoproj.github.io/argo-events/)
- [AWS CDK](https://aws.amazon.com/cdk/)
- [Amazon EKS](https://aws.amazon.com/eks/)
- [Hypothesis](https://hypothesis.readthedocs.io/) (property-based testing)
