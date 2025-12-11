# Argo Events Configuration

This directory contains the Argo Events configuration files for AphexPipeline.

## Files

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

## Testing

The git commit extraction logic is tested with property-based tests in `pipeline-scripts/tests/test_github_event_properties.py`.

Run the tests:
```bash
cd pipeline-scripts
python -m pytest tests/test_github_event_properties.py -v
```

The tests verify:
- Commit SHA and branch name are correctly extracted from webhook payloads
- Invalid payloads are properly rejected
- Main branch filtering works correctly
- Ref format handling (with/without "refs/heads/" prefix)
- Commit SHA format validation
