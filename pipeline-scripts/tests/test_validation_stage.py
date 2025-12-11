"""
Integration tests for validation stage.

These tests verify that the validation stage script works correctly
when invoked as a command-line tool.
"""

import subprocess
import tempfile
import yaml
import os
from pathlib import Path
import pytest


def get_script_path():
    """Get the path to the validation_stage.py script."""
    # Tests run from pipeline-scripts directory
    return Path(__file__).parent.parent / 'validation_stage.py'


def test_validation_stage_succeeds_with_valid_config():
    """Test that validation stage succeeds with a valid configuration."""
    # Create a temporary valid config
    config = {
        'version': '1.0',
        'build': {
            'commands': ['npm install', 'npm run build']
        },
        'environments': [
            {
                'name': 'dev',
                'region': 'us-east-1',
                'account': '123456789012',
                'stacks': [
                    {'name': 'DevStack', 'path': 'lib/dev-stack.ts'}
                ]
            }
        ]
    }
    
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / 'test-config.yaml'
        with open(config_path, 'w') as f:
            yaml.dump(config, f)
        
        # Get the schema path from the root directory
        schema_path = Path(__file__).parent.parent.parent / 'aphex-config.schema.json'
        
        # Run validation stage
        result = subprocess.run(
            [
                'python', str(get_script_path()),
                '--config', str(config_path),
                '--schema', str(schema_path),
                '--skip-aws-validation',
                '--skip-cdk-validation',
                '--skip-tool-validation'
            ],
            capture_output=True,
            text=True
        )
        
        # Should succeed
        assert result.returncode == 0
        assert 'All validations PASSED' in result.stdout


def test_validation_stage_fails_with_invalid_config():
    """Test that validation stage fails with an invalid configuration."""
    # Create a temporary invalid config (missing required field)
    config = {
        'version': '1.0',
        'build': {
            'commands': ['npm install']
        }
        # Missing 'environments' field
    }
    
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / 'test-config.yaml'
        with open(config_path, 'w') as f:
            yaml.dump(config, f)
        
        # Run validation stage
        result = subprocess.run(
            [
                'python', str(get_script_path()),
                '--config', str(config_path),
                '--skip-aws-validation',
                '--skip-cdk-validation',
                '--skip-tool-validation'
            ],
            capture_output=True,
            text=True
        )
        
        # Should fail
        assert result.returncode == 1
        assert 'Validation FAILED' in result.stdout


def test_validation_stage_fails_with_missing_config():
    """Test that validation stage fails when config file doesn't exist."""
    # Run validation stage with non-existent config
    result = subprocess.run(
        [
            'python', str(get_script_path()),
            '--config', 'nonexistent-config.yaml',
            '--skip-aws-validation',
            '--skip-cdk-validation',
            '--skip-tool-validation'
        ],
        capture_output=True,
        text=True
    )
    
    # Should fail
    assert result.returncode == 1
    assert 'Configuration file not found' in result.stdout


def test_validation_stage_displays_environment_info():
    """Test that validation stage displays environment information."""
    # Create a temporary valid config with multiple environments
    config = {
        'version': '1.0',
        'build': {
            'commands': ['npm install']
        },
        'environments': [
            {
                'name': 'dev',
                'region': 'us-east-1',
                'account': '123456789012',
                'stacks': [
                    {'name': 'DevStack', 'path': 'lib/dev-stack.ts'}
                ]
            },
            {
                'name': 'prod',
                'region': 'us-west-2',
                'account': '987654321098',
                'stacks': [
                    {'name': 'ProdStack', 'path': 'lib/prod-stack.ts'}
                ]
            }
        ]
    }
    
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / 'test-config.yaml'
        with open(config_path, 'w') as f:
            yaml.dump(config, f)
        
        # Get the schema path from the root directory
        schema_path = Path(__file__).parent.parent.parent / 'aphex-config.schema.json'
        
        # Run validation stage
        result = subprocess.run(
            [
                'python', str(get_script_path()),
                '--config', str(config_path),
                '--schema', str(schema_path),
                '--skip-aws-validation',
                '--skip-cdk-validation',
                '--skip-tool-validation'
            ],
            capture_output=True,
            text=True
        )
        
        # Should succeed and display environment info
        assert result.returncode == 0
        assert 'dev: us-east-1' in result.stdout
        assert 'prod: us-west-2' in result.stdout
        assert '123456789012' in result.stdout
        assert '987654321098' in result.stdout
