"""
Validation module for AphexPipeline.

This module provides validation functions for AWS credentials, CDK context,
and build tools before workflow execution.
"""

import os
import subprocess
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from typing import List, Dict, Optional, Tuple


class ValidationError(Exception):
    """Exception raised when validation fails."""
    pass


def validate_aws_credentials(account_id: Optional[str] = None, region: Optional[str] = None) -> bool:
    """
    Validate that AWS credentials are available and valid.
    
    Args:
        account_id: Optional AWS account ID to validate against
        region: Optional AWS region to set
        
    Returns:
        True if credentials are valid
        
    Raises:
        ValidationError: If credentials are invalid or unavailable
    """
    try:
        # Set region if provided
        if region:
            session = boto3.Session(region_name=region)
        else:
            session = boto3.Session()
        
        # Try to get caller identity
        sts_client = session.client('sts')
        identity = sts_client.get_caller_identity()
        
        # Verify account ID if provided
        if account_id:
            actual_account = identity['Account']
            if actual_account != account_id:
                raise ValidationError(
                    f"AWS account mismatch: expected {account_id}, got {actual_account}"
                )
        
        return True
        
    except NoCredentialsError:
        raise ValidationError("AWS credentials not found. Please configure AWS credentials.")
    except ClientError as e:
        raise ValidationError(f"AWS credential validation failed: {str(e)}")
    except Exception as e:
        raise ValidationError(f"Unexpected error validating AWS credentials: {str(e)}")


def validate_cdk_context(context_requirements: List[str], cdk_json_path: str = "cdk.json") -> bool:
    """
    Validate that required CDK context values are present.
    
    Args:
        context_requirements: List of required context keys
        cdk_json_path: Path to cdk.json file
        
    Returns:
        True if all required context values are present
        
    Raises:
        ValidationError: If required context values are missing
    """
    import json
    from pathlib import Path
    
    # Check if cdk.json exists
    cdk_json = Path(cdk_json_path)
    if not cdk_json.exists():
        raise ValidationError(f"cdk.json not found at {cdk_json_path}")
    
    # Load cdk.json
    try:
        with open(cdk_json, 'r') as f:
            cdk_config = json.load(f)
    except json.JSONDecodeError as e:
        raise ValidationError(f"Invalid JSON in cdk.json: {str(e)}")
    
    # Check for context section
    context = cdk_config.get('context', {})
    
    # Validate each required context key
    missing_keys = []
    for key in context_requirements:
        if key not in context:
            missing_keys.append(key)
    
    if missing_keys:
        raise ValidationError(
            f"Missing required CDK context values: {', '.join(missing_keys)}"
        )
    
    return True


def validate_build_tools(required_tools: List[str]) -> bool:
    """
    Validate that required build tools are available in the container.
    
    Args:
        required_tools: List of required tool names (e.g., ['npm', 'python3', 'aws'])
        
    Returns:
        True if all required tools are available
        
    Raises:
        ValidationError: If required tools are missing
    """
    missing_tools = []
    
    for tool in required_tools:
        try:
            # Try to run the tool with --version or -v
            result = subprocess.run(
                [tool, '--version'],
                capture_output=True,
                timeout=5
            )
            # If the command fails, try with -v
            if result.returncode != 0:
                result = subprocess.run(
                    [tool, '-v'],
                    capture_output=True,
                    timeout=5
                )
            # If still fails, consider it missing
            if result.returncode != 0:
                missing_tools.append(tool)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            missing_tools.append(tool)
    
    if missing_tools:
        raise ValidationError(
            f"Missing required build tools: {', '.join(missing_tools)}"
        )
    
    return True


def validate_all(
    config_path: str,
    schema_path: str = "aphex-config.schema.json",
    cdk_json_path: str = "cdk.json",
    context_requirements: Optional[List[str]] = None
) -> Tuple[bool, List[str]]:
    """
    Perform all validation checks before workflow execution.
    
    Args:
        config_path: Path to aphex-config.yaml
        schema_path: Path to JSON schema
        cdk_json_path: Path to cdk.json
        context_requirements: Optional list of required CDK context keys
        
    Returns:
        Tuple of (success: bool, errors: List[str])
    """
    from config_parser import parse_config
    
    errors = []
    
    # 1. Validate configuration schema
    try:
        config = parse_config(config_path, schema_path)
    except Exception as e:
        errors.append(f"Configuration validation failed: {str(e)}")
        return False, errors
    
    # 2. Validate AWS credentials for each environment
    for env in config.environments:
        try:
            validate_aws_credentials(account_id=env.account, region=env.region)
        except ValidationError as e:
            errors.append(f"AWS credential validation failed for {env.name}: {str(e)}")
    
    # 3. Validate CDK context if requirements provided
    if context_requirements:
        try:
            validate_cdk_context(context_requirements, cdk_json_path)
        except ValidationError as e:
            errors.append(f"CDK context validation failed: {str(e)}")
    
    # 4. Validate build tools
    # Extract tool names from build commands (simple heuristic)
    build_tools = set()
    for cmd in config.build.commands:
        # Get the first word of each command
        tool = cmd.split()[0] if cmd.split() else None
        if tool:
            build_tools.add(tool)
    
    if build_tools:
        try:
            validate_build_tools(list(build_tools))
        except ValidationError as e:
            errors.append(f"Build tool validation failed: {str(e)}")
    
    # Return success if no errors
    return len(errors) == 0, errors
