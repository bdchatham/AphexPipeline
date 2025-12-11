# Argo Events Configuration

This directory contains the Argo Events configuration files for AphexPipeline.

## Files

### logging-config.yaml

Configures Argo Workflows logging and log retention settings.

**Features:**
- Archives all workflow logs to S3 for long-term retention
- Configures log retention policies (30 days for completed, 90 days for failed)
- Enables workflow metrics for monitoring
- Sets up RBAC for workflow pods to access S3
- Configures pod garbage collection to retain pods for 24 hours after completion

**Before deploying:**
1. Ensure the `ARTIFACT_BUCKET` environment variable is set to your S3 bucket name
2. Ensure the `WORKFLOW_EXECUTION_ROLE_ARN` is set to the IAM role ARN created by the Pipeline CDK Stack

**Deploy the logging configuration:**
```bash
# Substitute environment variables
export ARTIFACT_BUCKET=$(aws cloudformation describe-stacks \
  --stack-name AphexPipelineStack \
  --query 'Stacks[0].Outputs[?OutputKey==`ArtifactBucketName`].OutputValue' \
  --output text)

export WORKFLOW_EXECUTION_ROLE_ARN=$(aws cloudformation describe-stacks \
  --stack-name AphexPipelineStack \
  --query 'Stacks[0].Outputs[?OutputKey==`WorkflowExecutionRoleArn`].OutputValue' \
  --output text)

# Apply configuration with substitutions
envsubst < .argo/logging-config.yaml | kubectl apply -f -
```

**Verify configuration:**
```bash
kubectl get configmap workflow-controller-configmap -n argo -o yaml
kubectl get serviceaccount argo-workflow -n argo -o yaml
```

**Accessing logs:**
- View logs in Argo UI: Navigate to the workflow and click on any step
- View archived logs in S3: `s3://${ARTIFACT_BUCKET}/logs/`
- Query logs via AWS CLI:
  ```bash
  aws s3 ls s3://${ARTIFACT_BUCKET}/logs/ --recursive
  aws s3 cp s3://${ARTIFACT_BUCKET}/logs/<workflow-name>/<pod-name>/main.log -
  ```

### eventsource-github.yaml

Defines the GitHub EventSource that listens for webhook events from your GitHub repository.

**Before deploying:**
1. Update the `owner` and `names` fields with your GitHub organization and repository
2. Create a GitHub personal access token with `repo` scope
3. Create a Kubernetes secret with your GitHub token:
   ```bash
   kubectl create secret generic github-access \
     --from-literal=token=<your-github-token> \
     -n argo-events
   ```
4. (Optional but recommended) Create a webhook secret for validating GitHub signatures:
   ```bash
   kubectl create secret generic github-webhook-secret \
     --from-literal=secret=<your-webhook-secret> \
     -n argo-events
   ```

**Deploy the EventSource:**
```bash
kubectl apply -f .argo/eventsource-github.yaml
```

**Verify deployment:**
```bash
kubectl get eventsource -n argo-events
kubectl logs -n argo-events -l eventsource-name=github
```

### sensor-aphex-pipeline.yaml

Defines the Sensor that filters GitHub events and triggers Argo Workflows.

**Features:**
- Filters for pushes to the `main` branch only
- Extracts commit SHA, branch name, repository URL, and pusher information
- Creates Workflow instances from the `aphex-pipeline-template` WorkflowTemplate
- Passes GitHub event data as workflow parameters

**Deploy the Sensor:**
```bash
kubectl apply -f .argo/sensor-aphex-pipeline.yaml
```

**Verify deployment:**
```bash
kubectl get sensor -n argo-events
kubectl logs -n argo-events -l sensor-name=aphex-pipeline-sensor
```

## Workflow

1. Developer pushes code to the `main` branch
2. GitHub sends a webhook to the EventSource endpoint
3. EventSource receives the webhook and publishes it to the EventBus
4. Sensor filters the event (only main branch pushes)
5. Sensor creates a new Workflow instance with parameters from the GitHub event
6. Workflow executes the pipeline stages

## Troubleshooting

### Webhook not triggering workflows

1. Check GitHub webhook delivery status in repository settings
2. Verify EventSource is running:
   ```bash
   kubectl get pods -n argo-events
   kubectl logs -n argo-events -l eventsource-name=github
   ```
3. Verify Sensor is running:
   ```bash
   kubectl get pods -n argo-events
   kubectl logs -n argo-events -l sensor-name=aphex-pipeline-sensor
   ```
4. Check if the WorkflowTemplate exists:
   ```bash
   kubectl get workflowtemplate -n argo aphex-pipeline-template
   ```

### Events not being filtered correctly

Check the Sensor logs to see which events are being received and filtered:
```bash
kubectl logs -n argo-events -l sensor-name=aphex-pipeline-sensor -f
```

### Workflow parameters not being passed correctly

Inspect a created Workflow to verify parameters:
```bash
kubectl get workflow -n argo
kubectl describe workflow -n argo <workflow-name>
```

## Monitoring and Logging

### Workflow Logs

All workflow stage outputs are automatically logged to:
1. **Argo UI**: Real-time logs visible in the workflow UI
2. **S3 Archive**: Long-term storage in `s3://${ARTIFACT_BUCKET}/logs/`
3. **CloudWatch**: Metrics for workflow success/failure and duration

### Log Retention

- **Completed workflows**: Logs retained for 30 days
- **Failed workflows**: Logs retained for 90 days
- **Pods**: Retained for 24 hours after workflow completion for debugging

### Viewing Logs

**Via Argo UI:**
```bash
# Get Argo UI URL
kubectl get ingress -n argo

# Or port-forward
kubectl port-forward -n argo svc/argo-server 2746:2746
# Access at https://localhost:2746
```

**Via kubectl:**
```bash
# List workflows
kubectl get workflows -n argo

# View workflow logs
kubectl logs -n argo -l workflows.argoproj.io/workflow=<workflow-name>

# View specific pod logs
kubectl logs -n argo <pod-name>
```

**Via S3:**
```bash
# List archived logs
aws s3 ls s3://${ARTIFACT_BUCKET}/logs/ --recursive

# Download specific log
aws s3 cp s3://${ARTIFACT_BUCKET}/logs/<workflow-name>/<pod-name>/main.log -
```

### Workflow Metadata

Workflow metadata (ID, commit SHA, timestamps, status) is recorded to S3 at:
```
s3://${ARTIFACT_BUCKET}/metadata/workflows/<workflow-id>.json
```

This metadata includes:
- Workflow ID and status
- Git commit SHA and branch
- Trigger and completion timestamps
- Stage execution details
- Error messages for failed stages

### CloudWatch Metrics

The following metrics are emitted to CloudWatch namespace `AphexPipeline`:

**Workflow Metrics:**
- `WorkflowCount`: Number of workflows (dimensions: Status)
- `WorkflowDuration`: Workflow execution time in seconds

**Deployment Metrics:**
- `DeploymentCount`: Number of deployments (dimensions: StackName, Status, Environment)
- `DeploymentDuration`: Deployment time in seconds (dimensions: StackName, Environment)

**Viewing metrics:**
```bash
# List available metrics
aws cloudwatch list-metrics --namespace AphexPipeline

# Get workflow success rate
aws cloudwatch get-metric-statistics \
  --namespace AphexPipeline \
  --metric-name WorkflowCount \
  --dimensions Name=Status,Value=succeeded \
  --start-time $(date -u -d '1 day ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 3600 \
  --statistics Sum
```

### Notifications

Workflow completion and failure notifications can be sent via SNS. Configure SNS topics in your environment and use the `NotificationDelivery` class from `pipeline-scripts/monitoring.py`.

Example notification includes:
- Workflow ID and status
- Git commit SHA
- Link to Argo UI for the workflow
- Error message (for failures)

## Testing

The git commit extraction logic is tested with property-based tests in `pipeline-scripts/tests/test_github_event_properties.py`.

The monitoring and logging functionality is tested with property-based tests in `pipeline-scripts/tests/test_monitoring_properties.py`.

Run the tests:
```bash
cd pipeline-scripts
python -m pytest tests/test_github_event_properties.py -v
python -m pytest tests/test_monitoring_properties.py -v
```

The tests verify:
- Commit SHA and branch name are correctly extracted from webhook payloads
- Invalid payloads are properly rejected
- Main branch filtering works correctly
- Ref format handling (with/without "refs/heads/" prefix)
- Commit SHA format validation
- Workflow metadata recording and retrieval (round-trip property)
- CloudWatch metrics emission for deployments and workflows
- Notification delivery to single and multiple channels
