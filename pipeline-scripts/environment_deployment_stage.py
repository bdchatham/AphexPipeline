"""
Environment deployment stage script for AphexPipeline.

This module provides functionality to execute environment deployment stages:
- Clone repository at specific commit SHA
- Download artifacts from S3
- Set AWS region and account context
- Synthesize Application CDK Stacks just-in-time
- Deploy stacks in configured order
- Capture stack outputs
"""

import os
import subprocess
import sys
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
import boto3
from botocore.exceptions import ClientError

from config_parser import StackConfig, EnvironmentConfig


def get_current_account_id() -> str:
    """
    Get the current AWS account ID.
    
    Returns:
        Current AWS account ID
        
    Raises:
        EnvironmentDeploymentError: If unable to get account ID
    """
    try:
        sts_client = boto3.client('sts')
        response = sts_client.get_caller_identity()
        return response['Account']
    except Exception as e:
        raise EnvironmentDeploymentError(f"Failed to get current account ID: {str(e)}") from e


def assume_cross_account_role(
    target_account: str,
    role_name: str = "AphexPipelineCrossAccountRole",
    session_name: str = "AphexPipelineSession"
) -> Dict[str, str]:
    """
    Assume a cross-account IAM role and return temporary credentials.
    
    Args:
        target_account: Target AWS account ID
        role_name: Name of the role to assume in the target account
        session_name: Session name for the assumed role
        
    Returns:
        Dictionary with AWS credentials (AccessKeyId, SecretAccessKey, SessionToken)
        
    Raises:
        EnvironmentDeploymentError: If role assumption fails
    """
    try:
        role_arn = f"arn:aws:iam::{target_account}:role/{role_name}"
        
        print(f"Assuming cross-account role: {role_arn}")
        
        sts_client = boto3.client('sts')
        response = sts_client.assume_role(
            RoleArn=role_arn,
            RoleSessionName=session_name
        )
        
        credentials = response['Credentials']
        
        print(f"Successfully assumed role in account {target_account}")
        
        return {
            'AccessKeyId': credentials['AccessKeyId'],
            'SecretAccessKey': credentials['SecretAccessKey'],
            'SessionToken': credentials['SessionToken']
        }
        
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')
        error_msg = e.response.get('Error', {}).get('Message', '')
        
        raise EnvironmentDeploymentError(
            f"Failed to assume cross-account role {role_arn}: {error_code} - {error_msg}"
        ) from e
    except Exception as e:
        raise EnvironmentDeploymentError(
            f"Failed to assume cross-account role: {str(e)}"
        ) from e


class EnvironmentDeploymentError(Exception):
    """Exception raised when environment deployment stage fails."""
    pass


@dataclass
class StackOutput:
    """Represents a CloudFormation stack output."""
    output_key: str
    output_value: str
    description: Optional[str] = None
    export_name: Optional[str] = None


@dataclass
class StackDeploymentResult:
    """Result of deploying a single stack."""
    stack_name: str
    status: str  # "success" or "failed"
    outputs: List[StackOutput]
    error_message: Optional[str] = None


@dataclass
class EnvironmentDeploymentResult:
    """Result of deploying an entire environment."""
    environment_name: str
    region: str
    account: str
    commit_sha: str
    stack_results: List[StackDeploymentResult]
    status: str  # "success" or "failed"


class EnvironmentDeploymentStage:
    """Handles the environment deployment stage execution."""
    
    def __init__(
        self,
        repo_url: str,
        commit_sha: str,
        environment: EnvironmentConfig,
        artifact_path: Optional[str] = None,
        workspace_dir: str = "/workspace",
        artifacts_dir: str = "/workspace/artifacts",
        cross_account_role_name: str = "AphexPipelineCrossAccountRole"
    ):
        """
        Initialize the environment deployment stage.
        
        Args:
            repo_url: Git repository URL to clone
            commit_sha: Specific commit SHA to checkout
            environment: Environment configuration
            artifact_path: S3 path to artifacts (e.g., s3://bucket/commit-sha/)
            workspace_dir: Directory to clone repository into
            artifacts_dir: Directory to download artifacts to
            cross_account_role_name: Name of the cross-account role to assume
        """
        self.repo_url = repo_url
        self.commit_sha = commit_sha
        self.environment = environment
        self.artifact_path = artifact_path
        self.workspace_dir = Path(workspace_dir)
        self.artifacts_dir = Path(artifacts_dir)
        self.cross_account_role_name = cross_account_role_name
        self.stack_results: List[StackDeploymentResult] = []
        self.current_account_id: Optional[str] = None
        self.assumed_credentials: Optional[Dict[str, str]] = None
        
    def clone_repository(self) -> None:
        """
        Clone the repository at the specific commit SHA.
        
        Raises:
            EnvironmentDeploymentError: If cloning or checkout fails
        """
        try:
            # Create workspace directory if it doesn't exist
            self.workspace_dir.mkdir(parents=True, exist_ok=True)
            
            # Clone the repository
            print(f"Cloning repository: {self.repo_url}")
            result = subprocess.run(
                ["git", "clone", self.repo_url, str(self.workspace_dir)],
                capture_output=True,
                text=True,
                check=True
            )
            print(result.stdout)
            
            # Checkout specific commit
            print(f"Checking out commit: {self.commit_sha}")
            result = subprocess.run(
                ["git", "checkout", self.commit_sha],
                cwd=str(self.workspace_dir),
                capture_output=True,
                text=True,
                check=True
            )
            print(result.stdout)
            
            # Verify we're at the correct commit
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(self.workspace_dir),
                capture_output=True,
                text=True,
                check=True
            )
            actual_sha = result.stdout.strip()
            
            if actual_sha != self.commit_sha:
                raise EnvironmentDeploymentError(
                    f"Failed to checkout correct commit. "
                    f"Expected: {self.commit_sha}, Got: {actual_sha}"
                )
            
            print(f"Successfully cloned and checked out commit {self.commit_sha}")
            
        except subprocess.CalledProcessError as e:
            error_msg = f"Git operation failed: {e.stderr}"
            print(error_msg, file=sys.stderr)
            raise EnvironmentDeploymentError(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to clone repository: {str(e)}"
            print(error_msg, file=sys.stderr)
            raise EnvironmentDeploymentError(error_msg) from e
    
    def download_artifacts_from_s3(self) -> None:
        """
        Download artifacts from S3 to local artifacts directory.
        
        Raises:
            EnvironmentDeploymentError: If S3 download fails
        """
        if not self.artifact_path:
            print("No artifact path specified, skipping artifact download")
            return
        
        try:
            # Parse S3 path
            if not self.artifact_path.startswith('s3://'):
                raise EnvironmentDeploymentError(
                    f"Invalid S3 path: {self.artifact_path}. Must start with s3://"
                )
            
            # Extract bucket and prefix
            s3_path_parts = self.artifact_path[5:].split('/', 1)
            bucket_name = s3_path_parts[0]
            prefix = s3_path_parts[1] if len(s3_path_parts) > 1 else ""
            
            print(f"Downloading artifacts from {self.artifact_path}")
            
            # Create artifacts directory
            self.artifacts_dir.mkdir(parents=True, exist_ok=True)
            
            # Create S3 client
            s3_client = boto3.client('s3', region_name=self.environment.region)
            
            # List objects in the prefix
            paginator = s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=bucket_name, Prefix=prefix)
            
            downloaded_count = 0
            for page in pages:
                if 'Contents' not in page:
                    continue
                
                for obj in page['Contents']:
                    s3_key = obj['Key']
                    
                    # Skip if it's just the prefix (directory marker)
                    if s3_key == prefix or s3_key.endswith('/'):
                        continue
                    
                    # Get relative path from prefix
                    relative_path = s3_key[len(prefix):].lstrip('/')
                    local_file = self.artifacts_dir / relative_path
                    
                    # Create parent directories
                    local_file.parent.mkdir(parents=True, exist_ok=True)
                    
                    # Download file
                    print(f"Downloading {s3_key} to {local_file}")
                    s3_client.download_file(bucket_name, s3_key, str(local_file))
                    downloaded_count += 1
            
            if downloaded_count == 0:
                print(f"Warning: No artifacts found at {self.artifact_path}")
            else:
                print(f"Successfully downloaded {downloaded_count} artifact(s)")
            
        except ClientError as e:
            error_msg = f"S3 download failed: {e}"
            print(error_msg, file=sys.stderr)
            raise EnvironmentDeploymentError(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to download artifacts from S3: {str(e)}"
            print(error_msg, file=sys.stderr)
            raise EnvironmentDeploymentError(error_msg) from e
    
    def detect_and_assume_cross_account_role(self) -> None:
        """
        Detect if deploying to a different AWS account and assume cross-account role if needed.
        
        This method:
        1. Gets the current AWS account ID
        2. Compares it with the target environment account
        3. If different, assumes the configured cross-account role
        4. Sets AWS credentials environment variables for the assumed role
        
        Raises:
            EnvironmentDeploymentError: If cross-account role assumption fails
        """
        try:
            # Get current account ID
            self.current_account_id = get_current_account_id()
            print(f"Current AWS account: {self.current_account_id}")
            print(f"Target AWS account: {self.environment.account}")
            
            # Check if we need to assume a cross-account role
            if self.current_account_id != self.environment.account:
                print(f"\nCross-account deployment detected!")
                print(f"Assuming role in target account {self.environment.account}...")
                
                # Assume the cross-account role
                self.assumed_credentials = assume_cross_account_role(
                    target_account=self.environment.account,
                    role_name=self.cross_account_role_name,
                    session_name=f"AphexPipeline-{self.environment.name}"
                )
                
                # Set AWS credentials environment variables
                os.environ['AWS_ACCESS_KEY_ID'] = self.assumed_credentials['AccessKeyId']
                os.environ['AWS_SECRET_ACCESS_KEY'] = self.assumed_credentials['SecretAccessKey']
                os.environ['AWS_SESSION_TOKEN'] = self.assumed_credentials['SessionToken']
                
                print(f"Successfully configured credentials for account {self.environment.account}")
            else:
                print(f"Same-account deployment - no role assumption needed")
                
        except EnvironmentDeploymentError:
            raise
        except Exception as e:
            error_msg = f"Failed to detect or assume cross-account role: {str(e)}"
            print(error_msg, file=sys.stderr)
            raise EnvironmentDeploymentError(error_msg) from e
    
    def set_aws_context(self) -> None:
        """
        Set AWS region and account context for deployment.
        
        This sets environment variables that CDK will use.
        """
        print(f"\nSetting AWS context:")
        print(f"  Region: {self.environment.region}")
        print(f"  Account: {self.environment.account}")
        
        os.environ['AWS_REGION'] = self.environment.region
        os.environ['AWS_DEFAULT_REGION'] = self.environment.region
        os.environ['CDK_DEFAULT_REGION'] = self.environment.region
        os.environ['CDK_DEFAULT_ACCOUNT'] = self.environment.account
        
        print("AWS context set successfully")
    
    def synthesize_cdk_stack(self, stack: StackConfig) -> None:
        """
        Synthesize a single Application CDK Stack just-in-time.
        
        This uses the commit-specific CDK code to synthesize the stack
        immediately before deployment.
        
        Args:
            stack: Stack configuration
            
        Raises:
            EnvironmentDeploymentError: If synthesis fails
        """
        try:
            print(f"\nSynthesizing stack: {stack.name}")
            print(f"  Stack path: {stack.path}")
            
            # Determine the CDK app directory
            # If stack.path is specified, use it; otherwise use workspace root
            cdk_app_dir = self.workspace_dir
            if stack.path and stack.path != ".":
                cdk_app_dir = self.workspace_dir / stack.path
            
            if not cdk_app_dir.exists():
                raise EnvironmentDeploymentError(
                    f"CDK app directory not found: {cdk_app_dir}"
                )
            
            # Install dependencies if package.json exists
            package_json = cdk_app_dir / "package.json"
            if package_json.exists():
                print(f"Installing dependencies in {cdk_app_dir}...")
                result = subprocess.run(
                    ["npm", "install"],
                    cwd=str(cdk_app_dir),
                    capture_output=True,
                    text=True,
                    check=True
                )
                if result.stdout:
                    print(result.stdout)
            
            # Synthesize the stack
            print(f"Running CDK synth for {stack.name}...")
            result = subprocess.run(
                ["npx", "cdk", "synth", stack.name],
                cwd=str(cdk_app_dir),
                capture_output=True,
                text=True,
                check=True,
                env={**os.environ}  # Pass through environment variables
            )
            
            # Print synthesis output
            if result.stdout:
                print(result.stdout)
            
            print(f"Stack {stack.name} synthesized successfully")
            
        except subprocess.CalledProcessError as e:
            error_msg = (
                f"CDK synthesis failed for stack {stack.name}\n"
                f"Exit code: {e.returncode}\n"
                f"Stdout: {e.stdout}\n"
                f"Stderr: {e.stderr}"
            )
            print(error_msg, file=sys.stderr)
            raise EnvironmentDeploymentError(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to synthesize stack {stack.name}: {str(e)}"
            print(error_msg, file=sys.stderr)
            raise EnvironmentDeploymentError(error_msg) from e
    
    def synthesize_all_stacks(self) -> None:
        """
        Synthesize all Application CDK Stacks for the environment.
        
        This synthesizes each stack just-in-time using the commit-specific
        CDK code before any deployments occur.
        
        Raises:
            EnvironmentDeploymentError: If any synthesis fails
        """
        print(f"\n=== Synthesizing {len(self.environment.stacks)} stack(s) for environment {self.environment.name} ===")
        
        for i, stack in enumerate(self.environment.stacks, 1):
            print(f"\n[{i}/{len(self.environment.stacks)}] Synthesizing {stack.name}...")
            self.synthesize_cdk_stack(stack)
        
        print(f"\n=== All stacks synthesized successfully ===")
    
    def deploy_cdk_stack(self, stack: StackConfig) -> StackDeploymentResult:
        """
        Deploy a single Application CDK Stack.
        
        This method supports two cross-account deployment strategies:
        1. CDK Native: Uses CDK bootstrap roles with --role-arn (recommended)
        2. Custom: Uses assumed role credentials via environment variables
        
        Args:
            stack: Stack configuration
            
        Returns:
            StackDeploymentResult with deployment status and outputs
            
        Raises:
            EnvironmentDeploymentError: If deployment fails
        """
        try:
            print(f"\nDeploying stack: {stack.name}")
            
            # Determine the CDK app directory
            cdk_app_dir = self.workspace_dir
            if stack.path and stack.path != ".":
                cdk_app_dir = self.workspace_dir / stack.path
            
            # Build CDK deploy command
            cdk_command = ["npx", "cdk", "deploy", stack.name, "--require-approval", "never"]
            
            # If cross-account deployment with assumed credentials, use CDK's native role assumption
            # This aligns with CDK bootstrap pattern
            if self.assumed_credentials:
                # Use CDK's deployment role from bootstrap
                # Format: cdk-hnb659fds-deploy-role-{account}-{region}
                deploy_role_arn = f"arn:aws:iam::{self.environment.account}:role/cdk-hnb659fds-deploy-role-{self.environment.account}-{self.environment.region}"
                cdk_command.extend(["--role-arn", deploy_role_arn])
                print(f"Using CDK bootstrap deployment role: {deploy_role_arn}")
            
            # Deploy the stack
            print(f"Running CDK deploy for {stack.name}...")
            result = subprocess.run(
                cdk_command,
                cwd=str(cdk_app_dir),
                capture_output=True,
                text=True,
                check=True,
                env={**os.environ}
            )
            
            # Print deployment output
            if result.stdout:
                print(result.stdout)
            
            print(f"Stack {stack.name} deployed successfully")
            
            # Capture stack outputs
            outputs = self.capture_stack_outputs(stack.name)
            
            return StackDeploymentResult(
                stack_name=stack.name,
                status="success",
                outputs=outputs
            )
            
        except subprocess.CalledProcessError as e:
            error_msg = (
                f"CDK deployment failed for stack {stack.name}\n"
                f"Exit code: {e.returncode}\n"
                f"Stdout: {e.stdout}\n"
                f"Stderr: {e.stderr}"
            )
            print(error_msg, file=sys.stderr)
            
            return StackDeploymentResult(
                stack_name=stack.name,
                status="failed",
                outputs=[],
                error_message=error_msg
            )
        except Exception as e:
            error_msg = f"Failed to deploy stack {stack.name}: {str(e)}"
            print(error_msg, file=sys.stderr)
            
            return StackDeploymentResult(
                stack_name=stack.name,
                status="failed",
                outputs=[],
                error_message=error_msg
            )
    
    def deploy_stacks_in_order(self) -> List[StackDeploymentResult]:
        """
        Deploy all stacks in the configured order.
        
        Waits for each stack to complete before deploying the next.
        Halts on first failure.
        
        Returns:
            List of StackDeploymentResult for each stack
            
        Raises:
            EnvironmentDeploymentError: If any stack deployment fails
        """
        print(f"\n=== Deploying {len(self.environment.stacks)} stack(s) in order ===")
        
        results = []
        
        for i, stack in enumerate(self.environment.stacks, 1):
            print(f"\n[{i}/{len(self.environment.stacks)}] Deploying {stack.name}...")
            
            result = self.deploy_cdk_stack(stack)
            results.append(result)
            
            if result.status == "failed":
                error_msg = f"Stack deployment failed: {stack.name}. Halting deployment."
                print(error_msg, file=sys.stderr)
                raise EnvironmentDeploymentError(error_msg)
            
            print(f"[{i}/{len(self.environment.stacks)}] Stack {stack.name} deployed successfully")
        
        print(f"\n=== All stacks deployed successfully ===")
        return results
    
    def capture_stack_outputs(self, stack_name: str) -> List[StackOutput]:
        """
        Query CloudFormation for stack outputs and capture them.
        
        Args:
            stack_name: Name of the CloudFormation stack
            
        Returns:
            List of StackOutput objects
        """
        try:
            print(f"Capturing outputs for stack: {stack_name}")
            
            # Create CloudFormation client
            cfn_client = boto3.client('cloudformation', region_name=self.environment.region)
            
            # Describe the stack
            response = cfn_client.describe_stacks(StackName=stack_name)
            
            if not response['Stacks']:
                print(f"Warning: Stack {stack_name} not found")
                return []
            
            stack = response['Stacks'][0]
            outputs_data = stack.get('Outputs', [])
            
            if not outputs_data:
                print(f"Stack {stack_name} has no outputs")
                return []
            
            # Convert to StackOutput objects
            outputs = []
            for output in outputs_data:
                stack_output = StackOutput(
                    output_key=output['OutputKey'],
                    output_value=output['OutputValue'],
                    description=output.get('Description'),
                    export_name=output.get('ExportName')
                )
                outputs.append(stack_output)
                
                print(f"  {output['OutputKey']}: {output['OutputValue']}")
            
            print(f"Captured {len(outputs)} output(s) from stack {stack_name}")
            return outputs
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            
            # If stack doesn't exist, return empty list
            if error_code == 'ValidationError':
                print(f"Warning: Stack {stack_name} not found in CloudFormation")
                return []
            
            print(f"Warning: Failed to capture outputs for stack {stack_name}: {e}", file=sys.stderr)
            return []
        except Exception as e:
            print(f"Warning: Failed to capture outputs for stack {stack_name}: {str(e)}", file=sys.stderr)
            return []
    
    def save_outputs_to_file(self, output_file: str = "/tmp/stack-outputs.json") -> None:
        """
        Save all captured stack outputs to a JSON file.
        
        Args:
            output_file: Path to output file
        """
        try:
            # Consolidate all outputs
            all_outputs = {}
            for result in self.stack_results:
                stack_outputs = {}
                for output in result.outputs:
                    stack_outputs[output.output_key] = {
                        'value': output.output_value,
                        'description': output.description,
                        'export_name': output.export_name
                    }
                all_outputs[result.stack_name] = stack_outputs
            
            # Write to file
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w') as f:
                json.dump(all_outputs, f, indent=2)
            
            print(f"\nStack outputs saved to {output_file}")
            
        except Exception as e:
            print(f"Warning: Failed to save outputs to file: {str(e)}", file=sys.stderr)
    
    def capture_cloudformation_error_events(self, stack_name: str) -> List[Dict[str, Any]]:
        """
        Capture CloudFormation error events for a failed stack deployment.
        
        Args:
            stack_name: Name of the CloudFormation stack
            
        Returns:
            List of error events
        """
        try:
            print(f"Capturing error events for stack: {stack_name}")
            
            cfn_client = boto3.client('cloudformation', region_name=self.environment.region)
            
            # Get stack events
            paginator = cfn_client.get_paginator('describe_stack_events')
            pages = paginator.paginate(StackName=stack_name)
            
            error_events = []
            for page in pages:
                for event in page['StackEvents']:
                    # Capture events with FAILED status
                    if 'FAILED' in event.get('ResourceStatus', ''):
                        error_event = {
                            'timestamp': event['Timestamp'].isoformat(),
                            'resource_type': event.get('ResourceType', ''),
                            'logical_resource_id': event.get('LogicalResourceId', ''),
                            'resource_status': event.get('ResourceStatus', ''),
                            'resource_status_reason': event.get('ResourceStatusReason', '')
                        }
                        error_events.append(error_event)
                        
                        print(f"  Error: {event.get('LogicalResourceId')} - {event.get('ResourceStatusReason')}")
            
            return error_events
            
        except ClientError as e:
            print(f"Warning: Failed to capture error events: {e}", file=sys.stderr)
            return []
        except Exception as e:
            print(f"Warning: Failed to capture error events: {str(e)}", file=sys.stderr)
            return []
    
    def save_error_details(self, stack_name: str, error_message: str, error_file: str = "/tmp/deployment-error.json") -> None:
        """
        Save error details to a file for debugging.
        
        Args:
            stack_name: Name of the failed stack
            error_message: Error message
            error_file: Path to error file
        """
        try:
            # Capture CloudFormation error events
            error_events = self.capture_cloudformation_error_events(stack_name)
            
            error_details = {
                'environment': self.environment.name,
                'stack_name': stack_name,
                'region': self.environment.region,
                'account': self.environment.account,
                'commit_sha': self.commit_sha,
                'error_message': error_message,
                'cloudformation_events': error_events
            }
            
            # Write to file
            error_path = Path(error_file)
            error_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(error_path, 'w') as f:
                json.dump(error_details, f, indent=2)
            
            print(f"Error details saved to {error_file}", file=sys.stderr)
            
        except Exception as e:
            print(f"Warning: Failed to save error details: {str(e)}", file=sys.stderr)
    
    def run(self) -> EnvironmentDeploymentResult:
        """
        Execute the complete environment deployment stage.
        
        Returns:
            EnvironmentDeploymentResult with deployment status
            
        Raises:
            EnvironmentDeploymentError: If any critical stage fails
        """
        try:
            print(f"\n{'='*80}")
            print(f"Environment Deployment Stage: {self.environment.name}")
            print(f"Region: {self.environment.region}")
            print(f"Account: {self.environment.account}")
            print(f"Commit SHA: {self.commit_sha}")
            print(f"{'='*80}\n")
            
            # Step 1: Clone repository at specific commit
            self.clone_repository()
            
            # Step 2: Download artifacts from S3
            if self.artifact_path:
                self.download_artifacts_from_s3()
            
            # Step 3: Detect cross-account deployment and assume role if needed
            self.detect_and_assume_cross_account_role()
            
            # Step 4: Set AWS region and account context
            self.set_aws_context()
            
            # Step 5: Synthesize all Application CDK Stacks just-in-time
            self.synthesize_all_stacks()
            
            # Step 6: Deploy stacks in configured order
            self.stack_results = self.deploy_stacks_in_order()
            
            # Step 7: Save outputs to file
            self.save_outputs_to_file()
            
            print(f"\n{'='*80}")
            print(f"Environment {self.environment.name} deployment completed successfully")
            print(f"{'='*80}\n")
            
            return EnvironmentDeploymentResult(
                environment_name=self.environment.name,
                region=self.environment.region,
                account=self.environment.account,
                commit_sha=self.commit_sha,
                stack_results=self.stack_results,
                status="success"
            )
            
        except EnvironmentDeploymentError as e:
            print(f"\n{'='*80}", file=sys.stderr)
            print(f"Environment {self.environment.name} deployment failed", file=sys.stderr)
            print(f"{'='*80}\n", file=sys.stderr)
            
            # Try to save error details
            if self.stack_results:
                failed_stack = next((r for r in self.stack_results if r.status == "failed"), None)
                if failed_stack:
                    self.save_error_details(failed_stack.stack_name, str(e))
            
            return EnvironmentDeploymentResult(
                environment_name=self.environment.name,
                region=self.environment.region,
                account=self.environment.account,
                commit_sha=self.commit_sha,
                stack_results=self.stack_results,
                status="failed"
            )


def main():
    """
    Main entry point for the environment deployment stage script.
    
    Expected environment variables:
    - REPO_URL: Git repository URL
    - COMMIT_SHA: Commit SHA to checkout
    - ENVIRONMENT_NAME: Name of the environment to deploy
    - ENVIRONMENT_REGION: AWS region for the environment
    - ENVIRONMENT_ACCOUNT: AWS account for the environment
    - ENVIRONMENT_STACKS: JSON array of stack configurations
    - ARTIFACT_PATH: (Optional) S3 path to artifacts
    """
    # Get parameters from environment variables
    repo_url = os.environ.get('REPO_URL')
    commit_sha = os.environ.get('COMMIT_SHA')
    env_name = os.environ.get('ENVIRONMENT_NAME')
    env_region = os.environ.get('ENVIRONMENT_REGION')
    env_account = os.environ.get('ENVIRONMENT_ACCOUNT')
    env_stacks_json = os.environ.get('ENVIRONMENT_STACKS', '[]')
    artifact_path = os.environ.get('ARTIFACT_PATH')
    
    if not repo_url:
        print("Error: REPO_URL environment variable not set", file=sys.stderr)
        sys.exit(1)
    
    if not commit_sha:
        print("Error: COMMIT_SHA environment variable not set", file=sys.stderr)
        sys.exit(1)
    
    if not env_name:
        print("Error: ENVIRONMENT_NAME environment variable not set", file=sys.stderr)
        sys.exit(1)
    
    if not env_region:
        print("Error: ENVIRONMENT_REGION environment variable not set", file=sys.stderr)
        sys.exit(1)
    
    if not env_account:
        print("Error: ENVIRONMENT_ACCOUNT environment variable not set", file=sys.stderr)
        sys.exit(1)
    
    try:
        stacks_data = json.loads(env_stacks_json)
        stacks = [StackConfig(name=s['name'], path=s.get('path', '.')) for s in stacks_data]
    except json.JSONDecodeError as e:
        print(f"Error: Invalid ENVIRONMENT_STACKS JSON: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Create environment configuration
    environment = EnvironmentConfig(
        name=env_name,
        region=env_region,
        account=env_account,
        stacks=stacks,
        tests=None  # Tests are handled separately
    )
    
    # Create and run environment deployment stage
    stage = EnvironmentDeploymentStage(
        repo_url=repo_url,
        commit_sha=commit_sha,
        environment=environment,
        artifact_path=artifact_path
    )
    
    try:
        result = stage.run()
        
        if result.status == "success":
            print(f"\nDeployment successful for environment: {env_name}")
            sys.exit(0)
        else:
            print(f"\nDeployment failed for environment: {env_name}", file=sys.stderr)
            sys.exit(1)
            
    except Exception as e:
        print(f"\nUnexpected error: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
