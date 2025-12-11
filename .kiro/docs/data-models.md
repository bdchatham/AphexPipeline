# Data Models

This document describes the data structures used throughout AphexPipeline.

## Configuration Models

### AphexConfig

Complete AphexPipeline configuration parsed from `aphex-config.yaml`.

**Fields**:
- `version` (str): Configuration version (currently "1.0")
- `build` (BuildConfig): Build stage configuration
- `environments` (List[EnvironmentConfig]): List of deployment environments

**Source**: `pipeline-scripts/config_parser.py`

**Example**:
```python
AphexConfig(
    version="1.0",
    build=BuildConfig(commands=["npm install", "npm run build"]),
    environments=[
        EnvironmentConfig(
            name="dev",
            region="us-east-1",
            account="123456789012",
            stacks=[StackConfig(name="MyStack", path="lib/my-stack.ts")],
            tests=None
        )
    ]
)
```

### BuildConfig

Build stage configuration.

**Fields**:
- `commands` (List[str]): List of build commands to execute

**Source**: `pipeline-scripts/config_parser.py`

**Example**:
```python
BuildConfig(
    commands=[
        "npm install",
        "npm run build",
        "npm test"
    ]
)
```

### EnvironmentConfig

Configuration for a deployment environment.

**Fields**:
- `name` (str): Environment name (e.g., "dev", "staging", "prod")
- `region` (str): AWS region (e.g., "us-east-1")
- `account` (str): AWS account ID (12 digits)
- `stacks` (List[StackConfig]): List of CDK stacks to deploy
- `tests` (Optional[TestConfig]): Post-deployment test configuration

**Source**: `pipeline-scripts/config_parser.py`

**Example**:
```python
EnvironmentConfig(
    name="production",
    region="us-west-2",
    account="987654321098",
    stacks=[
        StackConfig(name="NetworkStack", path="lib/network-stack.ts"),
        StackConfig(name="AppStack", path="lib/app-stack.ts")
    ],
    tests=TestConfig(commands=["npm run integration-test"])
)
```

### StackConfig

Configuration for a CDK stack.

**Fields**:
- `name` (str): Stack name
- `path` (str): Path to stack definition file

**Source**: `pipeline-scripts/config_parser.py`

**Example**:
```python
StackConfig(
    name="MyAppStack",
    path="lib/my-app-stack.ts"
)
```

### TestConfig

Post-deployment test configuration.

**Fields**:
- `commands` (List[str]): List of test commands to execute

**Source**: `pipeline-scripts/config_parser.py`

**Example**:
```python
TestConfig(
    commands=[
        "npm run smoke-test",
        "npm run integration-test"
    ]
)
```

## Workflow Metadata Models

### WorkflowMetadata

Tracks workflow execution metadata for monitoring and auditing.

**Fields**:
- `workflow_id` (str): Unique workflow identifier
- `commit_sha` (str): Git commit SHA
- `branch` (str): Git branch name
- `triggered_at` (datetime): Workflow start timestamp
- `completed_at` (Optional[datetime]): Workflow completion timestamp
- `status` (str): Workflow status ("running", "succeeded", "failed")
- `stages` (List[StageMetadata]): List of stage metadata

**Source**: `pipeline-scripts/monitoring.py`

**Example**:
```python
WorkflowMetadata(
    workflow_id="workflow-abc123",
    commit_sha="a1b2c3d4e5f6",
    branch="main",
    triggered_at=datetime(2024, 1, 15, 10, 30, 0),
    completed_at=datetime(2024, 1, 15, 10, 45, 0),
    status="succeeded",
    stages=[
        StageMetadata(
            stage_name="build",
            started_at=datetime(2024, 1, 15, 10, 30, 0),
            completed_at=datetime(2024, 1, 15, 10, 35, 0),
            status="succeeded",
            error_message=None
        )
    ]
)
```

### StageMetadata

Tracks individual stage execution metadata.

**Fields**:
- `stage_name` (str): Name of the stage
- `started_at` (datetime): Stage start timestamp
- `completed_at` (Optional[datetime]): Stage completion timestamp
- `status` (str): Stage status ("running", "succeeded", "failed")
- `error_message` (Optional[str]): Error message if stage failed

**Source**: `pipeline-scripts/monitoring.py`

**Example**:
```python
StageMetadata(
    stage_name="deploy-production",
    started_at=datetime(2024, 1, 15, 10, 40, 0),
    completed_at=datetime(2024, 1, 15, 10, 45, 0),
    status="succeeded",
    error_message=None
)
```

## Artifact Models

### ArtifactMetadata

Tracks build artifacts for traceability.

**Fields**:
- `commit_sha` (str): Git commit SHA
- `timestamp` (datetime): Artifact creation timestamp
- `s3_path` (str): S3 path to artifact
- `artifact_type` (str): Type of artifact (e.g., "lambda-layer", "binary", "package")
- `size_bytes` (int): Artifact size in bytes
- `checksum` (str): Artifact checksum (SHA256)

**Source**: `pipeline-scripts/build_stage.py`

**Example**:
```python
ArtifactMetadata(
    commit_sha="a1b2c3d4e5f6",
    timestamp=datetime(2024, 1, 15, 10, 35, 0),
    s3_path="s3://aphex-artifacts/a1b2c3d4e5f6/build.zip",
    artifact_type="package",
    size_bytes=1048576,
    checksum="abc123def456..."
)
```

## Event Models

### GitHubEvent

Parsed GitHub webhook event.

**Fields**:
- `commit_sha` (str): Git commit SHA
- `branch` (str): Git branch name (e.g., "refs/heads/main")
- `repo_url` (str): Repository clone URL
- `author` (str): Commit author
- `message` (str): Commit message
- `timestamp` (datetime): Commit timestamp

**Source**: `pipeline-scripts/github_event_parser.py`

**Example**:
```python
GitHubEvent(
    commit_sha="a1b2c3d4e5f6",
    branch="refs/heads/main",
    repo_url="https://github.com/org/repo.git",
    author="developer@example.com",
    message="Add new feature",
    timestamp=datetime(2024, 1, 15, 10, 30, 0)
)
```

## Execution Result Models

### BuildResult

Result of build stage execution.

**Fields**:
- `success` (bool): Whether build succeeded
- `exit_code` (int): Exit code of build commands
- `stdout` (str): Standard output
- `stderr` (str): Standard error
- `duration` (float): Build duration in seconds
- `artifacts` (List[str]): List of artifact paths

**Source**: `pipeline-scripts/build_stage.py`

**Example**:
```python
BuildResult(
    success=True,
    exit_code=0,
    stdout="Build completed successfully",
    stderr="",
    duration=120.5,
    artifacts=["dist/bundle.js", "dist/styles.css"]
)
```

### TestExecutionResult

Result of test execution.

**Fields**:
- `success` (bool): Whether all tests passed
- `exit_code` (int): Exit code of test commands
- `stdout` (str): Standard output
- `stderr` (str): Standard error
- `duration` (float): Test duration in seconds
- `test_count` (int): Number of tests executed
- `passed_count` (int): Number of tests passed
- `failed_count` (int): Number of tests failed

**Source**: `pipeline-scripts/test_execution_stage.py`

**Example**:
```python
TestExecutionResult(
    success=True,
    exit_code=0,
    stdout="All tests passed",
    stderr="",
    duration=45.2,
    test_count=25,
    passed_count=25,
    failed_count=0
)
```

### DeploymentResult

Result of CDK stack deployment.

**Fields**:
- `success` (bool): Whether deployment succeeded
- `stack_name` (str): Name of the deployed stack
- `stack_outputs` (Dict[str, str]): CloudFormation stack outputs
- `duration` (float): Deployment duration in seconds
- `cloudformation_events` (List[Dict]): CloudFormation events

**Source**: `pipeline-scripts/environment_deployment_stage.py`

**Example**:
```python
DeploymentResult(
    success=True,
    stack_name="MyAppStack",
    stack_outputs={
        "ApiUrl": "https://api.example.com",
        "BucketName": "my-app-bucket"
    },
    duration=180.0,
    cloudformation_events=[...]
)
```

## Data Flow

### Configuration Flow

```
aphex-config.yaml
    ↓ (parse)
AphexConfig
    ↓ (validate)
JSON Schema Validation
    ↓ (generate)
WorkflowTemplate YAML
    ↓ (apply)
Argo Workflows
```

### Artifact Flow

```
Source Code
    ↓ (build)
Build Artifacts
    ↓ (tag)
ArtifactMetadata
    ↓ (upload)
S3 Bucket
    ↓ (download)
Environment Stage
    ↓ (deploy)
CloudFormation
```

### Metadata Flow

```
Workflow Execution
    ↓ (record)
WorkflowMetadata
    ↓ (store)
CloudWatch Logs
    ↓ (emit)
CloudWatch Metrics
    ↓ (send)
Notifications
```

### Event Flow

```
GitHub Push
    ↓ (webhook)
Argo Events EventSource
    ↓ (parse)
GitHubEvent
    ↓ (filter)
Argo Events Sensor
    ↓ (trigger)
Argo Workflow Instance
```

## Data Validation

### Configuration Validation

Configuration is validated against `aphex-config.schema.json`:

**Required Fields**:
- `version`: Must be "1.0"
- `build.commands`: Non-empty array of strings
- `environments`: Non-empty array of environment objects
- `environments[].name`: Non-empty string
- `environments[].region`: Valid AWS region
- `environments[].account`: 12-digit string
- `environments[].stacks`: Non-empty array of stack objects
- `environments[].stacks[].name`: Non-empty string
- `environments[].stacks[].path`: Non-empty string

**Optional Fields**:
- `environments[].tests.commands`: Array of strings

### Credential Validation

AWS credentials are validated before deployment:
- Credentials must be available via IRSA or environment variables
- Account ID must match configured environment account
- Credentials must have required permissions

### Context Validation

CDK context is validated if requirements are specified:
- Required context keys must be present in `cdk.json`
- Context values must be non-empty

### Tool Validation

Build tools are validated before execution:
- Required tools must be available in PATH
- Tools must respond to `--version` or `-v` flag

## Data Storage

### CloudWatch Logs

Workflow logs are stored in CloudWatch Logs:
- **Log Group**: `/aws/eks/aphex-pipeline/workflows`
- **Retention**: 30 days (configurable)
- **Format**: JSON with timestamp, workflow ID, stage, message

### CloudWatch Metrics

Metrics are emitted to CloudWatch:
- **Namespace**: `AphexPipeline`
- **Dimensions**: Environment, Stack, Status
- **Metrics**: DeploymentCount, DeploymentDuration, WorkflowDuration

### S3 Artifacts

Build artifacts are stored in S3:
- **Bucket**: Created by Pipeline CDK Stack
- **Path**: `s3://{bucket}/{commit-sha}/`
- **Versioning**: Enabled
- **Encryption**: AES-256
- **Lifecycle**: 90-day expiration (configurable)

### Workflow Metadata

Workflow metadata can be stored in:
- **CloudWatch Logs**: JSON log entries
- **DynamoDB**: Optional table for queryable metadata
- **S3**: Optional JSON files for long-term storage

## Schema Definitions

### Configuration Schema

See `aphex-config.schema.json` for the complete JSON schema definition.

### CloudFormation Outputs Schema

Stack outputs follow CloudFormation format:
```json
{
  "OutputKey": "string",
  "OutputValue": "string",
  "Description": "string",
  "ExportName": "string"
}
```

## Source References

- **Configuration Models**: `pipeline-scripts/config_parser.py`
- **Workflow Metadata**: `pipeline-scripts/monitoring.py`
- **Artifact Models**: `pipeline-scripts/build_stage.py`
- **Event Models**: `pipeline-scripts/github_event_parser.py`
- **Result Models**: `pipeline-scripts/*_stage.py`
- **Schema**: `aphex-config.schema.json`
- **Tests**: `pipeline-scripts/tests/*.py`
