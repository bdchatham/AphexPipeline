"""
Pipeline deployment stage script for AphexPipeline.

This module provides functionality to execute the pipeline deployment stage:
- Clone repository at specific commit SHA
- Synthesize Pipeline CDK Stack
- Deploy Pipeline CDK Stack
- Read aphex-config.yaml
- Generate and apply updated WorkflowTemplate
"""

import os
import subprocess
import sys
import json
from pathlib import Path
from typing import Optional
import yaml
import boto3
from botocore.exceptions import ClientError

from config_parser import ConfigParser, AphexConfig


class PipelineDeploymentError(Exception):
    """Exception raised when pipeline deployment stage fails."""
    pass


class PipelineDeploymentStage:
    """Handles the pipeline deployment stage execution."""
    
    def __init__(
        self,
        repo_url: str,
        commit_sha: str,
        workspace_dir: str = "/workspace",
        config_file: str = "aphex-config.yaml",
        schema_file: str = "aphex-config.schema.json"
    ):
        """
        Initialize the pipeline deployment stage.
        
        Args:
            repo_url: Git repository URL to clone
            commit_sha: Specific commit SHA to checkout
            workspace_dir: Directory to clone repository into
            config_file: Path to configuration file (relative to workspace)
            schema_file: Path to schema file (relative to workspace)
        """
        self.repo_url = repo_url
        self.commit_sha = commit_sha
        self.workspace_dir = Path(workspace_dir)
        self.config_file = config_file
        self.schema_file = schema_file
        self.config: Optional[AphexConfig] = None
        
    def clone_repository(self) -> None:
        """
        Clone the repository at the specific commit SHA.
        
        Raises:
            PipelineDeploymentError: If cloning or checkout fails
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
                raise PipelineDeploymentError(
                    f"Failed to checkout correct commit. "
                    f"Expected: {self.commit_sha}, Got: {actual_sha}"
                )
            
            print(f"Successfully cloned and checked out commit {self.commit_sha}")
            
        except subprocess.CalledProcessError as e:
            error_msg = f"Git operation failed: {e.stderr}"
            print(error_msg, file=sys.stderr)
            raise PipelineDeploymentError(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to clone repository: {str(e)}"
            print(error_msg, file=sys.stderr)
            raise PipelineDeploymentError(error_msg) from e
    
    def synthesize_pipeline_stack(self) -> None:
        """
        Synthesize the Pipeline CDK Stack.
        
        Raises:
            PipelineDeploymentError: If synthesis fails
        """
        try:
            pipeline_infra_dir = self.workspace_dir / "pipeline-infra"
            
            if not pipeline_infra_dir.exists():
                raise PipelineDeploymentError(
                    f"Pipeline infrastructure directory not found: {pipeline_infra_dir}"
                )
            
            print("Installing pipeline infrastructure dependencies...")
            result = subprocess.run(
                ["npm", "install"],
                cwd=str(pipeline_infra_dir),
                capture_output=True,
                text=True,
                check=True
            )
            if result.stdout:
                print(result.stdout)
            
            print("Synthesizing Pipeline CDK Stack...")
            result = subprocess.run(
                ["npx", "cdk", "synth", "AphexPipelineStack"],
                cwd=str(pipeline_infra_dir),
                capture_output=True,
                text=True,
                check=True
            )
            print(result.stdout)
            
            print("Pipeline CDK Stack synthesized successfully")
            
        except subprocess.CalledProcessError as e:
            error_msg = (
                f"CDK synthesis failed\n"
                f"Exit code: {e.returncode}\n"
                f"Stdout: {e.stdout}\n"
                f"Stderr: {e.stderr}"
            )
            print(error_msg, file=sys.stderr)
            raise PipelineDeploymentError(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to synthesize Pipeline CDK Stack: {str(e)}"
            print(error_msg, file=sys.stderr)
            raise PipelineDeploymentError(error_msg) from e
    
    def deploy_pipeline_stack(self) -> None:
        """
        Deploy the Pipeline CDK Stack.
        
        Raises:
            PipelineDeploymentError: If deployment fails
        """
        try:
            pipeline_infra_dir = self.workspace_dir / "pipeline-infra"
            
            print("Deploying Pipeline CDK Stack...")
            result = subprocess.run(
                ["npx", "cdk", "deploy", "AphexPipelineStack", "--require-approval", "never"],
                cwd=str(pipeline_infra_dir),
                capture_output=True,
                text=True,
                check=True
            )
            print(result.stdout)
            
            print("Pipeline CDK Stack deployed successfully")
            
        except subprocess.CalledProcessError as e:
            error_msg = (
                f"CDK deployment failed\n"
                f"Exit code: {e.returncode}\n"
                f"Stdout: {e.stdout}\n"
                f"Stderr: {e.stderr}"
            )
            print(error_msg, file=sys.stderr)
            raise PipelineDeploymentError(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to deploy Pipeline CDK Stack: {str(e)}"
            print(error_msg, file=sys.stderr)
            raise PipelineDeploymentError(error_msg) from e
    
    def read_configuration(self) -> AphexConfig:
        """
        Read and parse the aphex-config.yaml configuration file.
        
        Returns:
            Parsed AphexConfig object
            
        Raises:
            PipelineDeploymentError: If configuration reading or parsing fails
        """
        try:
            config_path = self.workspace_dir / self.config_file
            schema_path = self.workspace_dir / self.schema_file
            
            if not config_path.exists():
                raise PipelineDeploymentError(
                    f"Configuration file not found: {config_path}"
                )
            
            if not schema_path.exists():
                raise PipelineDeploymentError(
                    f"Schema file not found: {schema_path}"
                )
            
            print(f"Reading configuration from {config_path}")
            
            # Parse configuration
            parser = ConfigParser(schema_path=str(schema_path))
            config = parser.parse(str(config_path))
            
            print(f"Configuration parsed successfully")
            print(f"  Version: {config.version}")
            print(f"  Environments: {len(config.environments)}")
            for env in config.environments:
                print(f"    - {env.name} ({env.region}, {env.account})")
            
            self.config = config
            return config
            
        except Exception as e:
            error_msg = f"Failed to read configuration: {str(e)}"
            print(error_msg, file=sys.stderr)
            raise PipelineDeploymentError(error_msg) from e
    
    def generate_workflow_template(self) -> str:
        """
        Generate WorkflowTemplate YAML from configuration.
        
        Returns:
            WorkflowTemplate YAML as string
            
        Raises:
            PipelineDeploymentError: If generation fails
        """
        if not self.config:
            raise PipelineDeploymentError(
                "Configuration not loaded. Call read_configuration() first."
            )
        
        try:
            print("Generating WorkflowTemplate...")
            
            # Get artifact bucket name from CloudFormation outputs
            artifact_bucket = self._get_artifact_bucket_name()
            
            # Generate WorkflowTemplate
            template = self._build_workflow_template(artifact_bucket)
            
            # Convert to YAML
            template_yaml = yaml.dump(template, default_flow_style=False, sort_keys=False)
            
            print(f"WorkflowTemplate generated with {len(self.config.environments)} environment(s)")
            
            return template_yaml
            
        except Exception as e:
            error_msg = f"Failed to generate WorkflowTemplate: {str(e)}"
            print(error_msg, file=sys.stderr)
            raise PipelineDeploymentError(error_msg) from e
    
    def _get_artifact_bucket_name(self) -> str:
        """Get the artifact bucket name from CloudFormation stack outputs."""
        try:
            cfn_client = boto3.client('cloudformation')
            
            response = cfn_client.describe_stacks(StackName='AphexPipelineStack')
            
            if not response['Stacks']:
                raise PipelineDeploymentError("AphexPipelineStack not found")
            
            outputs = response['Stacks'][0].get('Outputs', [])
            
            for output in outputs:
                if output['OutputKey'] == 'ArtifactBucketName':
                    return output['OutputValue']
            
            raise PipelineDeploymentError(
                "ArtifactBucketName output not found in AphexPipelineStack"
            )
            
        except ClientError as e:
            raise PipelineDeploymentError(
                f"Failed to get artifact bucket name: {e}"
            ) from e
    
    def _build_workflow_template(self, artifact_bucket: str) -> dict:
        """Build the WorkflowTemplate manifest."""
        # Generate build stage
        build_stage = self._generate_build_stage(artifact_bucket)
        
        # Generate pipeline deployment stage
        pipeline_stage = self._generate_pipeline_deployment_stage()
        
        # Generate environment stages
        env_stages = []
        for env in self.config.environments:
            env_stages.append(self._generate_environment_stage(env, artifact_bucket))
            if env.tests:
                env_stages.append(self._generate_test_stage(env))
        
        # Build steps list
        steps = [
            [{"name": "build", "template": "build", "arguments": build_stage["arguments"]}],
            [{"name": "pipeline-deployment", "template": "pipeline-deployment", "arguments": pipeline_stage["arguments"]}],
        ]
        
        # Add environment stages
        for i, env in enumerate(self.config.environments):
            env_step = {
                "name": f"deploy-{env.name}",
                "template": f"deploy-{env.name}",
                "arguments": {
                    "parameters": [
                        {"name": "commit-sha", "value": "{{workflow.parameters.commit-sha}}"},
                        {"name": "repo-url", "value": "{{workflow.parameters.repo-url}}"},
                        {"name": "artifact-path", "value": "{{steps.build.outputs.parameters.artifact-path}}"},
                    ]
                }
            }
            steps.append([env_step])
            
            if env.tests:
                test_step = {
                    "name": f"test-{env.name}",
                    "template": f"test-{env.name}",
                    "arguments": {
                        "parameters": [
                            {"name": "commit-sha", "value": "{{workflow.parameters.commit-sha}}"},
                            {"name": "repo-url", "value": "{{workflow.parameters.repo-url}}"},
                            {"name": "stack-outputs", "value": f"{{{{steps.deploy-{env.name}.outputs.parameters.stack-outputs}}}}"},
                        ]
                    }
                }
                steps.append([test_step])
        
        # Build complete template
        template = {
            "apiVersion": "argoproj.io/v1alpha1",
            "kind": "WorkflowTemplate",
            "metadata": {
                "name": "aphex-pipeline-template",
                "namespace": "argo",
            },
            "spec": {
                "serviceAccountName": "workflow-executor",
                "entrypoint": "main",
                "arguments": {
                    "parameters": [
                        {"name": "commit-sha"},
                        {"name": "branch"},
                        {"name": "repo-url"},
                    ]
                },
                "templates": [
                    {
                        "name": "main",
                        "steps": steps,
                    },
                    build_stage,
                    pipeline_stage,
                    *env_stages,
                ],
            },
        }
        
        return template
    
    def _generate_build_stage(self, artifact_bucket: str) -> dict:
        """Generate the build stage template."""
        build_commands = "\n        ".join(self.config.build.commands)
        
        return {
            "name": "build",
            "inputs": {
                "parameters": [
                    {"name": "commit-sha"},
                    {"name": "repo-url"},
                ]
            },
            "outputs": {
                "parameters": [
                    {
                        "name": "artifact-path",
                        "value": f"s3://{artifact_bucket}/{{{{inputs.parameters.commit-sha}}}}/",
                    }
                ]
            },
            "container": {
                "image": "aphex-pipeline/builder:latest",
                "command": ["/bin/bash"],
                "args": [
                    "-c",
                    f"""
        set -e
        echo "Cloning repository..."
        git clone {{{{inputs.parameters.repo-url}}}} /workspace
        cd /workspace
        git checkout {{{{inputs.parameters.commit-sha}}}}
        
        echo "Executing build commands..."
        {build_commands}
        
        echo "Uploading artifacts to S3..."
        if [ -d ./artifacts ]; then
          aws s3 sync ./artifacts s3://{artifact_bucket}/{{{{inputs.parameters.commit-sha}}}}/
        else
          echo "No artifacts directory found, skipping upload"
        fi
        
        echo "Build stage complete"
        """,
                ],
                "env": [
                    {"name": "ARTIFACT_BUCKET", "value": artifact_bucket}
                ],
            },
            "arguments": {
                "parameters": [
                    {"name": "commit-sha", "value": "{{workflow.parameters.commit-sha}}"},
                    {"name": "repo-url", "value": "{{workflow.parameters.repo-url}}"},
                ]
            },
        }
    
    def _generate_pipeline_deployment_stage(self) -> dict:
        """Generate the pipeline deployment stage template."""
        return {
            "name": "pipeline-deployment",
            "inputs": {
                "parameters": [
                    {"name": "commit-sha"},
                    {"name": "repo-url"},
                ]
            },
            "container": {
                "image": "aphex-pipeline/deployer:latest",
                "command": ["/bin/bash"],
                "args": [
                    "-c",
                    """
        set -e
        echo "Cloning repository..."
        git clone {{inputs.parameters.repo-url}} /workspace
        cd /workspace
        git checkout {{inputs.parameters.commit-sha}}
        
        echo "Synthesizing Pipeline CDK Stack..."
        cd pipeline-infra
        npm install
        npx cdk synth AphexPipelineStack
        
        echo "Deploying Pipeline CDK Stack..."
        npx cdk deploy AphexPipelineStack --require-approval never
        
        echo "Reading configuration..."
        cd /workspace
        
        echo "Generating WorkflowTemplate..."
        python3 pipeline-scripts/pipeline_deployment_stage.py --generate-only
        
        echo "Applying WorkflowTemplate..."
        kubectl apply -f /tmp/workflow-template.yaml
        
        echo "Pipeline deployment stage complete"
        """,
                ],
            },
            "arguments": {
                "parameters": [
                    {"name": "commit-sha", "value": "{{workflow.parameters.commit-sha}}"},
                    {"name": "repo-url", "value": "{{workflow.parameters.repo-url}}"},
                ]
            },
        }
    
    def _generate_environment_stage(self, env, artifact_bucket: str) -> dict:
        """Generate a deployment stage for a specific environment."""
        stack_deployments = []
        for stack in env.stacks:
            stack_deployments.append(f"""
        echo "Synthesizing stack: {stack.name}..."
        npx cdk synth {stack.name}
        
        echo "Deploying stack: {stack.name}..."
        npx cdk deploy {stack.name} --require-approval never
        
        echo "Capturing outputs for stack: {stack.name}..."
        aws cloudformation describe-stacks \\
          --stack-name {stack.name} \\
          --region {env.region} \\
          --query 'Stacks[0].Outputs' \\
          > /tmp/{stack.name}-outputs.json || echo "No outputs for {stack.name}"
        """)
        
        stack_deployment_script = "\n        ".join(stack_deployments)
        
        return {
            "name": f"deploy-{env.name}",
            "inputs": {
                "parameters": [
                    {"name": "commit-sha"},
                    {"name": "repo-url"},
                    {"name": "artifact-path"},
                ]
            },
            "outputs": {
                "parameters": [
                    {
                        "name": "stack-outputs",
                        "valueFrom": {"path": "/tmp/stack-outputs.json"},
                    }
                ]
            },
            "container": {
                "image": "aphex-pipeline/deployer:latest",
                "command": ["/bin/bash"],
                "args": [
                    "-c",
                    f"""
        set -e
        echo "Cloning repository..."
        git clone {{{{inputs.parameters.repo-url}}}} /workspace
        cd /workspace
        git checkout {{{{inputs.parameters.commit-sha}}}}
        
        echo "Downloading artifacts from S3..."
        mkdir -p ./artifacts
        aws s3 sync {{{{inputs.parameters.artifact-path}}}} ./artifacts/ || echo "No artifacts to download"
        
        echo "Setting AWS region and account..."
        export AWS_REGION={env.region}
        export AWS_ACCOUNT={env.account}
        
        echo "Installing dependencies..."
        npm install
        
        echo "Deploying stacks for environment: {env.name}..."
        {stack_deployment_script}
        
        echo "Consolidating stack outputs..."
        echo "[]" > /tmp/stack-outputs.json
        
        echo "Environment {env.name} deployment complete"
        """,
                ],
                "env": [
                    {"name": "AWS_REGION", "value": env.region},
                    {"name": "AWS_ACCOUNT", "value": env.account},
                ],
            },
        }
    
    def _generate_test_stage(self, env) -> dict:
        """Generate a test stage for a specific environment."""
        test_commands = "\n        ".join(env.tests.commands)
        
        return {
            "name": f"test-{env.name}",
            "inputs": {
                "parameters": [
                    {"name": "commit-sha"},
                    {"name": "repo-url"},
                    {"name": "stack-outputs"},
                ]
            },
            "container": {
                "image": "aphex-pipeline/deployer:latest",
                "command": ["/bin/bash"],
                "args": [
                    "-c",
                    f"""
        set -e
        echo "Cloning repository..."
        git clone {{{{inputs.parameters.repo-url}}}} /workspace
        cd /workspace
        git checkout {{{{inputs.parameters.commit-sha}}}}
        
        echo "Installing dependencies..."
        npm install
        
        echo "Running tests for environment: {env.name}..."
        {test_commands}
        
        echo "Tests for environment {env.name} complete"
        """,
                ],
                "env": [
                    {"name": "AWS_REGION", "value": env.region},
                    {"name": "STACK_OUTPUTS", "value": "{{inputs.parameters.stack-outputs}}"},
                ],
            },
        }
    
    def apply_workflow_template(self, template_yaml: str) -> None:
        """
        Apply WorkflowTemplate to Argo using kubectl.
        
        Args:
            template_yaml: WorkflowTemplate YAML string
            
        Raises:
            PipelineDeploymentError: If kubectl apply fails
        """
        try:
            # Write template to temporary file
            template_file = Path("/tmp/workflow-template.yaml")
            template_file.write_text(template_yaml)
            
            print(f"Applying WorkflowTemplate to Argo...")
            
            # Apply using kubectl
            result = subprocess.run(
                ["kubectl", "apply", "-f", str(template_file)],
                capture_output=True,
                text=True,
                check=True
            )
            print(result.stdout)
            
            print("WorkflowTemplate applied successfully")
            
        except subprocess.CalledProcessError as e:
            error_msg = (
                f"kubectl apply failed\n"
                f"Exit code: {e.returncode}\n"
                f"Stdout: {e.stdout}\n"
                f"Stderr: {e.stderr}"
            )
            print(error_msg, file=sys.stderr)
            raise PipelineDeploymentError(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to apply WorkflowTemplate: {str(e)}"
            print(error_msg, file=sys.stderr)
            raise PipelineDeploymentError(error_msg) from e
    
    def run(self, continue_on_error: bool = True) -> None:
        """
        Execute the complete pipeline deployment stage.
        
        Args:
            continue_on_error: If True, continue with existing topology on deployment failure
            
        Raises:
            PipelineDeploymentError: If any critical stage fails
        """
        try:
            # Step 1: Clone repository at specific commit
            self.clone_repository()
            
            # Step 2: Synthesize Pipeline CDK Stack
            try:
                self.synthesize_pipeline_stack()
            except PipelineDeploymentError as e:
                if continue_on_error:
                    print(f"Warning: Pipeline synthesis failed, continuing with existing topology: {e}", file=sys.stderr)
                else:
                    raise
            
            # Step 3: Deploy Pipeline CDK Stack
            try:
                self.deploy_pipeline_stack()
            except PipelineDeploymentError as e:
                if continue_on_error:
                    print(f"Warning: Pipeline deployment failed, continuing with existing topology: {e}", file=sys.stderr)
                else:
                    raise
            
            # Step 4: Read configuration
            self.read_configuration()
            
            # Step 5: Generate WorkflowTemplate
            template_yaml = self.generate_workflow_template()
            
            # Step 6: Apply WorkflowTemplate
            self.apply_workflow_template(template_yaml)
            
            print("\n=== Pipeline deployment stage completed successfully ===")
            
        except PipelineDeploymentError:
            print("\n=== Pipeline deployment stage failed ===", file=sys.stderr)
            raise


def main():
    """
    Main entry point for the pipeline deployment stage script.
    
    Expected environment variables:
    - REPO_URL: Git repository URL
    - COMMIT_SHA: Commit SHA to checkout
    - CONTINUE_ON_ERROR: (Optional) "true" to continue on deployment errors
    
    Command line arguments:
    - --generate-only: Only generate WorkflowTemplate, don't run full pipeline
    """
    import argparse
    
    parser = argparse.ArgumentParser(description='Pipeline deployment stage')
    parser.add_argument('--generate-only', action='store_true',
                       help='Only generate WorkflowTemplate YAML')
    args = parser.parse_args()
    
    if args.generate_only:
        # Generate WorkflowTemplate from current workspace
        try:
            stage = PipelineDeploymentStage(
                repo_url="",  # Not needed for generate-only
                commit_sha="",  # Not needed for generate-only
                workspace_dir="/workspace"
            )
            config = stage.read_configuration()
            template_yaml = stage.generate_workflow_template()
            
            # Write to file
            output_file = Path("/tmp/workflow-template.yaml")
            output_file.write_text(template_yaml)
            print(f"WorkflowTemplate written to {output_file}")
            sys.exit(0)
        except Exception as e:
            print(f"Error generating WorkflowTemplate: {e}", file=sys.stderr)
            sys.exit(1)
    
    # Get parameters from environment variables
    repo_url = os.environ.get('REPO_URL')
    commit_sha = os.environ.get('COMMIT_SHA')
    continue_on_error = os.environ.get('CONTINUE_ON_ERROR', 'true').lower() == 'true'
    
    if not repo_url:
        print("Error: REPO_URL environment variable not set", file=sys.stderr)
        sys.exit(1)
    
    if not commit_sha:
        print("Error: COMMIT_SHA environment variable not set", file=sys.stderr)
        sys.exit(1)
    
    # Create and run pipeline deployment stage
    stage = PipelineDeploymentStage(
        repo_url=repo_url,
        commit_sha=commit_sha
    )
    
    try:
        stage.run(continue_on_error=continue_on_error)
        sys.exit(0)
    except PipelineDeploymentError:
        sys.exit(1)


if __name__ == "__main__":
    main()
