# API Documentation

This document describes the Python APIs provided by AphexPipeline's pipeline scripts.

## Configuration Parser API

### Module: `config_parser`

#### `parse_config(config_path: str, schema_path: str = "aphex-config.schema.json") -> AphexConfig`

Parses and validates an AphexPipeline configuration file.

**Parameters**:
- `config_path` (str): Path to the aphex-config.yaml file
- `schema_path` (str, optional): Path to the JSON schema file. Defaults to "aphex-config.schema.json"

**Returns**:
- `AphexConfig`: Parsed and validated configuration object

**Raises**:
- `FileNotFoundError`: If config or schema file doesn't exist
- `ValidationError`: If config doesn't match schema
- `yaml.YAMLError`: If YAML is malformed

**Example**:
```python
from config_parser import parse_config

config = parse_config('aphex-config.yaml')
print(f"Version: {config.version}")
print(f"Environments: {len(config.environments)}")
for env in config.environments:
    print(f"  - {env.name}: {env.region} ({env.account})")
```

#### `class ConfigParser`

Configuration parser class for more control over parsing.

**Constructor**:
```python
ConfigParser(schema_path: str = "aphex-config.schema.json")
```

**Methods**:

##### `parse(config_path: str) -> AphexConfig`

Parse and validate a configuration file.

**Example**:
```python
from config_parser import ConfigParser

parser = ConfigParser(schema_path='custom-schema.json')
config = parser.parse('aphex-config.yaml')
```

## Validation API

### Module: `validation`

#### `validate_aws_credentials(account_id: Optional[str] = None, region: Optional[str] = None) -> bool`

Validates that AWS credentials are available and valid.

**Parameters**:
- `account_id` (str, optional): AWS account ID to validate against
- `region` (str, optional): AWS region to set

**Returns**:
- `bool`: True if credentials are valid

**Raises**:
- `ValidationError`: If credentials are invalid or unavailable

**Example**:
```python
from validation import validate_aws_credentials

try:
    validate_aws_credentials(account_id='123456789012', region='us-east-1')
    print("Credentials valid!")
except ValidationError as e:
    print(f"Validation failed: {e}")
```

#### `validate_cdk_context(context_requirements: List[str], cdk_json_path: str = "cdk.json") -> bool`

Validates that required CDK context values are present.

**Parameters**:
- `context_requirements` (List[str]): List of required context keys
- `cdk_json_path` (str, optional): Path to cdk.json file. Defaults to "cdk.json"

**Returns**:
- `bool`: True if all required context values are present

**Raises**:
- `ValidationError`: If required context values are missing

**Example**:
```python
from validation import validate_cdk_context

try:
    validate_cdk_context(['vpc-id', 'subnet-ids'], 'cdk.json')
    print("CDK context valid!")
except ValidationError as e:
    print(f"Missing context: {e}")
```

#### `validate_build_tools(required_tools: List[str]) -> bool`

Validates that required build tools are available in the container.

**Parameters**:
- `required_tools` (List[str]): List of required tool names (e.g., ['npm', 'python3', 'aws'])

**Returns**:
- `bool`: True if all required tools are available

**Raises**:
- `ValidationError`: If required tools are missing

**Example**:
```python
from validation import validate_build_tools

try:
    validate_build_tools(['npm', 'node', 'python3'])
    print("All tools available!")
except ValidationError as e:
    print(f"Missing tools: {e}")
```

#### `validate_all(config_path: str, schema_path: str = "aphex-config.schema.json", cdk_json_path: str = "cdk.json", context_requirements: Optional[List[str]] = None) -> Tuple[bool, List[str]]`

Performs all validation checks before workflow execution.

**Parameters**:
- `config_path` (str): Path to aphex-config.yaml
- `schema_path` (str, optional): Path to JSON schema
- `cdk_json_path` (str, optional): Path to cdk.json
- `context_requirements` (List[str], optional): Required CDK context keys

**Returns**:
- `Tuple[bool, List[str]]`: (success, list of error messages)

**Example**:
```python
from validation import validate_all

success, errors = validate_all(
    'aphex-config.yaml',
    context_requirements=['vpc-id']
)

if success:
    print("All validations passed!")
else:
    print("Validation errors:")
    for error in errors:
        print(f"  - {error}")
```

## Monitoring API

### Module: `monitoring`

#### `record_workflow_metadata(workflow_id: str, commit_sha: str, branch: str) -> WorkflowMetadata`

Records metadata for a workflow execution.

**Parameters**:
- `workflow_id` (str): Unique workflow identifier
- `commit_sha` (str): Git commit SHA
- `branch` (str): Git branch name

**Returns**:
- `WorkflowMetadata`: Created metadata object

**Example**:
```python
from monitoring import record_workflow_metadata

metadata = record_workflow_metadata(
    workflow_id='workflow-abc123',
    commit_sha='a1b2c3d4',
    branch='main'
)
print(f"Workflow {metadata.workflow_id} started at {metadata.triggered_at}")
```

#### `update_workflow_status(workflow_id: str, status: str) -> None`

Updates the status of a workflow.

**Parameters**:
- `workflow_id` (str): Workflow identifier
- `status` (str): New status ('running', 'succeeded', 'failed')

**Example**:
```python
from monitoring import update_workflow_status

update_workflow_status('workflow-abc123', 'succeeded')
```

#### `add_stage_metadata(workflow_id: str, stage_name: str, status: str, error_message: Optional[str] = None) -> None`

Adds metadata for a workflow stage.

**Parameters**:
- `workflow_id` (str): Workflow identifier
- `stage_name` (str): Name of the stage
- `status` (str): Stage status
- `error_message` (str, optional): Error message if stage failed

**Example**:
```python
from monitoring import add_stage_metadata

add_stage_metadata(
    workflow_id='workflow-abc123',
    stage_name='build',
    status='succeeded'
)
```

#### `emit_deployment_metric(stack_name: str, environment: str, status: str, duration: float) -> None`

Emits CloudWatch metrics for a deployment.

**Parameters**:
- `stack_name` (str): Name of the deployed stack
- `environment` (str): Environment name
- `status` (str): Deployment status ('success' or 'failure')
- `duration` (float): Deployment duration in seconds

**Example**:
```python
from monitoring import emit_deployment_metric

emit_deployment_metric(
    stack_name='MyAppStack',
    environment='production',
    status='success',
    duration=120.5
)
```

#### `send_notification(workflow_id: str, status: str, message: str, channels: List[str]) -> None`

Sends notifications about workflow status.

**Parameters**:
- `workflow_id` (str): Workflow identifier
- `status` (str): Workflow status
- `message` (str): Notification message
- `channels` (List[str]): List of notification channels ('slack', 'email')

**Example**:
```python
from monitoring import send_notification

send_notification(
    workflow_id='workflow-abc123',
    status='failed',
    message='Build stage failed: npm test returned exit code 1',
    channels=['slack', 'email']
)
```

## Build Stage API

### Module: `build_stage`

#### `class BuildStage`

Handles build stage execution.

**Methods**:

##### `clone_repository(repo_url: str, commit_sha: str, workspace: str) -> None`

Clones repository at specific commit.

**Parameters**:
- `repo_url` (str): Git repository URL
- `commit_sha` (str): Commit SHA to checkout
- `workspace` (str): Workspace directory path

##### `execute_build_commands(commands: List[str], workspace: str) -> BuildResult`

Executes build commands.

**Parameters**:
- `commands` (List[str]): List of build commands
- `workspace` (str): Workspace directory path

**Returns**:
- `BuildResult`: Result object with success status and output

##### `tag_artifacts(artifact_path: str, commit_sha: str) -> ArtifactMetadata`

Tags artifacts with commit SHA and timestamp.

**Parameters**:
- `artifact_path` (str): Path to artifacts
- `commit_sha` (str): Git commit SHA

**Returns**:
- `ArtifactMetadata`: Metadata object with tags

##### `upload_to_s3(artifact_path: str, bucket: str, key: str) -> str`

Uploads artifacts to S3.

**Parameters**:
- `artifact_path` (str): Local path to artifacts
- `bucket` (str): S3 bucket name
- `key` (str): S3 object key

**Returns**:
- `str`: S3 URI of uploaded artifacts

## Environment Deployment API

### Module: `environment_deployment_stage`

#### `class EnvironmentDeploymentStage`

Handles environment deployment stage execution.

**Methods**:

##### `synthesize_stacks(stacks: List[StackConfig], workspace: str) -> List[str]`

Synthesizes CDK stacks just-in-time.

**Parameters**:
- `stacks` (List[StackConfig]): List of stack configurations
- `workspace` (str): Workspace directory path

**Returns**:
- `List[str]`: List of synthesized stack names

##### `deploy_stack(stack_name: str, region: str, account: str) -> Dict[str, Any]`

Deploys a CDK stack.

**Parameters**:
- `stack_name` (str): Name of the stack
- `region` (str): AWS region
- `account` (str): AWS account ID

**Returns**:
- `Dict[str, Any]`: Stack outputs

##### `assume_cross_account_role(account_id: str, region: str, role_name: str) -> Dict[str, str]`

Assumes cross-account IAM role.

**Parameters**:
- `account_id` (str): Target AWS account ID
- `region` (str): AWS region
- `role_name` (str): IAM role name

**Returns**:
- `Dict[str, str]`: Temporary credentials

## Test Execution API

### Module: `test_execution_stage`

#### `class TestExecutionStage`

Handles test execution stage.

**Methods**:

##### `execute_tests(commands: List[str], workspace: str) -> TestExecutionResult`

Executes test commands.

**Parameters**:
- `commands` (List[str]): List of test commands
- `workspace` (str): Workspace directory path

**Returns**:
- `TestExecutionResult`: Result object with pass/fail status and logs

## GitHub Event Parser API

### Module: `github_event_parser`

#### `parse_github_event(event_payload: Dict[str, Any]) -> GitHubEvent`

Parses GitHub webhook event payload.

**Parameters**:
- `event_payload` (Dict[str, Any]): GitHub webhook payload

**Returns**:
- `GitHubEvent`: Parsed event object with commit SHA, branch, etc.

**Example**:
```python
from github_event_parser import parse_github_event

event = parse_github_event(webhook_payload)
print(f"Commit: {event.commit_sha}")
print(f"Branch: {event.branch}")
print(f"Repo: {event.repo_url}")
```

## Error Handling

All APIs use custom exception classes:

### `ValidationError`

Raised when validation fails.

**Attributes**:
- `message` (str): Error message describing the validation failure

### `BuildError`

Raised when build stage fails.

**Attributes**:
- `message` (str): Error message
- `exit_code` (int): Command exit code
- `stdout` (str): Standard output
- `stderr` (str): Standard error

### `DeploymentError`

Raised when deployment fails.

**Attributes**:
- `message` (str): Error message
- `stack_name` (str): Name of the failed stack
- `cloudformation_events` (List[Dict]): CloudFormation error events

## CLI Tools

### Validation Stage CLI

```bash
python pipeline-scripts/validation_stage.py \
  --config aphex-config.yaml \
  --schema aphex-config.schema.json \
  --cdk-json cdk.json \
  --context-requirements vpc-id subnet-ids \
  --skip-aws-validation \
  --skip-cdk-validation \
  --skip-tool-validation
```

See [Validation Usage](../pipeline-scripts/VALIDATION_USAGE.md) for details.

## Source References

- **Configuration Parser**: `pipeline-scripts/config_parser.py`
- **Validation**: `pipeline-scripts/validation.py`
- **Monitoring**: `pipeline-scripts/monitoring.py`
- **Build Stage**: `pipeline-scripts/build_stage.py`
- **Environment Deployment**: `pipeline-scripts/environment_deployment_stage.py`
- **Test Execution**: `pipeline-scripts/test_execution_stage.py`
- **GitHub Event Parser**: `pipeline-scripts/github_event_parser.py`
- **Tests**: `pipeline-scripts/tests/*.py`
