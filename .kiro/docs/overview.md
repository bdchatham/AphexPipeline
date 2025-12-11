# Overview

## Purpose

AphexPipeline is a self-modifying CDK deployment platform built on Amazon EKS, Argo Workflows, and Argo Events. It provides automated infrastructure deployment with the unique capability to dynamically alter its own workflow topology based on configuration changes.

The platform serves as a generic, reusable CI/CD solution for deploying any CDK-based infrastructure across multiple environments and AWS accounts, following a just-in-time synthesis approach where CDK stacks are synthesized immediately before deployment at each stage.

## Key Features

### Self-Modification
- Dynamically updates its own workflow topology based on configuration changes
- Reads `aphex-config.yaml` during pipeline deployment stage
- Generates and applies updated WorkflowTemplate to Argo Workflows
- Changes take effect in the next workflow run

### Just-in-Time Synthesis
- Synthesizes CDK stacks immediately before deployment at each stage
- Ensures deployments always use the latest code from the current git commit
- No pre-synthesis or caching of templates across stages
- Traditional CI/CD pipeline flow with linear stage progression

### Event-Driven Automation
- Automatically triggers on GitHub push events via webhooks
- Argo Events receives webhooks and creates workflow instances
- Filters events (e.g., main branch only) before triggering
- Queues multiple workflows automatically

### Multi-Environment Support
- Deploy to multiple environments (dev, staging, prod) in sequence
- Each environment can have different AWS regions and accounts
- Configure stack deployment order per environment
- Optional post-deployment tests per environment

### Cross-Account Deployments
- Supports deploying to multiple AWS accounts
- Uses CDK bootstrap pattern (recommended) or custom IAM roles
- Automatic detection and assumption of cross-account roles
- Follows AWS security best practices

### Validation First
- Comprehensive pre-flight checks before workflow execution
- Validates configuration schema against JSON schema
- Validates AWS credentials for each environment
- Validates CDK context requirements
- Validates build tool availability
- Fails fast with clear error messages

### Application-Agnostic
- Works with any CDK-based infrastructure
- No application-specific code or logic required
- User-defined build commands from configuration
- Extensible via hooks for custom logic

### Comprehensive Monitoring
- Built-in logging to CloudWatch and Argo UI
- Metrics emission for workflow and deployment success/failure
- Workflow metadata recording (ID, commit SHA, timestamps, status)
- Configurable notifications (Slack, email) on completion/failure

## Architecture Overview

AphexPipeline consists of:

1. **EKS Cluster**: Managed Kubernetes cluster running Argo components
2. **Argo Workflows**: Orchestrates pipeline stages as Kubernetes pods
3. **Argo Events**: Receives GitHub webhooks and triggers workflows
4. **Pipeline CDK Stack**: Defines the pipeline infrastructure itself
5. **Container Images**: Builder and deployer images with required tools
6. **S3 Bucket**: Stores build artifacts with versioning
7. **IAM Roles**: IRSA for workflow execution, cross-account roles
8. **CloudWatch**: Logging and monitoring

## Pipeline Stages

### 1. Validation Stage
- Validates configuration schema
- Validates AWS credentials
- Validates CDK context
- Validates build tools
- Fails fast if any validation fails

### 2. Build Stage
- Clones repository at specific commit SHA
- Executes user-defined build commands
- Packages artifacts
- Tags artifacts with commit SHA and timestamp
- Uploads artifacts to S3

### 3. Pipeline Deployment Stage
- Synthesizes Pipeline CDK Stack
- Deploys Pipeline CDK Stack (if changes exist)
- Reads `aphex-config.yaml`
- Generates updated WorkflowTemplate
- Applies WorkflowTemplate to Argo (self-modification)

### 4. Environment Stages (per environment)
- Downloads artifacts from S3
- Sets AWS region and account context
- Assumes cross-account role (if needed)
- Synthesizes Application CDK Stacks just-in-time
- Deploys stacks in configured order
- Captures stack outputs
- Executes post-deployment tests (optional)

## Getting Started

### Prerequisites
- AWS account with appropriate permissions
- AWS CLI configured
- Node.js 18+ and npm
- Python 3.9+
- AWS CDK CLI
- kubectl
- GitHub repository with admin access

### Quick Setup

1. **Install dependencies**:
   ```bash
   cd pipeline-infra && npm install
   cd ../pipeline-scripts && pip install -r requirements.txt
   ```

2. **Configure pipeline** in `aphex-config.yaml`:
   ```yaml
   version: "1.0"
   build:
     commands: [npm install, npm run build]
   environments:
     - name: dev
       region: us-east-1
       account: "123456789012"
       stacks:
         - name: MyAppStack
           path: lib/my-app-stack.ts
   ```

3. **Bootstrap AWS accounts**:
   ```bash
   cdk bootstrap aws://ACCOUNT/REGION
   ```

4. **Deploy pipeline infrastructure**:
   ```bash
   cd pipeline-infra
   cdk deploy AphexPipelineStack
   ```

5. **Configure GitHub webhook** with URL from CDK outputs

6. **Push to trigger** your first workflow

## Configuration

The `aphex-config.yaml` file defines:
- **Build commands**: Commands to execute in build stage
- **Environments**: List of deployment targets
  - Name, AWS region, AWS account
  - CDK stacks to deploy (in order)
  - Optional post-deployment tests

Configuration is validated against `aphex-config.schema.json` before execution.

## Use Cases

AphexPipeline is ideal for:
- **Multi-environment deployments**: Dev, staging, prod with different configurations
- **Multi-account deployments**: Separate AWS accounts for different environments
- **Multi-region deployments**: Deploy to multiple regions for HA/DR
- **Microservices**: Deploy multiple services with dependencies
- **Data pipelines**: Deploy ETL infrastructure with proper ordering
- **Serverless applications**: Deploy Lambda, API Gateway, DynamoDB, etc.

## Property-Based Testing

AphexPipeline uses property-based testing to verify correctness:
- **25 correctness properties** defined in design document
- **Hypothesis** library for Python property-based testing
- **100+ examples per property** for extensive coverage
- Properties validate universal behaviors across all inputs

## Documentation Structure

- **[README.md](../../README.md)**: Quick start and overview
- **[Architecture](architecture.md)**: Detailed system architecture with diagrams
- **[Operations](operations.md)**: Monitoring, troubleshooting, maintenance
- **[API Documentation](api.md)**: Python module APIs
- **[Data Models](data-models.md)**: Configuration and metadata structures
- **[FAQ](faq.md)**: Common questions and answers
- **[Example Use Cases](example-use-cases.md)**: Real-world scenarios
- **[Requirements](../.kiro/specs/aphex-pipeline/requirements.md)**: Feature requirements
- **[Design](../.kiro/specs/aphex-pipeline/design.md)**: System design and properties
- **[Tasks](../.kiro/specs/aphex-pipeline/tasks.md)**: Implementation task list

## Archon Integration

This repository's documentation is ingested by the Archon RAG system from the `.kiro/docs/` directory. The documentation follows the Archon documentation contract to ensure accurate retrieval and grounding in code.

## Source References

- **Pipeline Infrastructure**: `pipeline-infra/lib/aphex-pipeline-stack.ts`
- **Pipeline Scripts**: `pipeline-scripts/*.py`
- **Configuration Schema**: `aphex-config.schema.json`
- **Argo Configuration**: `.argo/*.yaml`
- **Container Images**: `containers/builder/`, `containers/deployer/`
- **Tests**: `pipeline-scripts/tests/*.py`, `pipeline-infra/test/*.ts`

## Contributing

See [README.md](../../README.md) for development setup and contribution guidelines.

## License

MIT License - see LICENSE file for details.
