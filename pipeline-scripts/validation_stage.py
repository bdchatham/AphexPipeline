#!/usr/bin/env python3
"""
Validation stage for AphexPipeline workflows.

This script performs all validation checks before workflow execution begins:
- Configuration schema validation
- AWS credential validation
- CDK context validation
- Build tool validation

If any validation fails, the script exits with a non-zero status code and
provides clear error messages.
"""

import sys
import argparse
from pathlib import Path
from typing import List, Optional

from config_parser import parse_config
from validation import (
    validate_aws_credentials,
    validate_cdk_context,
    validate_build_tools,
    ValidationError
)


def main():
    """Main entry point for validation stage."""
    parser = argparse.ArgumentParser(
        description='Validate AphexPipeline configuration and environment before workflow execution'
    )
    parser.add_argument(
        '--config',
        type=str,
        default='aphex-config.yaml',
        help='Path to aphex-config.yaml file (default: aphex-config.yaml)'
    )
    parser.add_argument(
        '--schema',
        type=str,
        default='aphex-config.schema.json',
        help='Path to JSON schema file (default: aphex-config.schema.json)'
    )
    parser.add_argument(
        '--cdk-json',
        type=str,
        default='cdk.json',
        help='Path to cdk.json file (default: cdk.json)'
    )
    parser.add_argument(
        '--context-requirements',
        type=str,
        nargs='*',
        help='Required CDK context keys (space-separated)'
    )
    parser.add_argument(
        '--skip-aws-validation',
        action='store_true',
        help='Skip AWS credential validation (useful for local testing)'
    )
    parser.add_argument(
        '--skip-cdk-validation',
        action='store_true',
        help='Skip CDK context validation'
    )
    parser.add_argument(
        '--skip-tool-validation',
        action='store_true',
        help='Skip build tool validation'
    )
    
    args = parser.parse_args()
    
    errors = []
    
    print("=" * 80)
    print("AphexPipeline Validation Stage")
    print("=" * 80)
    print()
    
    # 1. Validate configuration schema
    print("1. Validating configuration schema...")
    try:
        config = parse_config(args.config, args.schema)
        print(f"   ✓ Configuration is valid")
        print(f"   - Version: {config.version}")
        print(f"   - Build commands: {len(config.build.commands)}")
        print(f"   - Environments: {len(config.environments)}")
        for env in config.environments:
            print(f"     - {env.name}: {env.region} ({env.account}), {len(env.stacks)} stacks")
    except FileNotFoundError as e:
        error_msg = f"Configuration file not found: {str(e)}"
        print(f"   ✗ {error_msg}")
        errors.append(error_msg)
        # Cannot continue without config
        print_summary(errors)
        sys.exit(1)
    except Exception as e:
        error_msg = f"Configuration validation failed: {str(e)}"
        print(f"   ✗ {error_msg}")
        errors.append(error_msg)
        # Cannot continue without valid config
        print_summary(errors)
        sys.exit(1)
    
    print()
    
    # 2. Validate AWS credentials for each environment
    if not args.skip_aws_validation:
        print("2. Validating AWS credentials...")
        for env in config.environments:
            try:
                validate_aws_credentials(account_id=env.account, region=env.region)
                print(f"   ✓ Credentials valid for {env.name} ({env.account})")
            except ValidationError as e:
                error_msg = f"AWS credential validation failed for {env.name}: {str(e)}"
                print(f"   ✗ {error_msg}")
                errors.append(error_msg)
    else:
        print("2. Skipping AWS credential validation (--skip-aws-validation)")
    
    print()
    
    # 3. Validate CDK context if requirements provided
    if not args.skip_cdk_validation and args.context_requirements:
        print("3. Validating CDK context...")
        try:
            validate_cdk_context(args.context_requirements, args.cdk_json)
            print(f"   ✓ All required CDK context values present")
            for key in args.context_requirements:
                print(f"     - {key}")
        except ValidationError as e:
            error_msg = f"CDK context validation failed: {str(e)}"
            print(f"   ✗ {error_msg}")
            errors.append(error_msg)
    elif args.skip_cdk_validation:
        print("3. Skipping CDK context validation (--skip-cdk-validation)")
    else:
        print("3. Skipping CDK context validation (no requirements specified)")
    
    print()
    
    # 4. Validate build tools
    if not args.skip_tool_validation:
        print("4. Validating build tools...")
        
        # Extract tool names from build commands
        build_tools = set()
        for cmd in config.build.commands:
            # Get the first word of each command
            tool = cmd.split()[0] if cmd.split() else None
            if tool:
                build_tools.add(tool)
        
        if build_tools:
            try:
                validate_build_tools(list(build_tools))
                print(f"   ✓ All required build tools available")
                for tool in sorted(build_tools):
                    print(f"     - {tool}")
            except ValidationError as e:
                error_msg = f"Build tool validation failed: {str(e)}"
                print(f"   ✗ {error_msg}")
                errors.append(error_msg)
        else:
            print("   ⚠ No build tools to validate")
    else:
        print("4. Skipping build tool validation (--skip-tool-validation)")
    
    print()
    
    # Print summary and exit
    print_summary(errors)
    
    if errors:
        sys.exit(1)
    else:
        sys.exit(0)


def print_summary(errors: List[str]):
    """Print validation summary."""
    print("=" * 80)
    print("Validation Summary")
    print("=" * 80)
    
    if errors:
        print(f"✗ Validation FAILED with {len(errors)} error(s):")
        print()
        for i, error in enumerate(errors, 1):
            print(f"{i}. {error}")
        print()
        print("Please fix the errors above before running the workflow.")
    else:
        print("✓ All validations PASSED")
        print()
        print("The workflow is ready to execute.")
    
    print("=" * 80)


if __name__ == '__main__':
    main()
