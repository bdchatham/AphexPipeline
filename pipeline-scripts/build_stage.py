"""
Build stage script for AphexPipeline.

This module provides functionality to execute the build stage of the pipeline:
- Clone repository at specific commit SHA
- Execute user-defined build commands
- Package artifacts
- Tag artifacts with commit SHA and timestamp
- Upload artifacts to S3
"""

import os
import subprocess
import sys
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
import shutil
import boto3
from botocore.exceptions import ClientError


@dataclass
class ArtifactMetadata:
    """Metadata for build artifacts."""
    commit_sha: str
    timestamp: str
    artifact_path: str
    build_commands: List[str]
    status: str  # "success" or "failed"
    error_message: Optional[str] = None


class BuildStageError(Exception):
    """Exception raised when build stage fails."""
    pass


class BuildStage:
    """Handles the build stage execution."""
    
    def __init__(
        self,
        repo_url: str,
        commit_sha: str,
        build_commands: List[str],
        workspace_dir: str = "/workspace",
        artifacts_dir: str = "/workspace/artifacts"
    ):
        """
        Initialize the build stage.
        
        Args:
            repo_url: Git repository URL to clone
            commit_sha: Specific commit SHA to checkout
            build_commands: List of build commands to execute
            workspace_dir: Directory to clone repository into
            artifacts_dir: Directory where artifacts will be stored
        """
        self.repo_url = repo_url
        self.commit_sha = commit_sha
        self.build_commands = build_commands
        self.workspace_dir = Path(workspace_dir)
        self.artifacts_dir = Path(artifacts_dir)
        self.timestamp = datetime.utcnow().isoformat() + "Z"
        
    def clone_repository(self) -> None:
        """
        Clone the repository at the specific commit SHA.
        
        Raises:
            BuildStageError: If cloning or checkout fails
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
                raise BuildStageError(
                    f"Failed to checkout correct commit. "
                    f"Expected: {self.commit_sha}, Got: {actual_sha}"
                )
            
            print(f"Successfully cloned and checked out commit {self.commit_sha}")
            
        except subprocess.CalledProcessError as e:
            error_msg = f"Git operation failed: {e.stderr}"
            print(error_msg, file=sys.stderr)
            raise BuildStageError(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to clone repository: {str(e)}"
            print(error_msg, file=sys.stderr)
            raise BuildStageError(error_msg) from e
    
    def execute_build_commands(self) -> None:
        """
        Execute user-defined build commands in order.
        
        Raises:
            BuildStageError: If any build command fails
        """
        if not self.build_commands:
            print("No build commands to execute")
            return
        
        print(f"Executing {len(self.build_commands)} build command(s)")
        
        for i, command in enumerate(self.build_commands, 1):
            try:
                print(f"\n[{i}/{len(self.build_commands)}] Executing: {command}")
                
                # Execute command in workspace directory
                result = subprocess.run(
                    command,
                    cwd=str(self.workspace_dir),
                    shell=True,
                    capture_output=True,
                    text=True,
                    check=True
                )
                
                # Print stdout
                if result.stdout:
                    print(result.stdout)
                
                print(f"[{i}/{len(self.build_commands)}] Command completed successfully")
                
            except subprocess.CalledProcessError as e:
                error_msg = (
                    f"Build command failed: {command}\n"
                    f"Exit code: {e.returncode}\n"
                    f"Stdout: {e.stdout}\n"
                    f"Stderr: {e.stderr}"
                )
                print(error_msg, file=sys.stderr)
                raise BuildStageError(error_msg) from e
        
        print("\nAll build commands completed successfully")
    
    def package_artifacts(self) -> None:
        """
        Package artifacts from the build.
        
        This creates the artifacts directory if it doesn't exist.
        The actual artifact files should be created by the build commands.
        """
        # Create artifacts directory
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        print(f"Artifacts directory ready: {self.artifacts_dir}")
        
        # Check if artifacts exist
        if self.artifacts_dir.exists() and any(self.artifacts_dir.iterdir()):
            artifact_count = len(list(self.artifacts_dir.iterdir()))
            print(f"Found {artifact_count} artifact(s) in {self.artifacts_dir}")
        else:
            print(f"Warning: No artifacts found in {self.artifacts_dir}")
    
    def create_artifact_metadata(self, status: str = "success", error_message: Optional[str] = None) -> ArtifactMetadata:
        """
        Create metadata for the build artifacts.
        
        Args:
            status: Build status ("success" or "failed")
            error_message: Error message if build failed
            
        Returns:
            ArtifactMetadata object with tagged information
        """
        return ArtifactMetadata(
            commit_sha=self.commit_sha,
            timestamp=self.timestamp,
            artifact_path=str(self.artifacts_dir),
            build_commands=self.build_commands,
            status=status,
            error_message=error_message
        )
    
    def save_metadata(self, metadata: ArtifactMetadata) -> None:
        """
        Save artifact metadata to a JSON file.
        
        Args:
            metadata: ArtifactMetadata object to save
        """
        # Ensure artifacts directory exists
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        
        metadata_file = self.artifacts_dir / "metadata.json"
        
        with open(metadata_file, 'w') as f:
            json.dump(asdict(metadata), f, indent=2)
        
        print(f"Artifact metadata saved to {metadata_file}")
    
    def upload_artifacts_to_s3(self, bucket_name: str) -> str:
        """
        Upload artifacts to S3 bucket using commit SHA in the path.
        
        Args:
            bucket_name: Name of the S3 bucket to upload to
            
        Returns:
            S3 path where artifacts were uploaded (s3://bucket/commit-sha/)
            
        Raises:
            BuildStageError: If S3 upload fails
        """
        try:
            # Create S3 client
            s3_client = boto3.client('s3')
            
            # S3 prefix uses commit SHA
            s3_prefix = f"{self.commit_sha}/"
            
            print(f"Uploading artifacts to s3://{bucket_name}/{s3_prefix}")
            
            # Check if artifacts directory exists and has files
            if not self.artifacts_dir.exists():
                print("Warning: No artifacts directory found, nothing to upload")
                return f"s3://{bucket_name}/{s3_prefix}"
            
            artifact_files = list(self.artifacts_dir.rglob('*'))
            artifact_files = [f for f in artifact_files if f.is_file()]
            
            if not artifact_files:
                print("Warning: No artifact files found, nothing to upload")
                return f"s3://{bucket_name}/{s3_prefix}"
            
            # Upload each file
            uploaded_count = 0
            for artifact_file in artifact_files:
                # Get relative path from artifacts directory
                relative_path = artifact_file.relative_to(self.artifacts_dir)
                s3_key = f"{s3_prefix}{relative_path}"
                
                print(f"Uploading {artifact_file.name} to {s3_key}")
                
                # Upload file
                s3_client.upload_file(
                    str(artifact_file),
                    bucket_name,
                    s3_key
                )
                
                uploaded_count += 1
            
            s3_path = f"s3://{bucket_name}/{s3_prefix}"
            print(f"Successfully uploaded {uploaded_count} artifact(s) to {s3_path}")
            
            return s3_path
            
        except ClientError as e:
            error_msg = f"S3 upload failed: {e}"
            print(error_msg, file=sys.stderr)
            raise BuildStageError(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to upload artifacts to S3: {str(e)}"
            print(error_msg, file=sys.stderr)
            raise BuildStageError(error_msg) from e
    
    def upload_error_logs_to_s3(self, bucket_name: str, error_message: str) -> None:
        """
        Upload error logs to S3 for debugging.
        
        Args:
            bucket_name: Name of the S3 bucket to upload to
            error_message: Error message to store
        """
        try:
            s3_client = boto3.client('s3')
            
            # Create error log file
            self.artifacts_dir.mkdir(parents=True, exist_ok=True)
            error_log_file = self.artifacts_dir / "error.log"
            error_log_file.write_text(error_message)
            
            # Upload error log to S3
            s3_key = f"{self.commit_sha}/error.log"
            s3_client.upload_file(
                str(error_log_file),
                bucket_name,
                s3_key
            )
            
            print(f"Error log uploaded to s3://{bucket_name}/{s3_key}", file=sys.stderr)
            
        except Exception as upload_error:
            print(f"Failed to upload error log to S3: {upload_error}", file=sys.stderr)
    
    def run(self, s3_bucket: Optional[str] = None) -> ArtifactMetadata:
        """
        Execute the complete build stage.
        
        Args:
            s3_bucket: Optional S3 bucket name to upload artifacts to
        
        Returns:
            ArtifactMetadata object with build results
            
        Raises:
            BuildStageError: If any stage fails
        """
        try:
            # Step 1: Clone repository at specific commit
            self.clone_repository()
            
            # Step 2: Execute build commands
            self.execute_build_commands()
            
            # Step 3: Package artifacts
            self.package_artifacts()
            
            # Step 4: Upload to S3 if bucket specified
            if s3_bucket:
                s3_path = self.upload_artifacts_to_s3(s3_bucket)
                print(f"Artifacts uploaded to: {s3_path}")
            
            # Step 5: Create and save metadata
            metadata = self.create_artifact_metadata(status="success")
            self.save_metadata(metadata)
            
            print("\n=== Build stage completed successfully ===")
            return metadata
            
        except BuildStageError as e:
            # Create failure metadata
            metadata = self.create_artifact_metadata(
                status="failed",
                error_message=str(e)
            )
            
            # Try to save metadata even on failure
            try:
                self.artifacts_dir.mkdir(parents=True, exist_ok=True)
                self.save_metadata(metadata)
                
                # Upload error logs to S3 if bucket specified
                if s3_bucket:
                    self.upload_error_logs_to_s3(s3_bucket, str(e))
                    
            except Exception as save_error:
                print(f"Failed to save error metadata: {save_error}", file=sys.stderr)
            
            print("\n=== Build stage failed ===", file=sys.stderr)
            raise


def main():
    """
    Main entry point for the build stage script.
    
    Expected environment variables:
    - REPO_URL: Git repository URL
    - COMMIT_SHA: Commit SHA to checkout
    - BUILD_COMMANDS: JSON array of build commands
    - S3_BUCKET: (Optional) S3 bucket name for artifact upload
    """
    # Get parameters from environment variables
    repo_url = os.environ.get('REPO_URL')
    commit_sha = os.environ.get('COMMIT_SHA')
    build_commands_json = os.environ.get('BUILD_COMMANDS', '[]')
    s3_bucket = os.environ.get('S3_BUCKET')
    
    if not repo_url:
        print("Error: REPO_URL environment variable not set", file=sys.stderr)
        sys.exit(1)
    
    if not commit_sha:
        print("Error: COMMIT_SHA environment variable not set", file=sys.stderr)
        sys.exit(1)
    
    try:
        build_commands = json.loads(build_commands_json)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid BUILD_COMMANDS JSON: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Create and run build stage
    build_stage = BuildStage(
        repo_url=repo_url,
        commit_sha=commit_sha,
        build_commands=build_commands
    )
    
    try:
        metadata = build_stage.run(s3_bucket=s3_bucket)
        print(f"\nArtifact path: {metadata.artifact_path}")
        print(f"Commit SHA: {metadata.commit_sha}")
        print(f"Timestamp: {metadata.timestamp}")
        sys.exit(0)
    except BuildStageError:
        sys.exit(1)


if __name__ == "__main__":
    main()
