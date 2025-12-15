# Overview

## Purpose

AphexPipeline is a CDK construct package that generates Argo WorkflowTemplates for deploying CDK applications. It provides a declarative way to define multi-environment deployment pipelines that execute on existing Kubernetes infrastructure.

The package operates as a pure orchestration layer, translating user configuration into Argo workflow definitions that reference execution containers provided by the separate `arbiter-pipeline-infrastructure` package.

**Source**
- `pipeline-infra/lib/aphex-pipeline-stack.ts`
- `.kiro/specs/aphex-pipeline/requirements.md`

## Key Features

### Declarative Pipeline Configuration

Define your entire deployment pipeline in CDK:

```typescript
new AphexPipeline(this, 'Pipeline', {
  clusterName: 'company-pipelines',
  githubOwner: 'my-org',
  githubRepo: 'my-app',
  stacks: [
    { name: 'DatabaseStack', path: 'lib/database-stack.ts' },
    { name: 'ApiStack', path: 'lib/api-stack.ts' },
  ],
  environments: [
    { name: 'dev', account: '111', region: 'us-east-1' },
    { name: 'prod', account: '222', region: 'us-west-2' },
  ],
});
```

### Cluster Discovery

Automatically discovers existing EKS clusters via CloudFormation exports:
- No library dependency on infrastructure package
- Runtime discovery at deployment time
- Works across AWS accounts and regions

**Source**
- `pipeline-infra/lib/aphex-pipeline-stack.ts` (cluster import logic)

### Container Image Management

Uses published container images with `:latest` tags by default:
- `public.ecr.aws/aphex/builder:latest` - Build environment
- `public.ecr.aws/aphex/deployer:latest` - Deployment environment
- `public.ecr.aws/aphex/tester:latest` - Test environment
- `public.ecr.aws/aphex/validator:latest` - Validation environment

Users can override with custom images for specific needs.

**Source**
- `.kiro/specs/aphex-pipeline/requirements.md` (Requirement 15)

### Multi-Environment Support

Deploy to multiple environments in sequence:
- Different AWS accounts per environment
- Different AWS regions per environment
- Different stack configurations per environment
- Optional tests per environment

**Source**
- `pipeline-infra/lib/workflow-template-generator.ts`

### Multi-Tenancy

Multiple pipelines share the same cluster infrastructure:
- Unique resource names prevent conflicts
- Separate service accounts with IRSA
- Separate S3 buckets for artifacts
- Complete isolation between pipelines

**Source**
- `pipeline-infra/examples/multi-pipeline-example.ts`

### Event-Driven Automation

Automatically triggers on GitHub events:
- GitHub webhooks received by Argo Events
- Sensor filters events (e.g., main branch only)
- Workflow created from WorkflowTemplate
- Queues multiple workflows automatically

**Source**
- `.argo/eventsource-github.yaml`
- `.argo/sensor-aphex-pipeline.yaml`

## Architecture

### Two-Package Design

AphexPipeline follows a clean separation:

1. **arbiter-pipeline-infrastructure** (separate, deployed once):
   - EKS cluster with Argo Workflows and Argo Events
   - Published container images
   - Execution scripts
   - CloudFormation exports

2. **aphex-pipeline** (this package, deployed per application):
   - CDK construct for WorkflowTemplate generation
   - Pipeline-specific resources (EventSource, Sensor, ServiceAccount, S3)
   - No library dependency on infrastructure package

**Source**
- `.kiro/docs/architecture.md`

### Deployment Flow

**Step 1: Platform Team** (once)
```bash
# Deploy cluster infrastructure
cdk deploy ArbiterPipelineInfrastructure
```

**Step 2: Application Teams** (per application)
```bash
# Install construct package
npm install aphex-pipeline

# Deploy pipeline
cdk deploy MyAppPipeline
```

**Step 3: Runtime** (automatic)
- GitHub push triggers webhook
- Argo Events creates workflow
- Workflow executes using published containers
- CDK stacks deployed to target accounts

**Source**
- `pipeline-infra/examples/single-pipeline-example.ts`

## Pipeline Stages

### 1. Validation Stage
- Validates configuration schema
- Validates AWS credentials
- Validates CDK context
- Validates build tools
- Fails fast with clear errors

### 2. Build Stage
- Clones repository at commit SHA
- Executes build commands
- Packages artifacts
- Tags with commit SHA and timestamp
- Uploads to S3

### 3. Pipeline Deployment Stage
- Synthesizes Pipeline CDK Stack
- Deploys pipeline updates
- Reads configuration
- Generates WorkflowTemplate
- Applies to Argo (self-modification)

### 4. Environment Stages
- Downloads artifacts from S3
- Sets AWS context (region, account)
- Assumes cross-account role if needed
- Synthesizes CDK stacks just-in-time
- Deploys in configured order
- Captures stack outputs
- Runs tests if configured

**Source**
- `pipeline-scripts/validation_stage.py`
- `pipeline-scripts/build_stage.py`
- `pipeline-scripts/pipeline_deployment_stage.py`
- `pipeline-scripts/environment_deployment_stage.py`

## Getting Started

### Prerequisites

1. **Existing cluster** deployed via `arbiter-pipeline-infrastructure`
2. **AWS CLI** configured with credentials
3. **CDK CLI** installed (`npm install -g aws-cdk`)
4. **kubectl** configured for cluster access
5. **GitHub repository** with admin access
6. **GitHub token** stored in AWS Secrets Manager

### Quick Setup

1. **Install package**:
   ```bash
   npm install aphex-pipeline
   ```

2. **Create pipeline**:
   ```typescript
   import { AphexPipeline } from 'aphex-pipeline';
   
   new AphexPipeline(this, 'Pipeline', {
     clusterName: 'company-pipelines',
     githubOwner: 'my-org',
     githubRepo: 'my-app',
     githubTokenSecretName: 'github-token',
     stacks: [...],
     environments: [...],
   });
   ```

3. **Deploy**:
   ```bash
   cdk deploy
   ```

4. **Configure GitHub webhook** with URL from outputs

5. **Push to trigger** first workflow

**Source**
- `pipeline-infra/examples/single-pipeline-example.ts`
- `pipeline-infra/examples/README.md`

## Configuration

### Stack Definitions

Define CDK stacks to deploy:

```typescript
stacks: [
  { 
    name: 'DatabaseStack', 
    path: 'lib/database-stack.ts' 
  },
  { 
    name: 'ApiStack', 
    path: 'lib/api-stack.ts',
    dependsOn: ['DatabaseStack']  // Optional dependencies
  },
]
```

### Environment Definitions

Define deployment targets:

```typescript
environments: [
  {
    name: 'dev',
    account: '111111111111',
    region: 'us-east-1',
    stacks: ['DatabaseStack', 'ApiStack'],
  },
  {
    name: 'prod',
    account: '222222222222',
    region: 'us-west-2',
    stacks: ['DatabaseStack', 'ApiStack'],
    tests: {
      commands: ['npm run integration-test'],
    },
  },
]
```

**Source**
- `.kiro/docs/api.md` (interface definitions)

## Use Cases

### Multi-Environment Deployments
Deploy to dev, staging, and prod with different configurations and accounts.

### Multi-Region Deployments
Deploy to multiple AWS regions for high availability and disaster recovery.

### Microservices
Deploy multiple services with proper dependency ordering.

### Serverless Applications
Deploy Lambda functions, API Gateway, DynamoDB, and other serverless resources.

### Data Pipelines
Deploy ETL infrastructure with proper sequencing.

**Source**
- `.kiro/docs/example-use-cases.md`

## Multi-Pipeline Scenarios

Multiple application teams can deploy pipelines to the same cluster:

```typescript
// Team A
new AphexPipeline(app, 'FrontendPipeline', {
  clusterName: 'company-pipelines',
  workflowTemplateName: 'frontend-pipeline',
  // ...
});

// Team B
new AphexPipeline(app, 'BackendPipeline', {
  clusterName: 'company-pipelines',
  workflowTemplateName: 'backend-pipeline',
  // ...
});
```

Each pipeline has:
- Unique WorkflowTemplate name
- Unique EventSource and Sensor
- Separate ServiceAccount with IRSA
- Separate S3 bucket

**Source**
- `pipeline-infra/examples/multi-pipeline-example.ts`

## Security

### IRSA (IAM Roles for Service Accounts)

Workflows authenticate to AWS using IRSA:
- No long-lived credentials
- Kubernetes ServiceAccount linked to IAM role
- Automatic credential rotation
- Least-privilege permissions

### Cross-Account Deployment

Deploy to different AWS accounts:
- Assume cross-account IAM roles
- Follows AWS security best practices
- Supports CDK bootstrap pattern

**Source**
- `pipeline-infra/lib/aphex-pipeline-stack.ts` (IRSA configuration)
- `.kiro/docs/operations.md` (security procedures)

## Documentation Structure

- **[Architecture](architecture.md)**: System design and components
- **[Operations](operations.md)**: Deployment, monitoring, troubleshooting
- **[API Reference](api.md)**: Construct interfaces and properties
- **[Data Models](data-models.md)**: Configuration structures
- **[FAQ](faq.md)**: Common questions
- **[Example Use Cases](example-use-cases.md)**: Real-world scenarios

## Archon Integration

This repository participates in the Archon RAG system. Documentation in `.kiro/docs/` is ingested for retrieval and follows the Archon documentation contract defined in `CLAUDE.md`.

## Source Code

- **CDK Construct**: `pipeline-infra/lib/aphex-pipeline-stack.ts`
- **WorkflowTemplate Generator**: `pipeline-infra/lib/workflow-template-generator.ts`
- **Configuration Parser**: `pipeline-infra/lib/config-parser.ts`
- **Examples**: `pipeline-infra/examples/*.ts`
- **Tests**: `pipeline-infra/test/*.ts`

## Contributing

See [README.md](../../README.md) for development setup and contribution guidelines.

## License

MIT License - see LICENSE file for details.
