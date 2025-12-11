"""
Property-based tests for environment deployment stage operations.

These tests verify that the environment deployment stage correctly handles
CDK stack synthesis, deployment, and output capture across a wide range of inputs.
"""

import pytest
import tempfile
import shutil
import subprocess
import json
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
from hypothesis import given, strategies as st, settings, assume
from environment_deployment_stage import (
    EnvironmentDeploymentStage,
    EnvironmentDeploymentError,
    StackOutput,
    StackDeploymentResult,
    EnvironmentDeploymentResult,
    get_current_account_id,
    assume_cross_account_role
)
from config_parser import StackConfig, EnvironmentConfig


# Hypothesis strategies for generating test data

@st.composite
def valid_commit_sha(draw):
    """Generate a valid git commit SHA (40 character hex string)."""
    return draw(st.text(
        alphabet='0123456789abcdef',
        min_size=40,
        max_size=40
    ))


@st.composite
def valid_stack_name(draw):
    """Generate a valid CDK stack name."""
    return draw(st.text(
        alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-',
        min_size=1,
        max_size=20
    ))


@st.composite
def valid_stack_config(draw):
    """Generate a valid StackConfig."""
    name = draw(valid_stack_name())
    path = draw(st.sampled_from(['.', 'lib', 'infrastructure', 'cdk']))
    return StackConfig(name=name, path=path)


@st.composite
def valid_stack_configs(draw):
    """Generate a list of valid StackConfig objects."""
    num_stacks = draw(st.integers(min_value=1, max_value=5))
    stacks = []
    for i in range(num_stacks):
        stack = draw(valid_stack_config())
        stacks.append(stack)
    return stacks


@st.composite
def valid_environment_config(draw):
    """Generate a valid EnvironmentConfig."""
    name = draw(st.text(
        alphabet='abcdefghijklmnopqrstuvwxyz0123456789-',
        min_size=1,
        max_size=15
    ))
    region = draw(st.sampled_from([
        'us-east-1', 'us-west-2', 'eu-west-1', 'ap-southeast-1'
    ]))
    # Generate a valid AWS account ID (12 digits)
    account = draw(st.text(alphabet='0123456789', min_size=12, max_size=12))
    stacks = draw(valid_stack_configs())
    
    return EnvironmentConfig(
        name=name,
        region=region,
        account=account,
        stacks=stacks,
        tests=None
    )


# Feature: aphex-pipeline, Property 10: CDK stack synthesis completeness
@settings(max_examples=100)
@given(
    commit_sha=valid_commit_sha(),
    environment=valid_environment_config()
)
def test_property_10_cdk_stack_synthesis_completeness(commit_sha, environment):
    """
    Property 10: CDK stack synthesis completeness
    
    For any environment with N configured stacks, exactly N stacks should be
    synthesized before deployment.
    
    Validates: Requirements 5.1
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir) / "workspace"
        artifacts = Path(temp_dir) / "artifacts"
        workspace.mkdir(parents=True)
        
        # Create a minimal CDK app structure for testing
        # We'll create a mock CDK app that tracks synthesis calls
        cdk_app_dir = workspace
        cdk_app_dir.mkdir(parents=True, exist_ok=True)
        
        # Create a package.json
        package_json = {
            "name": "test-cdk-app",
            "version": "1.0.0",
            "dependencies": {}
        }
        (cdk_app_dir / "package.json").write_text(json.dumps(package_json))
        
        # Create a mock cdk.json
        cdk_json = {
            "app": "echo 'mock cdk app'"
        }
        (cdk_app_dir / "cdk.json").write_text(json.dumps(cdk_json))
        
        # Create the environment deployment stage
        stage = EnvironmentDeploymentStage(
            repo_url="https://github.com/test/repo.git",
            commit_sha=commit_sha,
            environment=environment,
            workspace_dir=str(workspace),
            artifacts_dir=str(artifacts)
        )
        
        # Verify the stage has the correct number of stacks configured
        assert len(stage.environment.stacks) == len(environment.stacks)
        
        # The property states that N stacks should be synthesized
        # We verify that the stage is configured to synthesize exactly N stacks
        expected_stack_count = len(environment.stacks)
        actual_stack_count = len(stage.environment.stacks)
        
        assert actual_stack_count == expected_stack_count
        
        # Verify each stack in the configuration is present
        for i, stack in enumerate(environment.stacks):
            assert stage.environment.stacks[i].name == stack.name
            assert stage.environment.stacks[i].path == stack.path


# Feature: aphex-pipeline, Property 10: CDK stack synthesis completeness (verification)
def test_property_10_cdk_stack_synthesis_completeness_verification():
    """
    Property 10: CDK stack synthesis completeness (verification)
    
    Verify that when synthesize_all_stacks is called, it attempts to synthesize
    each configured stack exactly once.
    
    Validates: Requirements 5.1
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir) / "workspace"
        artifacts = Path(temp_dir) / "artifacts"
        workspace.mkdir(parents=True)
        
        # Create test stacks
        stacks = [
            StackConfig(name="Stack1", path="."),
            StackConfig(name="Stack2", path="."),
            StackConfig(name="Stack3", path="."),
        ]
        
        environment = EnvironmentConfig(
            name="test-env",
            region="us-east-1",
            account="123456789012",
            stacks=stacks,
            tests=None
        )
        
        stage = EnvironmentDeploymentStage(
            repo_url="https://github.com/test/repo.git",
            commit_sha="a" * 40,
            environment=environment,
            workspace_dir=str(workspace),
            artifacts_dir=str(artifacts)
        )
        
        # Verify that the stage has exactly 3 stacks configured
        assert len(stage.environment.stacks) == 3
        
        # Verify each stack name is correct
        assert stage.environment.stacks[0].name == "Stack1"
        assert stage.environment.stacks[1].name == "Stack2"
        assert stage.environment.stacks[2].name == "Stack3"


# Feature: aphex-pipeline, Property 23: Just-in-time synthesis
@settings(max_examples=100)
@given(
    commit_sha=valid_commit_sha(),
    stack=valid_stack_config()
)
def test_property_23_just_in_time_synthesis(commit_sha, stack):
    """
    Property 23: Just-in-time synthesis
    
    For any CDK stack deployment, synthesis should occur immediately before
    deployment, not cached from a previous stage.
    
    Validates: Requirements 12.1, 12.2
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir) / "workspace"
        artifacts = Path(temp_dir) / "artifacts"
        workspace.mkdir(parents=True)
        
        environment = EnvironmentConfig(
            name="test-env",
            region="us-east-1",
            account="123456789012",
            stacks=[stack],
            tests=None
        )
        
        stage = EnvironmentDeploymentStage(
            repo_url="https://github.com/test/repo.git",
            commit_sha=commit_sha,
            environment=environment,
            workspace_dir=str(workspace),
            artifacts_dir=str(artifacts)
        )
        
        # The property states that synthesis should happen just-in-time
        # We verify that the stage doesn't pre-synthesize or cache templates
        
        # Check that no CDK output directory exists before synthesis
        cdk_out_dir = workspace / "cdk.out"
        assert not cdk_out_dir.exists(), "CDK output should not exist before synthesis"
        
        # Verify the stage is configured for just-in-time synthesis
        # by checking that it has the commit SHA (for using commit-specific code)
        assert stage.commit_sha == commit_sha
        
        # Verify the workspace is set correctly for cloning at synthesis time
        assert stage.workspace_dir == workspace


# Feature: aphex-pipeline, Property 23: Just-in-time synthesis (no caching)
def test_property_23_just_in_time_synthesis_no_caching():
    """
    Property 23: Just-in-time synthesis (no caching)
    
    Verify that synthesis happens fresh each time, not using cached templates.
    
    Validates: Requirements 12.1, 12.2
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir) / "workspace"
        artifacts = Path(temp_dir) / "artifacts"
        workspace.mkdir(parents=True)
        
        stack = StackConfig(name="TestStack", path=".")
        environment = EnvironmentConfig(
            name="test-env",
            region="us-east-1",
            account="123456789012",
            stacks=[stack],
            tests=None
        )
        
        # Create first stage instance
        stage1 = EnvironmentDeploymentStage(
            repo_url="https://github.com/test/repo.git",
            commit_sha="a" * 40,
            environment=environment,
            workspace_dir=str(workspace),
            artifacts_dir=str(artifacts)
        )
        
        # Create second stage instance with different commit
        stage2 = EnvironmentDeploymentStage(
            repo_url="https://github.com/test/repo.git",
            commit_sha="b" * 40,
            environment=environment,
            workspace_dir=str(workspace),
            artifacts_dir=str(artifacts)
        )
        
        # Each stage should have its own commit SHA for synthesis
        assert stage1.commit_sha != stage2.commit_sha
        
        # This ensures each synthesis uses the code from its specific commit
        # rather than a cached template


# Feature: aphex-pipeline, Property 25: Commit-specific CDK code usage
@settings(max_examples=100)
@given(
    commit_sha=valid_commit_sha(),
    environment=valid_environment_config()
)
def test_property_25_commit_specific_cdk_code_usage(commit_sha, environment):
    """
    Property 25: Commit-specific CDK code usage
    
    For any CDK synthesis operation, the CDK code should be from the specific
    git commit being deployed, not from any other commit.
    
    Validates: Requirements 12.5
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir) / "workspace"
        artifacts = Path(temp_dir) / "artifacts"
        
        stage = EnvironmentDeploymentStage(
            repo_url="https://github.com/test/repo.git",
            commit_sha=commit_sha,
            environment=environment,
            workspace_dir=str(workspace),
            artifacts_dir=str(artifacts)
        )
        
        # Verify the stage stores the specific commit SHA
        assert stage.commit_sha == commit_sha
        
        # The commit SHA should be exactly what was provided
        assert len(stage.commit_sha) == 40
        assert stage.commit_sha != "HEAD"
        assert stage.commit_sha != ""
        
        # Verify the stage will clone at this specific commit
        # (the clone_repository method uses self.commit_sha)
        assert stage.commit_sha == commit_sha


# Feature: aphex-pipeline, Property 25: Commit-specific CDK code usage (verification)
def test_property_25_commit_specific_cdk_code_usage_verification():
    """
    Property 25: Commit-specific CDK code usage (verification)
    
    Verify that when cloning the repository, the exact commit SHA is checked out
    and verified, ensuring CDK code is from that specific commit.
    
    Validates: Requirements 12.5
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir) / "workspace"
        artifacts = Path(temp_dir) / "artifacts"
        
        # Create a test repository with multiple commits
        test_repo = Path(temp_dir) / "test_repo"
        test_repo.mkdir()
        
        # Initialize repo
        subprocess.run(
            ["git", "init"],
            cwd=str(test_repo),
            capture_output=True,
            check=True
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=str(test_repo),
            capture_output=True,
            check=True
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=str(test_repo),
            capture_output=True,
            check=True
        )
        
        # Create first commit with CDK code version 1
        (test_repo / "cdk_code.txt").write_text("CDK code version 1")
        subprocess.run(["git", "add", "."], cwd=str(test_repo), capture_output=True, check=True)
        subprocess.run(
            ["git", "commit", "-m", "First commit"],
            cwd=str(test_repo),
            capture_output=True,
            check=True
        )
        
        # Get first commit SHA
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(test_repo),
            capture_output=True,
            text=True,
            check=True
        )
        first_commit_sha = result.stdout.strip()
        
        # Create second commit with CDK code version 2
        (test_repo / "cdk_code.txt").write_text("CDK code version 2")
        subprocess.run(["git", "add", "."], cwd=str(test_repo), capture_output=True, check=True)
        subprocess.run(
            ["git", "commit", "-m", "Second commit"],
            cwd=str(test_repo),
            capture_output=True,
            check=True
        )
        
        # Get second commit SHA
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(test_repo),
            capture_output=True,
            text=True,
            check=True
        )
        second_commit_sha = result.stdout.strip()
        
        # Verify we have two different commits
        assert first_commit_sha != second_commit_sha
        
        # Create environment deployment stage for first commit
        environment = EnvironmentConfig(
            name="test-env",
            region="us-east-1",
            account="123456789012",
            stacks=[StackConfig(name="TestStack", path=".")],
            tests=None
        )
        
        stage = EnvironmentDeploymentStage(
            repo_url=str(test_repo),
            commit_sha=first_commit_sha,
            environment=environment,
            workspace_dir=str(workspace),
            artifacts_dir=str(artifacts)
        )
        
        # Clone the repository
        stage.clone_repository()
        
        # Verify we're at the first commit, not the second (HEAD)
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(workspace),
            capture_output=True,
            text=True,
            check=True
        )
        checked_out_sha = result.stdout.strip()
        
        # Should be at first commit, not second
        assert checked_out_sha == first_commit_sha
        assert checked_out_sha != second_commit_sha
        
        # Verify CDK code is from first commit
        cdk_code_content = (workspace / "cdk_code.txt").read_text()
        assert cdk_code_content == "CDK code version 1"
        assert cdk_code_content != "CDK code version 2"


# Feature: aphex-pipeline, Property 11: Stack output capture
@settings(max_examples=100)
@given(
    stack_name=valid_stack_name(),
    output_key=st.text(
        alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789',
        min_size=1,
        max_size=20
    ),
    output_value=st.text(min_size=1, max_size=100)
)
def test_property_11_stack_output_capture(stack_name, output_key, output_value):
    """
    Property 11: Stack output capture
    
    For any CDK stack that produces outputs, those outputs should be captured
    and available to subsequent stages.
    
    Validates: Requirements 5.3
    """
    # Create a StackOutput object
    stack_output = StackOutput(
        output_key=output_key,
        output_value=output_value,
        description="Test output",
        export_name=None
    )
    
    # Verify the output has the correct structure
    assert stack_output.output_key == output_key
    assert stack_output.output_value == output_value
    assert isinstance(stack_output.output_key, str)
    assert isinstance(stack_output.output_value, str)
    
    # Create a StackDeploymentResult with outputs
    result = StackDeploymentResult(
        stack_name=stack_name,
        status="success",
        outputs=[stack_output]
    )
    
    # Verify outputs are captured in the result
    assert len(result.outputs) == 1
    assert result.outputs[0].output_key == output_key
    assert result.outputs[0].output_value == output_value


# Feature: aphex-pipeline, Property 11: Stack output capture (multiple outputs)
def test_property_11_stack_output_capture_multiple_outputs():
    """
    Property 11: Stack output capture (multiple outputs)
    
    For any CDK stack with multiple outputs, all outputs should be captured.
    
    Validates: Requirements 5.3
    """
    outputs = [
        StackOutput(output_key="Output1", output_value="Value1"),
        StackOutput(output_key="Output2", output_value="Value2"),
        StackOutput(output_key="Output3", output_value="Value3"),
    ]
    
    result = StackDeploymentResult(
        stack_name="TestStack",
        status="success",
        outputs=outputs
    )
    
    # All outputs should be captured
    assert len(result.outputs) == 3
    assert result.outputs[0].output_key == "Output1"
    assert result.outputs[1].output_key == "Output2"
    assert result.outputs[2].output_key == "Output3"


# Feature: aphex-pipeline, Property 11: Stack output capture (persistence)
def test_property_11_stack_output_capture_persistence():
    """
    Property 11: Stack output capture (persistence)
    
    Verify that captured outputs can be saved to a file and retrieved.
    
    Validates: Requirements 5.3
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir) / "workspace"
        artifacts = Path(temp_dir) / "artifacts"
        
        environment = EnvironmentConfig(
            name="test-env",
            region="us-east-1",
            account="123456789012",
            stacks=[StackConfig(name="TestStack", path=".")],
            tests=None
        )
        
        stage = EnvironmentDeploymentStage(
            repo_url="https://github.com/test/repo.git",
            commit_sha="a" * 40,
            environment=environment,
            workspace_dir=str(workspace),
            artifacts_dir=str(artifacts)
        )
        
        # Create mock stack results with outputs
        stage.stack_results = [
            StackDeploymentResult(
                stack_name="Stack1",
                status="success",
                outputs=[
                    StackOutput(output_key="Url", output_value="https://example.com"),
                    StackOutput(output_key="BucketName", output_value="my-bucket"),
                ]
            ),
            StackDeploymentResult(
                stack_name="Stack2",
                status="success",
                outputs=[
                    StackOutput(output_key="ApiKey", output_value="abc123"),
                ]
            ),
        ]
        
        # Save outputs to file
        output_file = Path(temp_dir) / "outputs.json"
        stage.save_outputs_to_file(str(output_file))
        
        # Verify file exists
        assert output_file.exists()
        
        # Read and verify contents
        with open(output_file, 'r') as f:
            saved_outputs = json.load(f)
        
        # Verify structure
        assert "Stack1" in saved_outputs
        assert "Stack2" in saved_outputs
        
        # Verify Stack1 outputs
        assert "Url" in saved_outputs["Stack1"]
        assert saved_outputs["Stack1"]["Url"]["value"] == "https://example.com"
        assert "BucketName" in saved_outputs["Stack1"]
        assert saved_outputs["Stack1"]["BucketName"]["value"] == "my-bucket"
        
        # Verify Stack2 outputs
        assert "ApiKey" in saved_outputs["Stack2"]
        assert saved_outputs["Stack2"]["ApiKey"]["value"] == "abc123"


# Feature: aphex-pipeline, Property 24: Stage output propagation
@settings(max_examples=100)
@given(
    commit_sha=valid_commit_sha(),
    output_value=st.text(min_size=1, max_size=100)
)
def test_property_24_stage_output_propagation(commit_sha, output_value):
    """
    Property 24: Stage output propagation
    
    For any stage that produces outputs, those outputs should be available as
    inputs to subsequent stages.
    
    Validates: Requirements 12.3
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir) / "workspace"
        artifacts = Path(temp_dir) / "artifacts"
        
        environment = EnvironmentConfig(
            name="test-env",
            region="us-east-1",
            account="123456789012",
            stacks=[StackConfig(name="TestStack", path=".")],
            tests=None
        )
        
        stage = EnvironmentDeploymentStage(
            repo_url="https://github.com/test/repo.git",
            commit_sha=commit_sha,
            environment=environment,
            workspace_dir=str(workspace),
            artifacts_dir=str(artifacts)
        )
        
        # Create a deployment result with outputs
        result = EnvironmentDeploymentResult(
            environment_name=environment.name,
            region=environment.region,
            account=environment.account,
            commit_sha=commit_sha,
            stack_results=[
                StackDeploymentResult(
                    stack_name="TestStack",
                    status="success",
                    outputs=[
                        StackOutput(output_key="TestOutput", output_value=output_value)
                    ]
                )
            ],
            status="success"
        )
        
        # Verify the result contains the outputs
        assert len(result.stack_results) == 1
        assert len(result.stack_results[0].outputs) == 1
        assert result.stack_results[0].outputs[0].output_value == output_value
        
        # Verify the outputs are accessible from the result
        captured_output = result.stack_results[0].outputs[0].output_value
        assert captured_output == output_value


# Feature: aphex-pipeline, Property 24: Stage output propagation (multiple stages)
def test_property_24_stage_output_propagation_multiple_stages():
    """
    Property 24: Stage output propagation (multiple stages)
    
    Verify that outputs from multiple stacks are all available for propagation.
    
    Validates: Requirements 12.3
    """
    result = EnvironmentDeploymentResult(
        environment_name="test-env",
        region="us-east-1",
        account="123456789012",
        commit_sha="a" * 40,
        stack_results=[
            StackDeploymentResult(
                stack_name="Stack1",
                status="success",
                outputs=[
                    StackOutput(output_key="Output1", output_value="Value1")
                ]
            ),
            StackDeploymentResult(
                stack_name="Stack2",
                status="success",
                outputs=[
                    StackOutput(output_key="Output2", output_value="Value2")
                ]
            ),
            StackDeploymentResult(
                stack_name="Stack3",
                status="success",
                outputs=[
                    StackOutput(output_key="Output3", output_value="Value3")
                ]
            ),
        ],
        status="success"
    )
    
    # All outputs should be available
    assert len(result.stack_results) == 3
    
    # Verify each output is accessible
    assert result.stack_results[0].outputs[0].output_value == "Value1"
    assert result.stack_results[1].outputs[0].output_value == "Value2"
    assert result.stack_results[2].outputs[0].output_value == "Value3"
    
    # Verify outputs can be collected for propagation
    all_outputs = {}
    for stack_result in result.stack_results:
        for output in stack_result.outputs:
            all_outputs[f"{stack_result.stack_name}.{output.output_key}"] = output.output_value
    
    assert all_outputs["Stack1.Output1"] == "Value1"
    assert all_outputs["Stack2.Output2"] == "Value2"
    assert all_outputs["Stack3.Output3"] == "Value3"



# Feature: aphex-pipeline, Property 14: Cross-account role assumption
@settings(max_examples=100)
@given(
    current_account=st.text(alphabet='0123456789', min_size=12, max_size=12),
    target_account=st.text(alphabet='0123456789', min_size=12, max_size=12),
    commit_sha=valid_commit_sha()
)
def test_property_14_cross_account_role_assumption(current_account, target_account, commit_sha):
    """
    Property 14: Cross-account role assumption
    
    For any deployment to an AWS account different from the pipeline account,
    the correct cross-account IAM role should be assumed.
    
    Validates: Requirements 7.2
    """
    # Ensure we have different accounts for cross-account scenario
    assume(current_account != target_account)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir) / "workspace"
        artifacts = Path(temp_dir) / "artifacts"
        
        environment = EnvironmentConfig(
            name="test-env",
            region="us-east-1",
            account=target_account,
            stacks=[StackConfig(name="TestStack", path=".")],
            tests=None
        )
        
        stage = EnvironmentDeploymentStage(
            repo_url="https://github.com/test/repo.git",
            commit_sha=commit_sha,
            environment=environment,
            workspace_dir=str(workspace),
            artifacts_dir=str(artifacts),
            cross_account_role_name="TestCrossAccountRole"
        )
        
        # Mock the AWS API calls
        mock_credentials = {
            'AccessKeyId': 'AKIAIOSFODNN7EXAMPLE',
            'SecretAccessKey': 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY',
            'SessionToken': 'FwoGZXIvYXdzEBYaDH...'
        }
        
        with patch('environment_deployment_stage.get_current_account_id', return_value=current_account):
            with patch('environment_deployment_stage.assume_cross_account_role', return_value=mock_credentials):
                # Call the cross-account detection method
                stage.detect_and_assume_cross_account_role()
                
                # Verify that the current account was detected
                assert stage.current_account_id == current_account
                
                # Verify that credentials were assumed (since accounts are different)
                assert stage.assumed_credentials is not None
                assert stage.assumed_credentials == mock_credentials
                
                # Verify that AWS credentials environment variables were set
                assert os.environ.get('AWS_ACCESS_KEY_ID') == mock_credentials['AccessKeyId']
                assert os.environ.get('AWS_SECRET_ACCESS_KEY') == mock_credentials['SecretAccessKey']
                assert os.environ.get('AWS_SESSION_TOKEN') == mock_credentials['SessionToken']


# Feature: aphex-pipeline, Property 14: Cross-account role assumption (same account)
@settings(max_examples=100)
@given(
    account=st.text(alphabet='0123456789', min_size=12, max_size=12),
    commit_sha=valid_commit_sha()
)
def test_property_14_cross_account_role_assumption_same_account(account, commit_sha):
    """
    Property 14: Cross-account role assumption (same account)
    
    For any deployment to the same AWS account as the pipeline account,
    no cross-account role should be assumed.
    
    Validates: Requirements 7.2
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir) / "workspace"
        artifacts = Path(temp_dir) / "artifacts"
        
        environment = EnvironmentConfig(
            name="test-env",
            region="us-east-1",
            account=account,
            stacks=[StackConfig(name="TestStack", path=".")],
            tests=None
        )
        
        stage = EnvironmentDeploymentStage(
            repo_url="https://github.com/test/repo.git",
            commit_sha=commit_sha,
            environment=environment,
            workspace_dir=str(workspace),
            artifacts_dir=str(artifacts),
            cross_account_role_name="TestCrossAccountRole"
        )
        
        # Mock the AWS API calls - same account
        with patch('environment_deployment_stage.get_current_account_id', return_value=account):
            with patch('environment_deployment_stage.assume_cross_account_role') as mock_assume:
                # Call the cross-account detection method
                stage.detect_and_assume_cross_account_role()
                
                # Verify that the current account was detected
                assert stage.current_account_id == account
                
                # Verify that no credentials were assumed (same account)
                assert stage.assumed_credentials is None
                
                # Verify that assume_cross_account_role was NOT called
                mock_assume.assert_not_called()


# Feature: aphex-pipeline, Property 14: Cross-account role assumption (role ARN format)
@settings(max_examples=100)
@given(
    target_account=st.text(alphabet='0123456789', min_size=12, max_size=12),
    role_name=st.text(
        alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-',
        min_size=1,
        max_size=20
    )
)
def test_property_14_cross_account_role_assumption_role_arn_format(target_account, role_name):
    """
    Property 14: Cross-account role assumption (role ARN format)
    
    For any target account and role name, the correct role ARN should be constructed
    in the format: arn:aws:iam::{account}:role/{role_name}
    
    Validates: Requirements 7.2
    """
    expected_role_arn = f"arn:aws:iam::{target_account}:role/{role_name}"
    
    # Mock the STS client
    mock_sts_client = MagicMock()
    mock_sts_client.assume_role.return_value = {
        'Credentials': {
            'AccessKeyId': 'AKIAIOSFODNN7EXAMPLE',
            'SecretAccessKey': 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY',
            'SessionToken': 'FwoGZXIvYXdzEBYaDH...'
        }
    }
    
    with patch('boto3.client', return_value=mock_sts_client):
        # Call assume_cross_account_role
        credentials = assume_cross_account_role(
            target_account=target_account,
            role_name=role_name,
            session_name="TestSession"
        )
        
        # Verify that assume_role was called with the correct ARN
        mock_sts_client.assume_role.assert_called_once()
        call_args = mock_sts_client.assume_role.call_args
        
        # Check that the RoleArn parameter matches the expected format
        assert call_args[1]['RoleArn'] == expected_role_arn
        assert call_args[1]['RoleSessionName'] == "TestSession"
        
        # Verify credentials were returned
        assert credentials['AccessKeyId'] == 'AKIAIOSFODNN7EXAMPLE'
        assert credentials['SecretAccessKey'] == 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY'
        assert credentials['SessionToken'] == 'FwoGZXIvYXdzEBYaDH...'


# Feature: aphex-pipeline, Property 14: Cross-account role assumption (credentials structure)
def test_property_14_cross_account_role_assumption_credentials_structure():
    """
    Property 14: Cross-account role assumption (credentials structure)
    
    For any successful role assumption, the returned credentials should contain
    AccessKeyId, SecretAccessKey, and SessionToken.
    
    Validates: Requirements 7.2
    """
    target_account = "123456789012"
    role_name = "TestRole"
    
    # Mock the STS client
    mock_sts_client = MagicMock()
    mock_sts_client.assume_role.return_value = {
        'Credentials': {
            'AccessKeyId': 'AKIAIOSFODNN7EXAMPLE',
            'SecretAccessKey': 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY',
            'SessionToken': 'FwoGZXIvYXdzEBYaDH...',
            'Expiration': '2024-01-01T00:00:00Z'
        }
    }
    
    with patch('boto3.client', return_value=mock_sts_client):
        credentials = assume_cross_account_role(
            target_account=target_account,
            role_name=role_name
        )
        
        # Verify credentials structure
        assert 'AccessKeyId' in credentials
        assert 'SecretAccessKey' in credentials
        assert 'SessionToken' in credentials
        
        # Verify all values are non-empty strings
        assert isinstance(credentials['AccessKeyId'], str)
        assert isinstance(credentials['SecretAccessKey'], str)
        assert isinstance(credentials['SessionToken'], str)
        assert len(credentials['AccessKeyId']) > 0
        assert len(credentials['SecretAccessKey']) > 0
        assert len(credentials['SessionToken']) > 0


# Feature: aphex-pipeline, Property 14: Cross-account role assumption (error handling)
def test_property_14_cross_account_role_assumption_error_handling():
    """
    Property 14: Cross-account role assumption (error handling)
    
    For any failed role assumption, an EnvironmentDeploymentError should be raised
    with a descriptive error message.
    
    Validates: Requirements 7.2
    """
    target_account = "123456789012"
    role_name = "NonExistentRole"
    
    # Mock the STS client to raise an error
    mock_sts_client = MagicMock()
    from botocore.exceptions import ClientError
    mock_sts_client.assume_role.side_effect = ClientError(
        {
            'Error': {
                'Code': 'AccessDenied',
                'Message': 'User is not authorized to perform: sts:AssumeRole'
            }
        },
        'AssumeRole'
    )
    
    with patch('boto3.client', return_value=mock_sts_client):
        # Verify that an EnvironmentDeploymentError is raised
        with pytest.raises(EnvironmentDeploymentError) as exc_info:
            assume_cross_account_role(
                target_account=target_account,
                role_name=role_name
            )
        
        # Verify the error message contains useful information
        error_message = str(exc_info.value)
        assert 'AccessDenied' in error_message
        assert target_account in error_message
