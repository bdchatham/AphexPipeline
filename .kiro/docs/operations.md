# Operations Guide

This guide covers operational aspects of AphexPipeline including monitoring, troubleshooting, and maintenance.

## Monitoring

### Key Metrics to Monitor

#### Workflow Metrics
- **Workflow Success Rate**: Percentage of workflows that complete successfully
- **Workflow Duration**: Time from workflow start to completion
- **Workflow Failure Rate**: Percentage of workflows that fail
- **Queue Depth**: Number of workflows waiting to execute

#### Stage Metrics
- **Build Stage Duration**: Time spent in build stage
- **Pipeline Deployment Duration**: Time spent updating pipeline infrastructure
- **Environment Deployment Duration**: Time spent deploying to each environment
- **Test Execution Duration**: Time spent running tests

#### Resource Metrics
- **EKS Cluster CPU/Memory**: Resource utilization of the cluster
- **Pod Count**: Number of active workflow pods
- **S3 Storage Usage**: Size of artifact storage
- **CloudFormation Stack Status**: Health of deployed stacks

### CloudWatch Dashboards

AphexPipeline emits metrics to CloudWatch. Create a dashboard with:

```
- Workflow success/failure count (last 24h)
- Average workflow duration (last 7 days)
- Stage duration breakdown (stacked bar chart)
- EKS cluster resource utilization
- S3 artifact storage growth
```

### Monitoring Webhook Service

#### Check Service Status

```bash
# Get service details
kubectl get svc -n argo-events <eventsource-name>-eventsource-svc

# For LoadBalancer type, get external DNS
kubectl get svc -n argo-events <eventsource-name>-eventsource-svc \
  -o jsonpath='{.status.loadBalancer.ingress[0].hostname}'

# Check service endpoints (should match EventSource pod)
kubectl get endpoints -n argo-events <eventsource-name>-eventsource-svc
```

#### Verify EventSource Pod

```bash
# Check EventSource pod is running
kubectl get pods -n argo-events -l eventsource-name=<eventsource-name>

# View EventSource logs
kubectl logs -n argo-events -l eventsource-name=<eventsource-name> -f
```

#### Test Webhook Endpoint

```bash
# Get webhook URL from stack outputs
WEBHOOK_URL=$(aws cloudformation describe-stacks \
  --stack-name MyPipeline \
  --query 'Stacks[0].Outputs[?OutputKey==`ArgoEventsWebhookUrl`].OutputValue' \
  --output text)

# Test endpoint (should return 405 Method Not Allowed for GET)
curl -v $WEBHOOK_URL
```

### Monitoring Workflow Execution

#### Via Argo Workflows UI

1. Access the Argo Workflows UI (URL from Pipeline CDK Stack outputs)
2. View list of all workflows
3. Click on a workflow to see:
   - Overall status
   - Stage-by-stage progress
   - Logs for each stage
   - Workflow parameters (commit SHA, branch, etc.)

#### Via CloudWatch Logs

Workflow logs are automatically sent to CloudWatch Logs:

```bash
# View logs for a specific workflow
aws logs tail /aws/eks/aphex-pipeline/workflows --follow

# Filter for errors
aws logs filter-pattern /aws/eks/aphex-pipeline/workflows --filter-pattern "ERROR"
```

#### Via Workflow Metadata

Query workflow metadata from the monitoring system:

```python
from monitoring import get_workflow_metadata

# Get metadata for a specific workflow
metadata = get_workflow_metadata("workflow-abc123")
print(f"Status: {metadata.status}")
print(f"Duration: {metadata.completed_at - metadata.triggered_at}")

# List recent workflows
recent = list_recent_workflows(limit=10)
for wf in recent:
    print(f"{wf.workflow_id}: {wf.status} ({wf.commit_sha})")
```

### Alerts and Notifications

Configure alerts for critical events:

#### Workflow Failures
- **Trigger**: Workflow fails
- **Action**: Send notification to configured channels (Slack, email)
- **Includes**: Workflow ID, commit SHA, error details, Argo UI link

#### Build Failures
- **Trigger**: Build stage fails
- **Action**: Notify development team
- **Includes**: Build logs, commit SHA, repository URL

#### Deployment Failures
- **Trigger**: CDK deployment fails
- **Action**: Notify operations team
- **Includes**: CloudFormation error events, stack name, environment

#### Resource Exhaustion
- **Trigger**: EKS cluster CPU/memory > 80%
- **Action**: Alert operations team
- **Includes**: Current utilization, pod count

## Troubleshooting

### Workflow Not Triggering

**Symptoms**: Push to main branch doesn't trigger a workflow

**Diagnosis**:
1. Check GitHub webhook delivery in repository settings
   - Go to Settings → Webhooks
   - Click on the webhook
   - View "Recent Deliveries"
   - Check for failed deliveries

2. Verify Argo Events EventSource is running:
   ```bash
   kubectl get pods -n argo-events
   kubectl logs -n argo-events -l eventsource-name=github
   ```

3. Verify Sensor is running:
   ```bash
   kubectl get sensors -n argo-events
   kubectl logs -n argo-events -l sensor-name=aphex-pipeline-sensor
   ```

**Solutions**:
- If webhook delivery fails: Check EventSource endpoint is accessible
- If EventSource pod is not running: Check pod logs for errors
- If Sensor is not creating workflows: Check Sensor filters match your branch

### Workflow Failing at Build Stage

**Symptoms**: Workflow fails during build stage

**Diagnosis**:
1. Check workflow logs in Argo UI
2. Look for build command errors
3. Verify build tools are available in container

**Common Causes**:
- **Missing dependencies**: Build commands reference tools not in container
  - Solution: Update builder container image to include required tools
  
- **Build command errors**: Syntax errors or failing tests
  - Solution: Fix build commands in aphex-config.yaml
  
- **S3 permissions**: Cannot upload artifacts to S3
  - Solution: Verify IAM role has s3:PutObject permission

**Solutions**:
```bash
# View build stage logs
kubectl logs -n argo <workflow-pod-name> -c build

# Test build commands locally
docker run -it aphex-pipeline/builder:latest /bin/bash
# Run your build commands manually
```

### Workflow Failing at Pipeline Deployment Stage

**Symptoms**: Workflow fails when deploying Pipeline CDK Stack

**Diagnosis**:
1. Check CDK synthesis logs in Argo UI
2. Look for CloudFormation errors
3. Verify IAM permissions

**Common Causes**:
- **CDK synthesis errors**: Invalid CDK code
  - Solution: Fix Pipeline CDK Stack code, test locally with `cdk synth`
  
- **CloudFormation deployment errors**: Resource conflicts or limits
  - Solution: Check CloudFormation console for detailed error messages
  
- **IAM permissions**: Insufficient permissions to deploy infrastructure
  - Solution: Verify workflow execution role has required permissions

**Solutions**:
```bash
# View pipeline deployment logs
kubectl logs -n argo <workflow-pod-name> -c pipeline-deployment

# Test CDK synthesis locally
cd pipeline-infra
cdk synth AphexPipelineStack

# Check CloudFormation events
aws cloudformation describe-stack-events \
  --stack-name AphexPipelineStack \
  --max-items 20
```

### Workflow Failing at Environment Stage

**Symptoms**: Workflow fails when deploying to an environment

**Diagnosis**:
1. Check CDK synthesis logs for Application CDK Stacks
2. Check CloudFormation events for deployment errors
3. Verify cross-account IAM roles (if deploying to different account)
4. Check CDK context values

**Common Causes**:
- **CDK synthesis errors**: Invalid Application CDK Stack code
  - Solution: Fix CDK code, test locally with `cdk synth`
  
- **CloudFormation errors**: Resource conflicts, limits, or dependencies
  - Solution: Check CloudFormation console for detailed errors
  
- **Cross-account role assumption fails**: Invalid role ARN or trust policy
  - Solution: Verify cross-account role exists and trust policy allows assumption
  
- **Missing CDK context**: Required context values not present
  - Solution: Add required context to cdk.json or pass via CLI

**Solutions**:
```bash
# View environment deployment logs
kubectl logs -n argo <workflow-pod-name> -c deploy-<env-name>

# Test CDK synthesis locally
cdk synth <StackName> --context key=value

# Check CloudFormation events
aws cloudformation describe-stack-events \
  --stack-name <StackName> \
  --region <region> \
  --max-items 20

# Test cross-account role assumption
aws sts assume-role \
  --role-arn arn:aws:iam::<account>:role/<role-name> \
  --role-session-name test
```

### Self-Modification Not Working

**Symptoms**: Changes to aphex-config.yaml don't appear in subsequent workflows

**Diagnosis**:
1. Verify aphex-config.yaml is valid
2. Check pipeline deployment stage logs for WorkflowTemplate generation
3. Verify kubectl apply succeeded
4. Check WorkflowTemplate in cluster

**Common Causes**:
- **Invalid configuration**: YAML syntax errors or schema validation failures
  - Solution: Validate configuration with validation stage
  
- **WorkflowTemplate generation fails**: Error in generator script
  - Solution: Check pipeline deployment logs for errors
  
- **kubectl apply fails**: Insufficient permissions or invalid YAML
  - Solution: Verify service account has permission to update WorkflowTemplates

**Solutions**:
```bash
# Validate configuration
python pipeline-scripts/validation_stage.py --config aphex-config.yaml

# Check current WorkflowTemplate
kubectl get workflowtemplate -n argo aphex-pipeline-template -o yaml

# Manually apply WorkflowTemplate
python pipeline-scripts/workflow_template_generator.py \
  --config aphex-config.yaml \
  --output /tmp/workflow-template.yaml
kubectl apply -f /tmp/workflow-template.yaml
```

### Test Failures

**Symptoms**: Workflow fails during test execution stage

**Diagnosis**:
1. Check test logs in Argo UI
2. Identify which test failed
3. Check if infrastructure is in expected state

**Common Causes**:
- **Test command errors**: Syntax errors or missing test dependencies
  - Solution: Fix test commands in aphex-config.yaml
  
- **Infrastructure not ready**: Tests run before resources are fully available
  - Solution: Add wait conditions or retry logic to tests
  
- **Test assertions fail**: Deployed infrastructure doesn't match expectations
  - Solution: Investigate infrastructure state, fix deployment or test expectations

**Solutions**:
```bash
# View test logs
kubectl logs -n argo <workflow-pod-name> -c test-<env-name>

# Run tests manually against deployed infrastructure
# (SSH into test container or run locally with appropriate credentials)
```

### Validation Failures

**Symptoms**: Workflow fails immediately at validation stage

**Diagnosis**:
1. Check validation stage output
2. Identify which validation failed
3. Fix the underlying issue

**Common Causes**:
- **Invalid configuration**: Schema validation fails
  - Solution: Fix aphex-config.yaml to match schema
  
- **AWS credentials unavailable**: Cannot authenticate to AWS
  - Solution: Verify IRSA is configured correctly
  
- **Missing CDK context**: Required context values not present
  - Solution: Add required context to cdk.json
  
- **Missing build tools**: Required tools not in container
  - Solution: Update container image to include tools

**Solutions**:
```bash
# Run validation locally
python pipeline-scripts/validation_stage.py \
  --config aphex-config.yaml \
  --skip-aws-validation  # For local testing

# Check IRSA configuration
kubectl describe serviceaccount -n argo workflow-executor
# Should show eks.amazonaws.com/role-arn annotation

# Verify IAM role
aws iam get-role --role-name <workflow-execution-role>
```

### Cluster Access Problems

**Symptoms**: Pipeline deployment fails with cluster access errors

**Diagnosis**:
1. Verify cluster exists and is accessible
2. Check kubectl configuration
3. Verify IAM permissions for cluster access

**Common Causes**:
- **Cluster not found**: Cluster name or export name is incorrect
  - Solution: Verify cluster name matches CloudFormation export or provided parameter
  
- **kubectl not configured**: Cannot access cluster
  - Solution: Configure kubectl with cluster credentials
  
- **IAM permissions**: Insufficient permissions to access cluster
  - Solution: Verify IAM role has eks:DescribeCluster permission

**Solutions**:
```bash
# Verify cluster exists
aws eks describe-cluster --name <cluster-name> --region <region>

# Configure kubectl
aws eks update-kubeconfig --name <cluster-name> --region <region>

# Test cluster access
kubectl cluster-info
kubectl get nodes

# Check CloudFormation exports
aws cloudformation list-exports | grep AphexCluster

# Verify specific export
aws cloudformation list-exports \
  --query "Exports[?Name=='AphexCluster-ClusterName'].Value" \
  --output text
```

### Cluster Prerequisites Not Met

**Symptoms**: Pipeline deployment fails because Argo components are not installed

**Diagnosis**:
1. Check if Argo Workflows is installed
2. Check if Argo Events is installed
3. Verify EventBus exists

**Common Causes**:
- **Argo Workflows not installed**: Workflow Controller not running
  - Solution: Install Argo Workflows using aphex-cluster package or Helm
  
- **Argo Events not installed**: Event Controller not running
  - Solution: Install Argo Events using aphex-cluster package or Helm
  
- **EventBus missing**: EventBus not deployed
  - Solution: Deploy EventBus using Argo Events

**Solutions**:
```bash
# Check Argo Workflows installation
kubectl get pods -n argo
kubectl get deployment -n argo workflow-controller

# Check Argo Events installation
kubectl get pods -n argo-events
kubectl get deployment -n argo-events eventsource-controller

# Check EventBus
kubectl get eventbus -n argo-events

# Install using aphex-cluster package
npm install @bdchatham/aphex-cluster
# Follow aphex-cluster documentation

# Or install manually with Helm
helm repo add argo https://argoproj.github.io/argo-helm
helm install argo-workflows argo/argo-workflows -n argo --create-namespace
helm install argo-events argo/argo-events -n argo-events --create-namespace
```

### Multi-Pipeline Interference

**Symptoms**: Multiple pipelines on the same cluster interfere with each other

**Diagnosis**:
1. Check for resource name conflicts
2. Verify each pipeline has unique names
3. Check for shared resources being modified

**Common Causes**:
- **Duplicate resource names**: Multiple pipelines using same WorkflowTemplate name
  - Solution: Ensure each pipeline has unique workflowTemplateName parameter
  
- **Shared service accounts**: Pipelines sharing the same service account
  - Solution: Each pipeline should have its own service account
  
- **S3 bucket conflicts**: Pipelines writing to same S3 bucket
  - Solution: Each pipeline should have its own S3 bucket

**Solutions**:
```bash
# List all WorkflowTemplates
kubectl get workflowtemplate -n argo

# List all EventSources
kubectl get eventsource -n argo-events

# List all Sensors
kubectl get sensor -n argo-events

# Check for duplicate names
kubectl get workflowtemplate -n argo -o json | \
  jq '.items[].metadata.name' | sort | uniq -d

# Verify pipeline-specific resources
kubectl get workflowtemplate -n argo <pipeline-name>-template
kubectl get eventsource -n argo-events <pipeline-name>-github
kubectl get sensor -n argo-events <pipeline-name>-sensor
```

**Best Practices for Multi-Pipeline Deployments**:
- Use unique pipeline names for each instance
- Set unique `workflowTemplateName`, `eventSourceName`, and `sensorName` parameters
- Use separate S3 buckets for each pipeline
- Consider using separate namespaces for additional isolation
- Monitor resource usage to ensure cluster has sufficient capacity

## Maintenance

### Regular Maintenance Tasks

#### Weekly
- **Review failed workflows**: Investigate and resolve any failures
- **Monitor resource usage**: Check EKS cluster capacity and S3 storage
- **Review CloudWatch metrics**: Look for trends or anomalies

#### Monthly
- **Clean up old artifacts**: Implement or verify S3 lifecycle policies
- **Review IAM policies**: Ensure least-privilege access
- **Update container images**: Pull latest security patches
- **Review and update documentation**: Keep operational docs current

#### Quarterly
- **Update Argo Workflows**: Check for new versions and upgrade
- **Update Argo Events**: Check for new versions and upgrade
- **Review EKS cluster version**: Plan upgrades to stay current
- **Audit cross-account roles**: Verify trust policies and permissions

### Updating AphexPipeline Components

#### Updating Pipeline CDK Stack

Changes to the Pipeline CDK Stack are deployed automatically via the pipeline deployment stage:

1. Make changes to `pipeline-infra/` code
2. Commit and push to main branch
3. Workflow triggers and deploys changes automatically

#### Updating Container Images

To update builder or deployer container images:

1. Update Dockerfile in `containers/` directory
2. Build and push new image:
   ```bash
   cd containers
   ./build.sh builder v1.2.0
   ./build.sh deployer v1.2.0
   ```
3. Update image tags in WorkflowTemplate generator
4. Commit and push changes

#### Updating WorkflowTemplate Structure

To change the workflow topology:

1. Update `pipeline-scripts/workflow_template_generator.py`
2. Test generation locally:
   ```bash
   python pipeline-scripts/workflow_template_generator.py \
     --config aphex-config.yaml \
     --output /tmp/test-template.yaml
   ```
3. Commit and push changes
4. Next workflow run will use updated generator

### Artifact Cleanup

Implement S3 lifecycle policies to automatically clean up old artifacts:

```python
# In Pipeline CDK Stack
artifact_bucket.add_lifecycle_rule(
    id="DeleteOldArtifacts",
    expiration=Duration.days(90),
    noncurrent_version_expiration=Duration.days(30)
)
```

Or manually clean up:

```bash
# List artifacts older than 90 days
aws s3 ls s3://aphex-pipeline-artifacts/ --recursive \
  | awk '$1 < "'$(date -d '90 days ago' +%Y-%m-%d)'" {print $4}'

# Delete old artifacts
aws s3 rm s3://aphex-pipeline-artifacts/<old-commit-sha>/ --recursive
```

### Backup and Recovery

#### Configuration Backup

Configuration is stored in Git, so it's automatically backed up. Ensure:
- Regular commits to version control
- Protected main branch
- Multiple repository maintainers

#### Workflow History

Workflow metadata is stored in CloudWatch Logs and optionally in DynamoDB/S3:
- CloudWatch Logs retention: 30 days (configurable)
- Metadata store: Indefinite retention (implement cleanup as needed)

#### Infrastructure State

CloudFormation manages infrastructure state:
- Stack templates are in Git
- CloudFormation maintains current state
- Use CloudFormation drift detection to verify state

### Scaling Considerations

#### Horizontal Scaling

EKS cluster autoscaling is configured in Pipeline CDK Stack:
- Node groups scale based on pod resource requests
- Configure min/max node counts based on expected load

#### Vertical Scaling

Adjust resource requests/limits in WorkflowTemplate:
- Build stage: CPU/memory for build tools
- Deployment stages: CPU/memory for CDK operations
- Test stages: CPU/memory for test execution

#### Concurrent Workflows

Argo Workflows queues workflows automatically:
- Configure workflow parallelism in WorkflowTemplate
- Monitor queue depth and adjust cluster capacity

### Security Maintenance

#### Rotate Credentials

- **GitHub webhook secret**: Rotate periodically in GitHub and EventSource
- **Cross-account role credentials**: Automatically rotated by AWS STS
- **Service account tokens**: Automatically rotated by Kubernetes

#### Update IAM Policies

Review and update IAM policies to maintain least-privilege access:

```bash
# Review current policy
aws iam get-role-policy \
  --role-name AphexPipelineWorkflowExecutionRole \
  --policy-name WorkflowExecutionPolicy

# Update policy (via CDK or AWS CLI)
```

#### Scan Container Images

Regularly scan container images for vulnerabilities:

```bash
# Using AWS ECR image scanning
aws ecr start-image-scan \
  --repository-name aphex-pipeline/builder \
  --image-id imageTag=latest

# View scan results
aws ecr describe-image-scan-findings \
  --repository-name aphex-pipeline/builder \
  --image-id imageTag=latest
```

## Performance Optimization

### Reduce Workflow Duration

- **Optimize build commands**: Use caching, parallel builds
- **Optimize CDK synthesis**: Use CDK context to avoid lookups
- **Parallelize environment deployments**: Deploy independent environments concurrently
- **Use faster instance types**: Upgrade EKS node instance types

### Reduce Costs

- **Use Spot instances**: Configure EKS node groups to use Spot instances
- **Implement artifact cleanup**: Reduce S3 storage costs
- **Optimize CloudWatch Logs retention**: Reduce log retention period
- **Right-size resources**: Adjust pod resource requests to actual usage

## Disaster Recovery

### Scenario: EKS Cluster Failure

**Recovery Steps**:
1. Deploy new Pipeline CDK Stack to new region/account
2. Configure GitHub webhook to point to new cluster
3. Trigger workflow to verify functionality

**RTO**: ~30 minutes (time to deploy new cluster)
**RPO**: 0 (configuration in Git, no data loss)

### Scenario: Workflow Execution Failure

**Recovery Steps**:
1. Investigate failure cause
2. Fix underlying issue (code, configuration, permissions)
3. Manually trigger workflow or wait for next commit

**RTO**: Varies based on issue
**RPO**: 0 (can re-run workflow for any commit)

### Scenario: Artifact Storage Loss

**Recovery Steps**:
1. Trigger workflow to rebuild artifacts from source
2. Artifacts are regenerated from Git commit

**RTO**: ~10 minutes (time to rebuild)
**RPO**: 0 (artifacts can be rebuilt from source)

## References

- [Argo Workflows Documentation](https://argoproj.github.io/argo-workflows/)
- [Argo Events Documentation](https://argoproj.github.io/argo-events/)
- [AWS CDK Documentation](https://docs.aws.amazon.com/cdk/)
- [EKS Best Practices](https://aws.github.io/aws-eks-best-practices/)
- [Validation Stage Usage](../pipeline-scripts/VALIDATION_USAGE.md)
