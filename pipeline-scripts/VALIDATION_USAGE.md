# Validation Stage Usage

The validation stage performs comprehensive checks before workflow execution to ensure all requirements are met.

## Overview

The validation stage checks:
1. **Configuration Schema** - Validates aphex-config.yaml against JSON schema
2. **AWS Credentials** - Verifies credentials are available for each environment
3. **CDK Context** - Ensures required CDK context values are present
4. **Build Tools** - Confirms required build tools are available in the container

## Usage

### Basic Usage

```bash
python pipeline-scripts/validation_stage.py --config aphex-config.yaml
```

### With Custom Paths

```bash
python pipeline-scripts/validation_stage.py \
  --config path/to/aphex-config.yaml \
  --schema path/to/aphex-config.schema.json \
  --cdk-json path/to/cdk.json
```

### With CDK Context Requirements

```bash
python pipeline-scripts/validation_stage.py \
  --config aphex-config.yaml \
  --context-requirements vpc-id subnet-ids availability-zones
```

### Skip Specific Validations

For local testing or debugging, you can skip specific validation steps:

```bash
# Skip AWS credential validation
python pipeline-scripts/validation_stage.py \
  --config aphex-config.yaml \
  --skip-aws-validation

# Skip CDK context validation
python pipeline-scripts/validation_stage.py \
  --config aphex-config.yaml \
  --skip-cdk-validation

# Skip build tool validation
python pipeline-scripts/validation_stage.py \
  --config aphex-config.yaml \
  --skip-tool-validation

# Skip all validations except config schema
python pipeline-scripts/validation_stage.py \
  --config aphex-config.yaml \
  --skip-aws-validation \
  --skip-cdk-validation \
  --skip-tool-validation
```

## Integration with Argo Workflows

Add the validation stage as the first step in your WorkflowTemplate:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: WorkflowTemplate
metadata:
  name: aphex-pipeline-template
spec:
  entrypoint: main
  templates:
    - name: main
      steps:
        # Validation stage - runs first
        - - name: validate
            template: validation-stage
        
        # Build stage - only runs if validation passes
        - - name: build
            template: build-stage
        
        # ... other stages ...
    
    - name: validation-stage
      container:
        image: aphex-pipeline/deployer:latest
        command: ["/bin/bash"]
        args:
          - -c
          - |
            cd /workspace
            python pipeline-scripts/validation_stage.py \
              --config aphex-config.yaml \
              --context-requirements vpc-id subnet-ids
```

## Exit Codes

- **0**: All validations passed
- **1**: One or more validations failed

## Output Format

The validation stage provides clear, formatted output:

```
================================================================================
AphexPipeline Validation Stage
================================================================================

1. Validating configuration schema...
   ✓ Configuration is valid
   - Version: 1.0
   - Build commands: 3
   - Environments: 3
     - dev: us-east-1 (123456789012), 1 stacks
     - staging: us-west-2 (123456789012), 1 stacks
     - prod: us-east-1 (987654321098), 1 stacks

2. Validating AWS credentials...
   ✓ Credentials valid for dev (123456789012)
   ✓ Credentials valid for staging (123456789012)
   ✓ Credentials valid for prod (987654321098)

3. Validating CDK context...
   ✓ All required CDK context values present
     - vpc-id
     - subnet-ids

4. Validating build tools...
   ✓ All required build tools available
     - npm
     - python3

================================================================================
Validation Summary
================================================================================
✓ All validations PASSED

The workflow is ready to execute.
================================================================================
```

## Error Handling

If validation fails, the output clearly indicates which checks failed:

```
================================================================================
Validation Summary
================================================================================
✗ Validation FAILED with 2 error(s):

1. AWS credential validation failed for prod: AWS account mismatch: expected 987654321098, got 123456789012
2. CDK context validation failed: Missing required CDK context values: vpc-id

Please fix the errors above before running the workflow.
================================================================================
```

## Property-Based Tests

The validation logic is thoroughly tested with property-based tests:

- **Property 20**: AWS credential validation
- **Property 21**: CDK context validation
- **Property 22**: Build tool validation

Run tests with:

```bash
cd pipeline-scripts
python -m pytest tests/test_validation_properties.py -v
python -m pytest tests/test_validation_stage.py -v
```
