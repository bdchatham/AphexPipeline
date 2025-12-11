# Frequently Asked Questions

## General Questions

### What is AphexPipeline?

AphexPipeline is a self-modifying CDK deployment platform built on Amazon EKS, Argo Workflows, and Argo Events. It provides automated infrastructure deployment with the unique capability to dynamically alter its own workflow topology based on configuration changes.

### What makes AphexPipeline "self-modifying"?

AphexPipeline can update its own workflow topology based on changes to `aphex-config.yaml`. When you add or remove environments in the configuration, the pipeline deployment stage generates and applies an updated WorkflowTemplate to Argo Workflows. The changes take effect in the next workflow run.

### Is AphexPipeline application-specific?

No, AphexPipeline is application-agnostic. It works with any CDK-based infrastructure without requiring application-specific code or logic. You define your build commands and CDK stacks in the configuration, and AphexPipeline handles the deployment.

### What is "just-in-time synthesis"?

Just-in-time synthesis means CDK stacks are synthesized immediately before deployment at each stage, rather than being pre-synthesized at the beginning of the workflow. This ensures deployments always use the latest code from the current git commit and follows a traditional CI/CD pipeline flow.

### How does AphexPipeline differ from AWS CodePipeline?

Key differences:
- **Self-modification**: AphexPipeline can update its own topology dynamically
- **Just-in-time synthesis**: CDK stacks are synthesized at each stage
- **Kubernetes-based**: Runs on EKS with Argo Workflows
- **Application-agnostic**: No pipeline-specific code required
- **Property-based testing**: Extensive correctness properties validated

### What are the main use cases?

- Multi-environment deployments (dev, staging, prod)
- Multi-account deployments (separate AWS accounts)
- Multi-region deployments (HA/DR)
- Microservices with dependencies
- Data pipelines with ordered stack deployments
- Serverless applications

## Setup and Configuration

### What are the prerequisites?

- AWS account with appropriate permissions
- AWS CLI configured
- Node.js 18+ and npm
- Python 3.9+
- AWS CDK CLI
- kubectl
- GitHub repository with admin access

### How do I get started?

1. Install dependencies
2. Configure `aphex-config.yaml`
3. Bootstrap AWS accounts with CDK
4. Deploy Pipeline CDK Stack
5. Configure GitHub webhook
6. Push to trigger first workflow

See [README.md](../../README.md) for detailed quick start guide.

### What goes in aphex-config.yaml?

The configuration file defines:
- Build commands to execute
- List of environments to deploy to
- For each environment:
  - Name, AWS region, AWS account
  - CDK stacks to deploy (in order)
  - Optional post-deployment tests

See `aphex-config.schema.json` for the complete schema.

### How do I validate my configuration?

Run the validation stage locally:

```bash
python pipeline-scripts/validation_stage.py \
  --config aphex-config.yaml \
  --skip-aws-validation  # For local testing
```

This validates:
- Configuration schema
- AWS credentials (if not skipped)
- CDK context
- Build tools

### Can I use custom container images?

Yes! Update the container images in:
1. Build the new images: `cd containers && ./build.sh builder v1.0.0`
2. Update WorkflowTemplate generator to reference new images
3. Commit and push changes

## Deployment

### How do cross-account deployments work?

AphexPipeline supports two approaches:

**Option 1: CDK Bootstrap (Recommended)**
```bash
cdk bootstrap aws://TARGET_ACCOUNT/REGION \
  --trust PIPELINE_ACCOUNT \
  --cloudformation-execution-policies 'arn:aws:iam::aws:policy/AdministratorAccess'
```

**Option 2: Custom IAM Role**
Create `AphexPipelineCrossAccountRole` in each target account with trust to pipeline account.

The pipeline automatically detects cross-account deployments and assumes the appropriate role.

### What order do stacks deploy in?

Stacks deploy in the order specified in `aphex-config.yaml` for each environment. This allows you to handle dependencies:

```yaml
stacks:
  - name: NetworkStack      # Deploys first
  - name: DatabaseStack     # Deploys second (can reference NetworkStack outputs)
  - name: ApiStack          # Deploys third (can reference DatabaseStack outputs)
```

### How do I add a new environment?

1. Add the environment to `aphex-config.yaml`:
   ```yaml
   environments:
     - name: new-env
       region: us-west-2
       account: "123456789012"
       stacks:
         - name: MyStack
           path: lib/my-stack.ts
   ```

2. Commit and push

3. First workflow: Pipeline deployment stage generates new WorkflowTemplate

4. Second workflow: New environment is deployed!

This demonstrates self-modification in action.

### Can I deploy to multiple regions?

Yes! Create separate environments for each region:

```yaml
environments:
  - name: us-east
    region: us-east-1
    account: "123456789012"
    stacks: [...]
  
  - name: us-west
    region: us-west-2
    account: "123456789012"
    stacks: [...]
```

### How do I skip an environment temporarily?

Remove it from `aphex-config.yaml` or comment it out. The pipeline deployment stage will update the WorkflowTemplate to exclude that environment.

## Monitoring and Troubleshooting

### How do I view workflow logs?

**Via Argo UI**: Access the URL from CDK outputs, click on workflow, view logs per stage

**Via kubectl**:
```bash
kubectl logs -n argo <workflow-pod-name> -c <stage-name>
```

**Via CloudWatch**:
```bash
aws logs tail /aws/eks/aphex-pipeline/workflows --follow
```

### Why isn't my workflow triggering?

Check:
1. GitHub webhook delivery (Settings → Webhooks → Recent Deliveries)
2. Argo Events EventSource is running: `kubectl get pods -n argo-events`
3. Sensor is running: `kubectl get sensors -n argo-events`
4. Branch filter matches (default: main branch only)

See [Operations Guide](.kiro/docs/operations.md#workflow-not-triggering) for detailed troubleshooting.

### Why did my build fail?

Common causes:
- Missing build tools in container
- Build command errors
- Test failures
- S3 upload permissions

Check build logs in Argo UI or via kubectl. Test build commands locally in the builder container.

### Why did my deployment fail?

Common causes:
- CDK synthesis errors (invalid CDK code)
- CloudFormation errors (resource conflicts, limits)
- IAM permission issues
- Cross-account role assumption failures
- Missing CDK context

Check CloudFormation events for detailed error messages:
```bash
aws cloudformation describe-stack-events \
  --stack-name <StackName> \
  --max-items 20
```

### How do I debug self-modification issues?

1. Verify configuration is valid: `python pipeline-scripts/validation_stage.py --config aphex-config.yaml`
2. Check pipeline deployment stage logs
3. Verify WorkflowTemplate was applied: `kubectl get workflowtemplate -n argo aphex-pipeline-template -o yaml`
4. Check for errors in kubectl apply

### Where are metrics stored?

- **CloudWatch Metrics**: Namespace `AphexPipeline`
- **CloudWatch Logs**: Log group `/aws/eks/aphex-pipeline/workflows`
- **Workflow Metadata**: CloudWatch Logs (optionally DynamoDB or S3)

### How do I set up alerts?

Configure CloudWatch alarms for:
- Workflow failures
- Deployment failures
- Resource exhaustion (EKS cluster CPU/memory)

Notifications are sent to configured channels (Slack, email) on workflow completion/failure.

## Testing

### What is property-based testing?

Property-based testing verifies universal properties that should hold across all inputs, rather than testing specific examples. AphexPipeline uses Hypothesis to test 25 correctness properties with 100+ examples each.

Example property: "For any configuration with N environments, the generated WorkflowTemplate should contain exactly N environment stages."

### How do I run tests?

**All tests**:
```bash
cd pipeline-scripts
pytest tests/ -v
```

**Specific property tests**:
```bash
pytest tests/test_validation_properties.py -v
```

**CDK infrastructure tests**:
```bash
cd pipeline-infra
npm test
```

### What do the property tests validate?

The 25 correctness properties validate:
- Configuration parsing and validation
- Git commit extraction
- Repository cloning
- Build command execution
- Artifact tagging and storage
- WorkflowTemplate generation
- Stack deployment ordering
- CDK synthesis completeness
- Cross-account role assumption
- Workflow metadata recording
- And more...

See [Design Document](../.kiro/specs/aphex-pipeline/design.md#correctness-properties) for complete list.

## Advanced Topics

### Can I add manual approval steps?

Yes, by customizing the WorkflowTemplate generator to add Argo Workflows suspend steps:

```yaml
- name: approval
  suspend: {}
```

Then approve via Argo UI before proceeding to next stage.

### How do I customize the pipeline?

- **Build commands**: Update `aphex-config.yaml`
- **Container images**: Build custom images with required tools
- **WorkflowTemplate**: Modify `workflow_template_generator.py`
- **Stage logic**: Modify Python scripts in `pipeline-scripts/`
- **Pipeline infrastructure**: Modify `pipeline-infra/lib/aphex-pipeline-stack.ts`

### Can I use this with GitLab or Bitbucket?

Currently, AphexPipeline is designed for GitHub webhooks. To support other Git providers:
1. Update Argo Events EventSource configuration
2. Update `github_event_parser.py` to parse different webhook formats
3. Configure webhook in your Git provider

### How do I handle secrets?

**Don't store secrets in configuration!** Use:
- AWS Secrets Manager
- AWS Systems Manager Parameter Store
- Kubernetes Secrets
- CDK context (for non-sensitive values)

Reference secrets in your CDK stacks, not in `aphex-config.yaml`.

### Can I run multiple pipelines in the same cluster?

Yes! Deploy multiple instances of the Pipeline CDK Stack with different names and configure separate WorkflowTemplates and EventSources for each pipeline.

### How do I upgrade Argo Workflows/Events?

1. Update Helm chart versions in Pipeline CDK Stack
2. Commit and push changes
3. Pipeline deployment stage will upgrade Argo components

Test upgrades in a non-production environment first.

### What's the performance impact of just-in-time synthesis?

Just-in-time synthesis adds latency (CDK synthesis time) at each stage, but ensures:
- Deployments always use latest code
- No stale cached templates
- Traditional CI/CD pipeline flow

Typical synthesis time: 30-60 seconds per stack.

### How do I optimize workflow duration?

- Use caching in build commands
- Parallelize independent environment deployments (requires WorkflowTemplate customization)
- Use faster EKS instance types
- Optimize CDK synthesis (use context to avoid lookups)

### Can I deploy non-CDK infrastructure?

AphexPipeline is designed for CDK deployments. For non-CDK infrastructure:
- Wrap in CDK custom resources
- Use CDK to call external tools (Terraform, CloudFormation templates)
- Customize stage scripts to call other deployment tools

## Troubleshooting Common Errors

### "Schema file not found"

Ensure `aphex-config.schema.json` is in the correct location relative to where you're running the validation script.

### "AWS credentials not found"

Verify:
- IRSA is configured correctly
- Service account has correct annotation
- IAM role has required permissions

### "Missing required CDK context values"

Add required context to `cdk.json`:
```json
{
  "context": {
    "vpc-id": "vpc-123456",
    "subnet-ids": ["subnet-1", "subnet-2"]
  }
}
```

### "CloudFormation stack already exists"

Stack names must be unique per region/account. Either:
- Delete the existing stack
- Use a different stack name
- Use CDK stack name prefix/suffix

### "Cross-account role assumption failed"

Verify:
- Role exists in target account
- Trust policy allows pipeline account to assume role
- Role has required permissions
- CDK bootstrap was run with `--trust` flag

## Getting Help

### Where can I find more documentation?

- [README.md](../../README.md) - Quick start
- [Architecture](architecture.md) - System design
- [Operations](operations.md) - Monitoring and troubleshooting
- [API Documentation](api.md) - Python APIs
- [Data Models](data-models.md) - Data structures
- [Example Use Cases](example-use-cases.md) - Real-world scenarios
- [Requirements](../.kiro/specs/aphex-pipeline/requirements.md) - Feature requirements
- [Design](../.kiro/specs/aphex-pipeline/design.md) - System design and properties

### How do I report issues?

Open an issue on GitHub with:
- Description of the problem
- Steps to reproduce
- Expected vs actual behavior
- Relevant logs (workflow logs, CloudFormation events)
- Configuration (sanitized, no secrets)

### How do I contribute?

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass
6. Submit a pull request

See [README.md](../../README.md#contributing) for details.

## Source References

- **Configuration**: `aphex-config.yaml`, `aphex-config.schema.json`
- **Pipeline Scripts**: `pipeline-scripts/*.py`
- **Pipeline Infrastructure**: `pipeline-infra/lib/aphex-pipeline-stack.ts`
- **Argo Configuration**: `.argo/*.yaml`
- **Tests**: `pipeline-scripts/tests/*.py`, `pipeline-infra/test/*.ts`
- **Documentation**: `.kiro/docs/*.md`
