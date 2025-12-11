"""
Property-based tests for AphexPipeline validation logic.

These tests verify universal properties for AWS credential validation,
CDK context validation, and build tool validation.
"""

import json
import tempfile
import os
from pathlib import Path
from hypothesis import given, strategies as st, settings, assume
from unittest.mock import patch, MagicMock
import pytest
import subprocess

from validation import (
    validate_aws_credentials,
    validate_cdk_context,
    validate_build_tools,
    ValidationError
)


# Hypothesis strategies for generating test data

@st.composite
def aws_account_id(draw):
    """Generate a valid 12-digit AWS account ID."""
    return ''.join([str(draw(st.integers(min_value=0, max_value=9))) for _ in range(12)])


@st.composite
def aws_region(draw):
    """Generate a valid AWS region."""
    return draw(st.sampled_from([
        'us-east-1', 'us-east-2', 'us-west-1', 'us-west-2',
        'eu-west-1', 'eu-west-2', 'eu-central-1',
        'ap-southeast-1', 'ap-southeast-2', 'ap-northeast-1',
        'ca-central-1', 'sa-east-1'
    ]))


# Feature: aphex-pipeline, Property 20: AWS credential validation
@settings(max_examples=100)
@given(
    account_id=aws_account_id(),
    region=aws_region()
)
def test_property_20_aws_credential_validation_with_valid_credentials(account_id, region):
    """
    Property 20: AWS credential validation
    
    For any AWS account referenced in environment configuration, credentials
    should be validated before deployment.
    
    This test verifies that when valid credentials are available, validation succeeds.
    
    Validates: Requirements 9.3
    """
    # Mock boto3 session and STS client
    mock_identity = {
        'Account': account_id,
        'UserId': 'AIDAI123456789EXAMPLE',
        'Arn': f'arn:aws:iam::{account_id}:user/test-user'
    }
    
    with patch('validation.boto3.Session') as mock_session:
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = mock_identity
        mock_session.return_value.client.return_value = mock_sts
        
        # Validation should succeed
        result = validate_aws_credentials(account_id=account_id, region=region)
        assert result is True
        
        # Verify STS was called
        mock_sts.get_caller_identity.assert_called_once()


# Feature: aphex-pipeline, Property 20: AWS credential validation
@settings(max_examples=100)
@given(
    expected_account=aws_account_id(),
    actual_account=aws_account_id(),
    region=aws_region()
)
def test_property_20_aws_credential_validation_detects_account_mismatch(
    expected_account, actual_account, region
):
    """
    Property 20: AWS credential validation (account mismatch)
    
    For any AWS account referenced in environment configuration, if the actual
    credentials are for a different account, validation should fail.
    
    Validates: Requirements 9.3
    """
    # Only test when accounts are different
    assume(expected_account != actual_account)
    
    # Mock boto3 session with mismatched account
    mock_identity = {
        'Account': actual_account,
        'UserId': 'AIDAI123456789EXAMPLE',
        'Arn': f'arn:aws:iam::{actual_account}:user/test-user'
    }
    
    with patch('validation.boto3.Session') as mock_session:
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = mock_identity
        mock_session.return_value.client.return_value = mock_sts
        
        # Validation should fail with account mismatch
        with pytest.raises(ValidationError) as exc_info:
            validate_aws_credentials(account_id=expected_account, region=region)
        
        assert 'account mismatch' in str(exc_info.value).lower()
        assert expected_account in str(exc_info.value)
        assert actual_account in str(exc_info.value)


# Feature: aphex-pipeline, Property 20: AWS credential validation
@settings(max_examples=50)
@given(region=aws_region())
def test_property_20_aws_credential_validation_fails_without_credentials(region):
    """
    Property 20: AWS credential validation (no credentials)
    
    For any AWS region, if no credentials are available, validation should fail
    with a clear error message.
    
    Validates: Requirements 9.3
    """
    from botocore.exceptions import NoCredentialsError
    
    with patch('validation.boto3.Session') as mock_session:
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.side_effect = NoCredentialsError()
        mock_session.return_value.client.return_value = mock_sts
        
        # Validation should fail
        with pytest.raises(ValidationError) as exc_info:
            validate_aws_credentials(region=region)
        
        assert 'credentials not found' in str(exc_info.value).lower()



# Feature: aphex-pipeline, Property 21: CDK context validation
@settings(max_examples=100)
@given(
    context_keys=st.lists(
        st.text(min_size=1, max_size=30, alphabet=st.characters(
            whitelist_categories=('Lu', 'Ll', 'Nd'), min_codepoint=65, max_codepoint=122
        )).map(lambda s: s.replace(' ', '-')),
        min_size=1,
        max_size=10,
        unique=True
    ),
    context_values=st.lists(st.text(min_size=1, max_size=50), min_size=1, max_size=10)
)
def test_property_21_cdk_context_validation_with_all_required_keys(context_keys, context_values):
    """
    Property 21: CDK context validation
    
    For any required CDK context value, it should be validated as present before synthesis.
    
    This test verifies that when all required context keys are present, validation succeeds.
    
    Validates: Requirements 9.4
    """
    # Ensure we have enough values for all keys
    assume(len(context_values) >= len(context_keys))
    
    # Create a temporary cdk.json with all required context
    with tempfile.TemporaryDirectory() as tmpdir:
        cdk_json_path = Path(tmpdir) / 'cdk.json'
        
        # Build context dict
        context = {key: context_values[i] for i, key in enumerate(context_keys)}
        
        cdk_config = {
            'app': 'npx ts-node bin/app.ts',
            'context': context
        }
        
        with open(cdk_json_path, 'w') as f:
            json.dump(cdk_config, f)
        
        # Validation should succeed
        result = validate_cdk_context(context_keys, str(cdk_json_path))
        assert result is True


# Feature: aphex-pipeline, Property 21: CDK context validation
@settings(max_examples=100)
@given(
    required_keys=st.lists(
        st.text(min_size=1, max_size=30, alphabet=st.characters(
            whitelist_categories=('Lu', 'Ll', 'Nd'), min_codepoint=65, max_codepoint=122
        )).map(lambda s: s.replace(' ', '-')),
        min_size=2,
        max_size=10,
        unique=True
    ),
    context_values=st.lists(st.text(min_size=1, max_size=50), min_size=1, max_size=10)
)
def test_property_21_cdk_context_validation_detects_missing_keys(required_keys, context_values):
    """
    Property 21: CDK context validation (missing keys)
    
    For any required CDK context value, if it is missing from cdk.json,
    validation should fail with a clear error message.
    
    Validates: Requirements 9.4
    """
    # Ensure we have at least 2 required keys so we can omit one
    assume(len(required_keys) >= 2)
    assume(len(context_values) >= len(required_keys) - 1)
    
    # Create a temporary cdk.json with only some of the required context
    with tempfile.TemporaryDirectory() as tmpdir:
        cdk_json_path = Path(tmpdir) / 'cdk.json'
        
        # Build context dict with all but the last required key
        context = {key: context_values[i] for i, key in enumerate(required_keys[:-1])}
        
        cdk_config = {
            'app': 'npx ts-node bin/app.ts',
            'context': context
        }
        
        with open(cdk_json_path, 'w') as f:
            json.dump(cdk_config, f)
        
        # Validation should fail
        with pytest.raises(ValidationError) as exc_info:
            validate_cdk_context(required_keys, str(cdk_json_path))
        
        # Error message should mention the missing key
        assert 'missing' in str(exc_info.value).lower()
        assert required_keys[-1] in str(exc_info.value)


# Feature: aphex-pipeline, Property 21: CDK context validation
@settings(max_examples=50)
@given(
    context_keys=st.lists(
        st.text(min_size=1, max_size=30, alphabet='abcdefghijklmnopqrstuvwxyz'),
        min_size=1,
        max_size=5,
        unique=True
    )
)
def test_property_21_cdk_context_validation_fails_without_cdk_json(context_keys):
    """
    Property 21: CDK context validation (missing cdk.json)
    
    For any required CDK context values, if cdk.json doesn't exist,
    validation should fail with a clear error message.
    
    Validates: Requirements 9.4
    """
    # Use a non-existent path
    with tempfile.TemporaryDirectory() as tmpdir:
        cdk_json_path = Path(tmpdir) / 'nonexistent' / 'cdk.json'
        
        # Validation should fail
        with pytest.raises(ValidationError) as exc_info:
            validate_cdk_context(context_keys, str(cdk_json_path))
        
        assert 'not found' in str(exc_info.value).lower()



# Feature: aphex-pipeline, Property 22: Build tool validation
@settings(max_examples=100)
@given(
    available_tools=st.lists(
        st.sampled_from(['python', 'python3', 'node', 'npm', 'git', 'bash', 'sh']),
        min_size=1,
        max_size=5,
        unique=True
    )
)
def test_property_22_build_tool_validation_with_available_tools(available_tools):
    """
    Property 22: Build tool validation
    
    For any build command specified in configuration, the required tools should be
    validated as available in the container.
    
    This test verifies that when all required tools are available, validation succeeds.
    
    Validates: Requirements 9.5
    """
    # Mock subprocess to simulate tools being available
    def mock_run(cmd, **kwargs):
        result = MagicMock()
        result.returncode = 0
        result.stdout = b'version 1.0.0'
        result.stderr = b''
        return result
    
    with patch('validation.subprocess.run', side_effect=mock_run):
        # Validation should succeed
        result = validate_build_tools(available_tools)
        assert result is True


# Feature: aphex-pipeline, Property 22: Build tool validation
@settings(max_examples=100)
@given(
    required_tools=st.lists(
        st.text(min_size=1, max_size=20, alphabet='abcdefghijklmnopqrstuvwxyz0123456789-'),
        min_size=2,
        max_size=5,
        unique=True
    )
)
def test_property_22_build_tool_validation_detects_missing_tools(required_tools):
    """
    Property 22: Build tool validation (missing tools)
    
    For any build command specified in configuration, if required tools are not
    available, validation should fail with a clear error message.
    
    Validates: Requirements 9.5
    """
    # Ensure we have at least 2 tools so we can make one missing
    assume(len(required_tools) >= 2)
    
    # Mock subprocess to simulate some tools missing
    def mock_run(cmd, **kwargs):
        tool = cmd[0]
        result = MagicMock()
        
        # Make the last tool in the list unavailable
        if tool == required_tools[-1]:
            raise FileNotFoundError(f"Tool not found: {tool}")
        
        result.returncode = 0
        result.stdout = b'version 1.0.0'
        result.stderr = b''
        return result
    
    with patch('validation.subprocess.run', side_effect=mock_run):
        # Validation should fail
        with pytest.raises(ValidationError) as exc_info:
            validate_build_tools(required_tools)
        
        # Error message should mention the missing tool
        assert 'missing' in str(exc_info.value).lower()
        assert required_tools[-1] in str(exc_info.value)


# Feature: aphex-pipeline, Property 22: Build tool validation
@settings(max_examples=50)
@given(
    required_tools=st.lists(
        st.text(min_size=1, max_size=20, alphabet='abcdefghijklmnopqrstuvwxyz0123456789-'),
        min_size=1,
        max_size=5,
        unique=True
    )
)
def test_property_22_build_tool_validation_handles_tool_errors(required_tools):
    """
    Property 22: Build tool validation (tool errors)
    
    For any build command specified in configuration, if a tool exists but returns
    an error when checking version, it should be considered unavailable.
    
    Validates: Requirements 9.5
    """
    # Mock subprocess to simulate tools returning errors
    def mock_run(cmd, **kwargs):
        result = MagicMock()
        result.returncode = 1  # Non-zero return code
        result.stdout = b''
        result.stderr = b'error'
        return result
    
    with patch('validation.subprocess.run', side_effect=mock_run):
        # Validation should fail for all tools
        with pytest.raises(ValidationError) as exc_info:
            validate_build_tools(required_tools)
        
        # Error message should mention missing tools
        assert 'missing' in str(exc_info.value).lower()
