# Architecture

## Overview

AphexPipeline is a CDK construct package that generates Argo WorkflowTemplates for deploying CDK applications. It operates as a pure orchestration layer that references existing cluster infrastructure managed by the separate `arbiter-pipeline-infrastructure` package.

**Source**
- `pipeline-infra/lib/aphex-pipeline-stack.ts`
- `.kiro/specs/aphex-pipeline/design.md`
- `.kiro/specs/aphex-pipeline/requirements.md`

## Two-Package Architecture

### Package Separation

AphexPipeline follows a clean separation between infrastructure and orchestration:

1. **arbiter-pipeline-infrastructure** (separate package, already deployed):
   - EKS cluster with Argo Workflows and Argo Events
   - Published container images (`public.ecr.aws/aphex/*:latest`)
   - Execution scripts inside containers
   - CloudFormation exports for cluster discovery

2. **aphex-pipeline** (this package):
   - CDK construct for WorkflowTemplate generation
   - Pipeline-specific resource management
   - No library dependency on arbiter-pipeline-infrastructure
   - Discovers cluster at deployment time via CloudFormation exports

### Dependency Model

**Deployment-time dependency only** - no library imports:

```typescript
// aphex-pipeline package.json
{
  "dependencies": {
    "aws-cdk-lib": "^2.117.0",
    "constructs": "^10.0.0"
    // NO arbiter-pipeline-infrastructure dependency
  }
}
```

The packages communicate through:
- CloudFormation exports (cluster discovery)
- Published container images (execution environment)
- Documented script interfaces (execution contract)

## Cluster Discovery

### CloudFormation Exports

AphexPipeline discovers the cluster using CloudFormation exports:

```typescript
// Import cluster attributes at deployment time
const clusterName = cdk.Fn.importValue(`AphexCluster-${props.clusterName}-ClusterName`);
const oidcProviderArn = cdk.Fn.importValue(`AphexCluster-${props.clusterName}-OIDCProviderArn`);
const kubectlRoleArn = cdk.Fn.importValue(`AphexCluster-${props.clusterName}-KubectlRoleArn`);
```

**Required Exports** (provided by arbiter-pipeline-infrastructure):
- `AphexCluster-${clusterName}-ClusterName` - EKS cluster name
- `AphexCluster-${clusterName}-OIDCProviderArn` - OIDC provider for IRSA
- `AphexCluster-${clusterName}-KubectlRoleArn` - kubectl IAM role
- `AphexCluster-${clusterName}-ClusterSecurityGroupId` - Cluster security group

**Source**
- `pipeline-infra/lib/aphex-pipeline-stack.ts` (cluster import logic)
- `cluster_implementation_notes.md` (export naming convention)

## Container Images

### Default Images

AphexPipeline references published container images with `:latest` tags by default:

```typescript
const DEFAULT_IMAGES = {
  builder: 'public.ecr.aws/aphex/builder:latest',
  deployer: 'public.ecr.aws/aphex/deployer:latest',
  tester: 'public.ecr.aws/aphex/tester:latest',
  validator: 'public.ecr.aws/aphex/validator:latest',
};
```

### Image Override

Users can override default images for custom requirements:

```typescript
new AphexPipeline(this, 'Pipeline', {
  clusterName: 'my-cluster',
  builderImage: 'my-registry/custom-builder:v1.0.0',
  deployerImage: 'my-registry/custom-deployer:v1.0.0',
  // ...
});
```

### Versioning Strategy

- **`:latest` tag** (default): Automatic updates when platform team publishes new images
- **Explicit versions** (optional): Pin to specific versions for production stability
- **Git SHA tags** (optional): Pin to exact commit for debugging

**Source**
- `.kiro/specs/aphex-pipeline/requirements.md` (Requirement 15)
- `ARCHITECTURE_INTEGRATION.md` (container image strategy)

## Components

### AphexPipeline Construct

The main CDK construct that creates pipeline-specific resources.

**Responsibilities**:
- Generate Argo WorkflowTemplate from user configuration
- Create EventSource for GitHub webhooks
- Create Sensor for workflow triggering
- Create ServiceAccount with IRSA
- Create S3 bucket for artifacts
- Create IAM roles and policies

**Does NOT**:
- Create or manage EKS cluster
- Install Argo Workflows or Argo Events
- Build or publish container images
- Implement execution scripts

**Source**
- `pipeline-infra/lib/aphex-pipeline-stack.ts`

### WorkflowTemplate Generator

Translates user's stack and environment configuration into Argo WorkflowTemplate YAML.

**Inputs**:
- Stack definitions (name, path, dependencies)
- Environment definitions (name, account, region, stacks)
- Build commands
- Test commands

**Outputs**:
- Argo WorkflowTemplate YAML with stages for:
  - Validation
  - Build
  - Pipeline deployment
  - Environment deployments (one per environment)
  - Tests (if configured)

**Container References**:
```yaml
- name: build
  container:
    image: public.ecr.aws/aphex/builder:latest
    command: ["/usr/local/bin/aphex-build"]
    args:
    - "{{workflow.parameters.repo-url}}"
    - "{{workflow.parameters.commit-sha}}"
    - "npm install && npm run build"
    - "{{workflow.parameters.artifact-bucket}}"
```

**Source**
- `pipeline-infra/lib/workflow-template-generator.ts`

### Pipeline-Specific Resources

Resources created for each pipeline instance:

1. **WorkflowTemplate**: Defines the pipeline topology
2. **EventSource**: Receives GitHub webhooks
3. **Sensor**: Triggers workflows based on events
4. **ServiceAccount**: Kubernetes service account with IRSA
5. **IAM Role**: AWS IAM role for workflow execution
6. **S3 Bucket**: Artifact storage (pipeline-specific)

**Isolation**: Each pipeline has unique resource names to prevent conflicts.

**Source**
- `pipeline-infra/lib/aphex-pipeline-stack.ts`

## Execution Contract

### Script Interfaces

AphexPipeline invokes scripts inside containers using documented interfaces:

**Builder Script**:
```bash
aphex-build <repo-url> <commit-sha> <build-commands> <artifact-bucket>
```

**Deployer Scripts**:
```bash
aphex-deploy-pipeline <repo-url> <commit-sha> <stack-name> <artifact-bucket>
aphex-deploy-stack <repo-url> <commit-sha> <environment> <stack-list> <artifact-bucket>
```

**Tester Script**:
```bash
aphex-test <test-commands>
```

**Validator Script**:
```bash
aphex-validate <config-path>
```

**Source**
- `cluster_implementation_notes.md` (script interfaces)
- `ARCHITECTURE_INTEGRATION.md` (execution contract)

### Structured Output

Scripts output structured JSON that Argo captures:

```json
{
  "success": true,
  "data": {
    "message": "Operation completed",
    "artifact_path": "s3://bucket/abc123/",
    "details": { ... }
  },
  "timestamp": "2025-12-13T17:43:35.379952"
}
```

Argo WorkflowTemplate extracts values using jq filters:

```yaml
outputs:
  parameters:
  - name: artifact-path
    valueFrom:
      path: /tmp/output.json
      jqFilter: .data.artifact_path
```

**Source**
- `cluster_implementation_notes.md` (output format)

## Multi-Tenancy

### Resource Isolation

Multiple pipelines share the same cluster with isolation through:

1. **Unique Resource Names**:
   - WorkflowTemplate: `${pipelineName}-template`
   - EventSource: `${pipelineName}-github`
   - Sensor: `${pipelineName}-sensor`

2. **Separate Service Accounts**:
   - Each pipeline has its own ServiceAccount with IRSA
   - IAM permissions scoped to pipeline needs

3. **Separate S3 Buckets**:
   - Each pipeline stores artifacts in its own bucket
   - Prevents cross-pipeline artifact access

4. **Shared Cluster Resources**:
   - All pipelines share EKS cluster
   - All pipelines share Argo Workflows and Argo Events
   - All pipelines use same `argo` and `argo-events` namespaces

**Source**
- `pipeline-infra/examples/multi-pipeline-example.ts`
- `.kiro/specs/aphex-pipeline/requirements.md` (Requirement 14)

### Pipeline Destruction

When a pipeline is destroyed:
- Only pipeline-specific resources are removed
- Cluster remains intact
- Other pipelines continue functioning
- Shared Argo installations unaffected

**Source**
- `.kiro/specs/aphex-pipeline/requirements.md` (Requirement 14.5)

## Deployment Flow

### Step 1: Platform Team Deploys Infrastructure (Once)

```bash
# In arbiter-pipeline-infrastructure repository
cdk deploy ArbiterPipelineInfrastructure
```

Creates:
- EKS cluster
- Argo Workflows + Events
- CloudFormation exports
- Publishes container images

### Step 2: Application Team Deploys Pipeline (Many Times)

```bash
# In application repository
npm install aphex-pipeline
```

```typescript
import { AphexPipeline } from 'aphex-pipeline';

new AphexPipeline(this, 'MyAppPipeline', {
  clusterName: 'company-pipelines',  // Reference by name
  githubOwner: 'my-org',
  githubRepo: 'my-app',
  stacks: [...],
  environments: [...],
});
```

```bash
cdk deploy MyAppPipeline
```

Creates:
- WorkflowTemplate
- EventSource + Sensor
- ServiceAccount + IAM role
- S3 bucket

### Step 3: Runtime Execution

1. GitHub webhook triggers Argo Events
2. Sensor creates Workflow from WorkflowTemplate
3. Workflow steps execute using published container images
4. Scripts run inside containers
5. CDK stacks are deployed to target accounts

**Source**
- `pipeline-infra/examples/single-pipeline-example.ts`
- `.kiro/docs/operations.md` (deployment procedures)

## Data Flow

```
User's CDK App
    ↓
AphexPipeline Construct
    ↓
WorkflowTemplate YAML
    ↓
Argo Workflows (in cluster)
    ↓
Container Execution (published images)
    ↓
Execution Scripts (in containers)
    ↓
AWS Resources (CDK stacks deployed)
```

## Security

### IRSA Configuration

Workflows use IAM Roles for Service Accounts (IRSA) for AWS authentication:

```typescript
// Create IAM role with OIDC trust policy
const executionRole = new iam.Role(this, 'ExecutionRole', {
  assumedBy: new iam.FederatedPrincipal(
    oidcProviderArn,
    {
      StringEquals: {
        [`oidc.eks.${region}.amazonaws.com/id/${oidcProviderId}:sub`]: 
          `system:serviceaccount:argo:${serviceAccountName}`,
      },
    },
    'sts:AssumeRoleWithWebIdentity'
  ),
});
```

**Environment Variables** (set in WorkflowTemplate):
```yaml
env:
- name: AWS_ROLE_ARN
  value: arn:aws:iam::123456789012:role/pipeline-execution-role
- name: AWS_WEB_IDENTITY_TOKEN_FILE
  value: /var/run/secrets/eks.amazonaws.com/serviceaccount/token
- name: AWS_REGION
  value: us-east-1
```

**Source**
- `pipeline-infra/lib/aphex-pipeline-stack.ts` (IRSA configuration)
- `cluster_implementation_notes.md` (IRSA requirements)

### Cross-Account Deployment

For deploying to different AWS accounts:

```typescript
// Add sts:AssumeRole permission
executionRole.addToPolicy(new iam.PolicyStatement({
  actions: ['sts:AssumeRole'],
  resources: ['*'], // Or specific role ARN patterns
}));
```

Scripts assume target account roles before deployment.

**Source**
- `.kiro/specs/aphex-pipeline/requirements.md` (Requirement 7.2)

## Benefits

### Loose Coupling
- No library dependency between packages
- Infrastructure and orchestration evolve independently
- Version conflicts eliminated

### Simpler User Experience
- Application teams install one package
- Reference cluster by name
- No infrastructure management

### Multi-Tenant Friendly
- One cluster serves many teams
- Cost-efficient resource sharing
- Complete pipeline isolation

### Automatic Updates
- `:latest` tag means new images used automatically
- Platform team controls image publishing
- Application teams get updates without code changes

### Clear Ownership
- Platform team: Cluster infrastructure
- Application teams: Pipeline configuration
- Clean boundary between concerns

**Source**
- `ARCHITECTURE_INTEGRATION.md` (benefits analysis)
- `.kiro/specs/aphex-pipeline/REFACTORING_PLAN.md`

## Limitations

### Current Limitations

1. **Container Images Not Published**: Images must be built and pushed by platform team
2. **CloudFormation Export Dependency**: Cluster must export specific values
3. **Single Region Per Cluster**: Each cluster serves one AWS region
4. **No Cluster Modification**: Pipelines cannot modify cluster configuration

### Future Enhancements

1. **Explicit Image Versions**: Support pinning to specific versions for production
2. **Parallel Environment Deployment**: Deploy multiple environments concurrently
3. **Manual Approval Gates**: Require human approval before production deployment
4. **Rollback Capabilities**: Automatic rollback on deployment failure
5. **Custom Workflow Steps**: Allow users to inject custom stages

**Source**
- `.kiro/specs/aphex-pipeline/tasks.md` (future work)
- `cluster_implementation_notes.md` (known limitations)

## Related Documentation

- [Operations Guide](.kiro/docs/operations.md) - Deployment and monitoring
- [API Reference](.kiro/docs/api.md) - Construct interfaces
- [Design Specification](.kiro/specs/aphex-pipeline/design.md) - Detailed design
- [Requirements](.kiro/specs/aphex-pipeline/requirements.md) - System requirements
