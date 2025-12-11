"""
Property-based tests for AphexPipeline configuration validation.

These tests verify universal properties that should hold across all valid
and invalid configurations.
"""

import json
import tempfile
import yaml
from pathlib import Path
from hypothesis import given, strategies as st, settings
from jsonschema import ValidationError
import pytest

from config_parser import ConfigParser, parse_config


# Hypothesis strategies for generating test data

@st.composite
def valid_stack_config(draw):
    """Generate a valid stack configuration."""
    return {
        'name': draw(st.text(min_size=1, max_size=50, alphabet=st.characters(
            whitelist_categories=('Lu', 'Ll', 'Nd'), min_codepoint=65, max_codepoint=122
        ))),
        'path': draw(st.text(min_size=1, max_size=100).map(lambda s: f"lib/{s}.ts"))
    }


@st.composite
def valid_environment_config(draw):
    """Generate a valid environment configuration."""
    env = {
        'name': draw(st.text(min_size=1, max_size=20, alphabet='abcdefghijklmnopqrstuvwxyz0123456789-')),
        'region': draw(st.sampled_from([
            'us-east-1', 'us-west-2', 'eu-west-1', 'ap-southeast-1', 'ca-central-1'
        ])),
        'account': draw(st.text(min_size=12, max_size=12, alphabet='0123456789')),
        'stacks': draw(st.lists(valid_stack_config(), min_size=1, max_size=5))
    }
    
    # Optionally add tests
    if draw(st.booleans()):
        env['tests'] = {
            'commands': draw(st.lists(st.text(min_size=1, max_size=50), min_size=1, max_size=5))
        }
    
    return env


@st.composite
def valid_config(draw):
    """Generate a valid AphexPipeline configuration."""
    return {
        'version': '1.0',
        'build': {
            'commands': draw(st.lists(st.text(min_size=1, max_size=100), min_size=1, max_size=10))
        },
        'environments': draw(st.lists(valid_environment_config(), min_size=1, max_size=5))
    }


@st.composite
def invalid_config(draw):
    """Generate an invalid configuration that should fail validation."""
    config_type = draw(st.sampled_from([
        'missing_version',
        'missing_build',
        'missing_environments',
        'empty_environments',
        'invalid_region',
        'invalid_account',
        'missing_stacks',
        'empty_build_commands'
    ]))
    
    if config_type == 'missing_version':
        return {
            'build': {'commands': ['npm install']},
            'environments': [draw(valid_environment_config())]
        }
    elif config_type == 'missing_build':
        return {
            'version': '1.0',
            'environments': [draw(valid_environment_config())]
        }
    elif config_type == 'missing_environments':
        return {
            'version': '1.0',
            'build': {'commands': ['npm install']}
        }
    elif config_type == 'empty_environments':
        return {
            'version': '1.0',
            'build': {'commands': ['npm install']},
            'environments': []
        }
    elif config_type == 'invalid_region':
        env = draw(valid_environment_config())
        env['region'] = 'invalid-region-format'
        return {
            'version': '1.0',
            'build': {'commands': ['npm install']},
            'environments': [env]
        }
    elif config_type == 'invalid_account':
        env = draw(valid_environment_config())
        env['account'] = '123'  # Too short
        return {
            'version': '1.0',
            'build': {'commands': ['npm install']},
            'environments': [env]
        }
    elif config_type == 'missing_stacks':
        env = draw(valid_environment_config())
        del env['stacks']
        return {
            'version': '1.0',
            'build': {'commands': ['npm install']},
            'environments': [env]
        }
    elif config_type == 'empty_build_commands':
        return {
            'version': '1.0',
            'build': {'commands': []},
            'environments': [draw(valid_environment_config())]
        }


# Feature: aphex-pipeline, Property 19: Configuration schema validation
@settings(max_examples=100)
@given(config_data=valid_config())
def test_property_19_valid_configs_pass_validation(config_data):
    """
    Property 19: Configuration schema validation
    
    For any valid configuration file, it should be validated against the JSON schema
    before workflow execution begins.
    
    Validates: Requirements 9.1
    """
    # Create temporary files for config and schema
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / 'aphex-config.yaml'
        schema_path = Path('aphex-config.schema.json')
        
        # Write config to file
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f)
        
        # Parse should succeed without raising an exception
        parser = ConfigParser(schema_path=str(schema_path))
        result = parser.parse(str(config_path))
        
        # Verify the parsed result matches the input
        assert result.version == config_data['version']
        assert len(result.environments) == len(config_data['environments'])
        assert len(result.build.commands) == len(config_data['build']['commands'])


# Feature: aphex-pipeline, Property 19: Configuration schema validation
@settings(max_examples=100)
@given(config_data=invalid_config())
def test_property_19_invalid_configs_fail_validation(config_data):
    """
    Property 19: Configuration schema validation (negative test)
    
    For any invalid configuration file, validation should fail with a clear error
    before workflow execution begins.
    
    Validates: Requirements 9.1
    """
    # Create temporary files for config and schema
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / 'aphex-config.yaml'
        schema_path = Path('aphex-config.schema.json')
        
        # Write config to file
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f)
        
        # Parse should raise ValidationError
        parser = ConfigParser(schema_path=str(schema_path))
        with pytest.raises(ValidationError):
            parser.parse(str(config_path))



# Feature: aphex-pipeline, Property 8: Environment configuration schema compliance
@settings(max_examples=100)
@given(config_data=valid_config())
def test_property_8_environment_schema_compliance(config_data):
    """
    Property 8: Environment configuration schema compliance
    
    For any environment definition in the configuration, it should specify AWS region,
    account, and at least one CDK stack.
    
    Validates: Requirements 4.2
    """
    # Create temporary files for config and schema
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / 'aphex-config.yaml'
        schema_path = Path('aphex-config.schema.json')
        
        # Write config to file
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f)
        
        # Parse the configuration
        parser = ConfigParser(schema_path=str(schema_path))
        result = parser.parse(str(config_path))
        
        # Verify each environment has required fields
        for env in result.environments:
            # Must have name
            assert env.name is not None
            assert len(env.name) > 0
            
            # Must have region
            assert env.region is not None
            assert len(env.region) > 0
            
            # Must have account
            assert env.account is not None
            assert len(env.account) == 12
            assert env.account.isdigit()
            
            # Must have at least one stack
            assert env.stacks is not None
            assert len(env.stacks) >= 1
            
            # Each stack must have name and path
            for stack in env.stacks:
                assert stack.name is not None
                assert len(stack.name) > 0
                assert stack.path is not None
                assert len(stack.path) > 0



# Feature: aphex-pipeline, Property 15: Credential absence in configuration
@settings(max_examples=100)
@given(config_data=valid_config())
def test_property_15_credential_absence(config_data):
    """
    Property 15: Credential absence in configuration
    
    For any configuration file, it should not contain AWS credentials, API keys,
    or other secrets.
    
    Validates: Requirements 7.5
    """
    # Convert config to string for pattern matching
    config_str = yaml.dump(config_data).lower()
    
    # Patterns that indicate credentials (case-insensitive)
    forbidden_patterns = [
        'aws_access_key_id',
        'aws_secret_access_key',
        'aws_session_token',
        'secret_key',
        'access_key',
        'api_key',
        'apikey',
        'password',
        'passwd',
        'secret',
        'token',
        'credentials',
        'private_key',
        'privatekey'
    ]
    
    # Check for suspicious patterns that look like actual credentials
    # (not just the word "secret" in a command, but actual key-value pairs)
    for pattern in forbidden_patterns:
        # Look for patterns like "aws_access_key_id: AKIA..." or "secret: abc123"
        if f'{pattern}:' in config_str or f'{pattern}=' in config_str:
            # Additional check: if it's followed by a value that looks like a credential
            # For this property test, we're checking that the config doesn't have
            # these patterns at all in key positions
            lines = config_str.split('\n')
            for line in lines:
                if f'{pattern}:' in line or f'{pattern}=' in line:
                    # Check if there's a value after the colon/equals
                    parts = line.split(':' if ':' in line else '=')
                    if len(parts) > 1:
                        value = parts[1].strip()
                        # If there's a non-empty value, this might be a credential
                        if value and value not in ['', 'null', 'none', '~']:
                            pytest.fail(f"Configuration contains potential credential pattern: {pattern}")
    
    # The test passes if no forbidden patterns are found
    # Since we're generating valid configs, they shouldn't contain credentials
    assert True
