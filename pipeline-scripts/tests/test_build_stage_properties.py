"""
Property-based tests for build stage operations.

These tests verify that the build stage correctly handles repository cloning,
build command execution, and artifact management across a wide range of inputs.
"""

import pytest
import tempfile
import shutil
import subprocess
import json
from pathlib import Path
from hypothesis import given, strategies as st, settings, assume
from build_stage import BuildStage, BuildStageError, ArtifactMetadata


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
def valid_build_commands(draw):
    """Generate a list of valid build commands."""
    # Generate simple, safe commands for testing
    num_commands = draw(st.integers(min_value=0, max_value=5))
    
    commands = []
    for _ in range(num_commands):
        command_type = draw(st.sampled_from([
            'echo',
            'mkdir',
            'touch',
            'ls'
        ]))
        
        if command_type == 'echo':
            message = draw(st.text(
                alphabet='abcdefghijklmnopqrstuvwxyz0123456789 ',
                min_size=1,
                max_size=20
            ))
            commands.append(f'echo "{message}"')
        elif command_type == 'mkdir':
            dirname = draw(st.text(
                alphabet='abcdefghijklmnopqrstuvwxyz0123456789_',
                min_size=1,
                max_size=10
            ))
            commands.append(f'mkdir -p build_{dirname}')
        elif command_type == 'touch':
            filename = draw(st.text(
                alphabet='abcdefghijklmnopqrstuvwxyz0123456789_',
                min_size=1,
                max_size=10
            ))
            commands.append(f'touch artifact_{filename}.txt')
        else:  # ls
            commands.append('ls -la')
    
    return commands


# Feature: aphex-pipeline, Property 2: Repository cloning at specific commit
@settings(max_examples=100)
@given(commit_sha=valid_commit_sha())
def test_property_2_repository_cloning_at_specific_commit(commit_sha):
    """
    Property 2: Repository cloning at specific commit
    
    For any commit SHA provided to a workflow, the system should clone the
    repository at that exact commit, not at HEAD or any other commit.
    
    Validates: Requirements 1.5
    
    Note: This test uses a mock approach since we can't create arbitrary commits.
    We verify that the BuildStage attempts to checkout the specified commit SHA.
    """
    # Create a temporary directory for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir) / "workspace"
        artifacts = Path(temp_dir) / "artifacts"
        
        # Create a minimal git repository for testing
        workspace.mkdir(parents=True)
        
        # Initialize git repo
        subprocess.run(
            ["git", "init"],
            cwd=str(workspace),
            capture_output=True,
            check=True
        )
        
        # Configure git
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=str(workspace),
            capture_output=True,
            check=True
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=str(workspace),
            capture_output=True,
            check=True
        )
        
        # Create a commit
        test_file = workspace / "test.txt"
        test_file.write_text("test content")
        
        subprocess.run(
            ["git", "add", "."],
            cwd=str(workspace),
            capture_output=True,
            check=True
        )
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=str(workspace),
            capture_output=True,
            check=True
        )
        
        # Get the actual commit SHA
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(workspace),
            capture_output=True,
            text=True,
            check=True
        )
        actual_commit_sha = result.stdout.strip()
        
        # Now test that BuildStage would use the specified commit SHA
        # We verify the BuildStage stores the commit SHA correctly
        build_stage = BuildStage(
            repo_url="https://github.com/test/repo.git",
            commit_sha=commit_sha,
            build_commands=[],
            workspace_dir=str(workspace),
            artifacts_dir=str(artifacts)
        )
        
        # Verify the BuildStage has the correct commit SHA stored
        assert build_stage.commit_sha == commit_sha
        
        # Verify metadata creation includes the correct commit SHA
        metadata = build_stage.create_artifact_metadata()
        assert metadata.commit_sha == commit_sha
        
        # The commit SHA should be exactly what was provided, not HEAD or anything else
        assert metadata.commit_sha != "HEAD"
        assert metadata.commit_sha != ""
        assert len(metadata.commit_sha) == 40


# Feature: aphex-pipeline, Property 2: Repository cloning at specific commit (verification)
def test_property_2_repository_cloning_verification():
    """
    Property 2: Repository cloning at specific commit (verification)
    
    Verify that when cloning a real repository, the system checks out the
    exact commit specified and validates it matches.
    
    Validates: Requirements 1.5
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
        
        # Create first commit
        (test_repo / "file1.txt").write_text("content 1")
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
        
        # Create second commit
        (test_repo / "file2.txt").write_text("content 2")
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
        
        # Now clone at the first commit (not HEAD)
        build_stage = BuildStage(
            repo_url=str(test_repo),
            commit_sha=first_commit_sha,
            build_commands=[],
            workspace_dir=str(workspace),
            artifacts_dir=str(artifacts)
        )
        
        # Execute clone
        build_stage.clone_repository()
        
        # Verify we're at the first commit, not the second
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(workspace),
            capture_output=True,
            text=True,
            check=True
        )
        checked_out_sha = result.stdout.strip()
        
        # Should be at first commit, not second (HEAD)
        assert checked_out_sha == first_commit_sha
        assert checked_out_sha != second_commit_sha
        
        # Verify file1 exists but file2 doesn't (since we're at first commit)
        assert (workspace / "file1.txt").exists()
        assert not (workspace / "file2.txt").exists()


# Feature: aphex-pipeline, Property 2: Repository cloning at specific commit (error handling)
@settings(max_examples=100, deadline=None)
@given(commit_sha=valid_commit_sha())
def test_property_2_repository_cloning_invalid_commit(commit_sha):
    """
    Property 2: Repository cloning at specific commit (error handling)
    
    For any invalid commit SHA, the system should fail gracefully with a clear error.
    
    Validates: Requirements 1.5
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir) / "workspace"
        artifacts = Path(temp_dir) / "artifacts"
        
        # Create a test repository
        test_repo = Path(temp_dir) / "test_repo"
        test_repo.mkdir()
        
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
        
        # Create a commit
        (test_repo / "file.txt").write_text("content")
        subprocess.run(["git", "add", "."], cwd=str(test_repo), capture_output=True, check=True)
        subprocess.run(
            ["git", "commit", "-m", "Commit"],
            cwd=str(test_repo),
            capture_output=True,
            check=True
        )
        
        # Try to clone with a random (likely invalid) commit SHA
        build_stage = BuildStage(
            repo_url=str(test_repo),
            commit_sha=commit_sha,
            build_commands=[],
            workspace_dir=str(workspace),
            artifacts_dir=str(artifacts)
        )
        
        # Should raise BuildStageError for invalid commit
        with pytest.raises(BuildStageError):
            build_stage.clone_repository()


# Feature: aphex-pipeline, Property 3: Build command execution
@settings(max_examples=100)
@given(build_commands=valid_build_commands())
def test_property_3_build_command_execution(build_commands):
    """
    Property 3: Build command execution
    
    For any list of build commands in the configuration, all commands should be
    executed in the order specified.
    
    Validates: Requirements 2.2
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir) / "workspace"
        artifacts = Path(temp_dir) / "artifacts"
        workspace.mkdir(parents=True)
        
        # Create a BuildStage instance
        build_stage = BuildStage(
            repo_url="https://github.com/test/repo.git",
            commit_sha="a" * 40,
            build_commands=build_commands,
            workspace_dir=str(workspace),
            artifacts_dir=str(artifacts)
        )
        
        # Execute build commands
        if build_commands:
            build_stage.execute_build_commands()
            
            # Verify all commands were executed by checking their effects
            # For echo commands, we can't verify output easily in this context
            # For mkdir commands, verify directories were created
            for cmd in build_commands:
                if cmd.startswith('mkdir -p build_'):
                    dirname = cmd.split('build_')[1]
                    assert (workspace / f"build_{dirname}").exists()
                elif cmd.startswith('touch artifact_'):
                    filename = cmd.split('touch ')[1]
                    assert (workspace / filename).exists()
        else:
            # Empty command list should not raise an error
            build_stage.execute_build_commands()


# Feature: aphex-pipeline, Property 3: Build command execution (ordering)
def test_property_3_build_command_execution_ordering():
    """
    Property 3: Build command execution (ordering)
    
    Verify that build commands are executed in the exact order specified,
    not in parallel or in a different order.
    
    Validates: Requirements 2.2
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir) / "workspace"
        artifacts = Path(temp_dir) / "artifacts"
        workspace.mkdir(parents=True)
        
        # Create commands that depend on order
        # Each command writes to a file with a timestamp
        commands = [
            'echo "1" > order.txt',
            'echo "2" >> order.txt',
            'echo "3" >> order.txt',
        ]
        
        build_stage = BuildStage(
            repo_url="https://github.com/test/repo.git",
            commit_sha="a" * 40,
            build_commands=commands,
            workspace_dir=str(workspace),
            artifacts_dir=str(artifacts)
        )
        
        # Execute commands
        build_stage.execute_build_commands()
        
        # Verify order by reading the file
        order_file = workspace / "order.txt"
        assert order_file.exists()
        
        content = order_file.read_text()
        lines = content.strip().split('\n')
        
        # Should have executed in order: 1, 2, 3
        assert lines == ['1', '2', '3']


# Feature: aphex-pipeline, Property 3: Build command execution (failure handling)
def test_property_3_build_command_execution_failure():
    """
    Property 3: Build command execution (failure handling)
    
    When any build command fails, the system should stop execution and raise
    an error, not continue with subsequent commands.
    
    Validates: Requirements 2.2, 2.5
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir) / "workspace"
        artifacts = Path(temp_dir) / "artifacts"
        workspace.mkdir(parents=True)
        
        # Create commands where the second one will fail
        commands = [
            'echo "first" > first.txt',
            'exit 1',  # This will fail
            'echo "third" > third.txt',  # This should not execute
        ]
        
        build_stage = BuildStage(
            repo_url="https://github.com/test/repo.git",
            commit_sha="a" * 40,
            build_commands=commands,
            workspace_dir=str(workspace),
            artifacts_dir=str(artifacts)
        )
        
        # Should raise BuildStageError
        with pytest.raises(BuildStageError) as exc_info:
            build_stage.execute_build_commands()
        
        # Verify error message contains information about the failed command
        assert "exit 1" in str(exc_info.value)
        
        # Verify first command executed
        assert (workspace / "first.txt").exists()
        
        # Verify third command did NOT execute (stopped after failure)
        assert not (workspace / "third.txt").exists()


# Feature: aphex-pipeline, Property 3: Build command execution (empty list)
def test_property_3_build_command_execution_empty_list():
    """
    Property 3: Build command execution (empty list)
    
    When no build commands are specified, the system should handle it gracefully
    without errors.
    
    Validates: Requirements 2.2
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir) / "workspace"
        artifacts = Path(temp_dir) / "artifacts"
        workspace.mkdir(parents=True)
        
        build_stage = BuildStage(
            repo_url="https://github.com/test/repo.git",
            commit_sha="a" * 40,
            build_commands=[],
            workspace_dir=str(workspace),
            artifacts_dir=str(artifacts)
        )
        
        # Should not raise an error
        build_stage.execute_build_commands()


# Feature: aphex-pipeline, Property 4: Artifact tagging
@settings(max_examples=100)
@given(
    commit_sha=valid_commit_sha(),
    build_commands=valid_build_commands()
)
def test_property_4_artifact_tagging(commit_sha, build_commands):
    """
    Property 4: Artifact tagging
    
    For any build artifact created, it should be tagged with both the git commit
    SHA and a timestamp.
    
    Validates: Requirements 2.3
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir) / "workspace"
        artifacts = Path(temp_dir) / "artifacts"
        workspace.mkdir(parents=True)
        
        # Create a BuildStage instance
        build_stage = BuildStage(
            repo_url="https://github.com/test/repo.git",
            commit_sha=commit_sha,
            build_commands=build_commands,
            workspace_dir=str(workspace),
            artifacts_dir=str(artifacts)
        )
        
        # Create artifact metadata
        metadata = build_stage.create_artifact_metadata()
        
        # Verify commit SHA is tagged
        assert metadata.commit_sha == commit_sha
        assert isinstance(metadata.commit_sha, str)
        assert len(metadata.commit_sha) == 40
        
        # Verify timestamp is tagged
        assert metadata.timestamp is not None
        assert isinstance(metadata.timestamp, str)
        assert len(metadata.timestamp) > 0
        
        # Verify timestamp is in ISO format with Z suffix
        assert metadata.timestamp.endswith('Z')
        
        # Verify timestamp can be parsed as a valid datetime
        from datetime import datetime
        # Remove the Z and parse
        timestamp_str = metadata.timestamp[:-1]
        parsed_time = datetime.fromisoformat(timestamp_str)
        assert parsed_time is not None


# Feature: aphex-pipeline, Property 4: Artifact tagging (metadata persistence)
@settings(max_examples=100)
@given(
    commit_sha=valid_commit_sha(),
    build_commands=valid_build_commands()
)
def test_property_4_artifact_tagging_persistence(commit_sha, build_commands):
    """
    Property 4: Artifact tagging (metadata persistence)
    
    For any build artifact, the metadata should be persisted to a file that can
    be read back with the same information.
    
    Validates: Requirements 2.3
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir) / "workspace"
        artifacts = Path(temp_dir) / "artifacts"
        workspace.mkdir(parents=True)
        
        build_stage = BuildStage(
            repo_url="https://github.com/test/repo.git",
            commit_sha=commit_sha,
            build_commands=build_commands,
            workspace_dir=str(workspace),
            artifacts_dir=str(artifacts)
        )
        
        # Create and save metadata
        metadata = build_stage.create_artifact_metadata()
        build_stage.save_metadata(metadata)
        
        # Verify metadata file exists
        metadata_file = artifacts / "metadata.json"
        assert metadata_file.exists()
        
        # Read metadata back
        with open(metadata_file, 'r') as f:
            saved_metadata = json.load(f)
        
        # Verify all fields are preserved
        assert saved_metadata['commit_sha'] == commit_sha
        assert saved_metadata['timestamp'] == metadata.timestamp
        assert saved_metadata['artifact_path'] == str(artifacts)
        assert saved_metadata['build_commands'] == build_commands
        assert saved_metadata['status'] == 'success'


# Feature: aphex-pipeline, Property 4: Artifact tagging (uniqueness)
def test_property_4_artifact_tagging_uniqueness():
    """
    Property 4: Artifact tagging (uniqueness)
    
    For any two build stages created at different times, they should have
    different timestamps, ensuring artifacts can be uniquely identified.
    
    Validates: Requirements 2.3
    """
    import time
    
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace1 = Path(temp_dir) / "workspace1"
        artifacts1 = Path(temp_dir) / "artifacts1"
        workspace1.mkdir(parents=True)
        
        workspace2 = Path(temp_dir) / "workspace2"
        artifacts2 = Path(temp_dir) / "artifacts2"
        workspace2.mkdir(parents=True)
        
        # Create first build stage
        build_stage1 = BuildStage(
            repo_url="https://github.com/test/repo.git",
            commit_sha="a" * 40,
            build_commands=[],
            workspace_dir=str(workspace1),
            artifacts_dir=str(artifacts1)
        )
        metadata1 = build_stage1.create_artifact_metadata()
        
        # Wait a tiny bit to ensure different timestamp
        time.sleep(0.01)
        
        # Create second build stage
        build_stage2 = BuildStage(
            repo_url="https://github.com/test/repo.git",
            commit_sha="b" * 40,
            build_commands=[],
            workspace_dir=str(workspace2),
            artifacts_dir=str(artifacts2)
        )
        metadata2 = build_stage2.create_artifact_metadata()
        
        # Timestamps should be different
        assert metadata1.timestamp != metadata2.timestamp
        
        # Commit SHAs should be different
        assert metadata1.commit_sha != metadata2.commit_sha


# Feature: aphex-pipeline, Property 4: Artifact tagging (failure case)
@settings(max_examples=100)
@given(commit_sha=valid_commit_sha())
def test_property_4_artifact_tagging_failure_case(commit_sha):
    """
    Property 4: Artifact tagging (failure case)
    
    For any build that fails, the metadata should still be tagged with commit SHA
    and timestamp, plus include error information.
    
    Validates: Requirements 2.3, 2.5
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir) / "workspace"
        artifacts = Path(temp_dir) / "artifacts"
        workspace.mkdir(parents=True)
        
        build_stage = BuildStage(
            repo_url="https://github.com/test/repo.git",
            commit_sha=commit_sha,
            build_commands=[],
            workspace_dir=str(workspace),
            artifacts_dir=str(artifacts)
        )
        
        # Create failure metadata
        error_msg = "Build failed due to test error"
        metadata = build_stage.create_artifact_metadata(
            status="failed",
            error_message=error_msg
        )
        
        # Verify commit SHA and timestamp are still tagged
        assert metadata.commit_sha == commit_sha
        assert metadata.timestamp is not None
        
        # Verify failure information is included
        assert metadata.status == "failed"
        assert metadata.error_message == error_msg


# Feature: aphex-pipeline, Property 5: Artifact storage and retrieval
@settings(max_examples=100, deadline=None)
@given(
    commit_sha=valid_commit_sha(),
    # Avoid carriage return characters that cause line ending issues
    artifact_content=st.text(alphabet=st.characters(blacklist_characters='\r'), min_size=1, max_size=1000)
)
def test_property_5_artifact_storage_and_retrieval(commit_sha, artifact_content):
    """
    Property 5: Artifact storage and retrieval
    
    For any artifact uploaded to S3, it should be retrievable using the same path
    and have identical contents (round-trip property).
    
    Validates: Requirements 2.4
    
    Note: This test uses moto to mock S3 operations.
    """
    # Import moto for S3 mocking
    try:
        from moto import mock_aws
        import boto3
    except ImportError:
        pytest.skip("moto not installed, skipping S3 tests")
    
    with mock_aws():
        # Create mock S3 bucket
        bucket_name = "test-artifacts-bucket"
        s3_client = boto3.client('s3', region_name='us-east-1')
        s3_client.create_bucket(Bucket=bucket_name)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir) / "workspace"
            artifacts = Path(temp_dir) / "artifacts"
            workspace.mkdir(parents=True)
            artifacts.mkdir(parents=True)
            
            # Create an artifact file
            artifact_file = artifacts / "test_artifact.txt"
            artifact_file.write_text(artifact_content)
            
            # Create BuildStage and upload
            build_stage = BuildStage(
                repo_url="https://github.com/test/repo.git",
                commit_sha=commit_sha,
                build_commands=[],
                workspace_dir=str(workspace),
                artifacts_dir=str(artifacts)
            )
            
            # Upload to S3
            s3_path = build_stage.upload_artifacts_to_s3(bucket_name)
            
            # Verify S3 path uses commit SHA
            assert commit_sha in s3_path
            assert s3_path == f"s3://{bucket_name}/{commit_sha}/"
            
            # Download the artifact back from S3
            s3_key = f"{commit_sha}/test_artifact.txt"
            download_path = Path(temp_dir) / "downloaded_artifact.txt"
            
            s3_client.download_file(
                bucket_name,
                s3_key,
                str(download_path)
            )
            
            # Verify content matches (round-trip property)
            downloaded_content = download_path.read_text()
            assert downloaded_content == artifact_content


# Feature: aphex-pipeline, Property 5: Artifact storage and retrieval (multiple files)
def test_property_5_artifact_storage_and_retrieval_multiple_files():
    """
    Property 5: Artifact storage and retrieval (multiple files)
    
    For any set of artifacts uploaded to S3, all should be retrievable with
    identical contents.
    
    Validates: Requirements 2.4
    """
    try:
        from moto import mock_aws
        import boto3
    except ImportError:
        pytest.skip("moto not installed, skipping S3 tests")
    
    with mock_aws():
        bucket_name = "test-artifacts-bucket"
        s3_client = boto3.client('s3', region_name='us-east-1')
        s3_client.create_bucket(Bucket=bucket_name)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir) / "workspace"
            artifacts = Path(temp_dir) / "artifacts"
            workspace.mkdir(parents=True)
            artifacts.mkdir(parents=True)
            
            # Create multiple artifact files
            test_files = {
                "file1.txt": "content 1",
                "file2.txt": "content 2",
                "subdir/file3.txt": "content 3"
            }
            
            for file_path, content in test_files.items():
                full_path = artifacts / file_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text(content)
            
            commit_sha = "a" * 40
            build_stage = BuildStage(
                repo_url="https://github.com/test/repo.git",
                commit_sha=commit_sha,
                build_commands=[],
                workspace_dir=str(workspace),
                artifacts_dir=str(artifacts)
            )
            
            # Upload all artifacts
            s3_path = build_stage.upload_artifacts_to_s3(bucket_name)
            
            # Download and verify each file
            for file_path, expected_content in test_files.items():
                s3_key = f"{commit_sha}/{file_path}"
                download_path = Path(temp_dir) / f"downloaded_{file_path.replace('/', '_')}"
                
                s3_client.download_file(
                    bucket_name,
                    s3_key,
                    str(download_path)
                )
                
                # Verify content matches
                downloaded_content = download_path.read_text()
                assert downloaded_content == expected_content


# Feature: aphex-pipeline, Property 5: Artifact storage and retrieval (commit SHA isolation)
def test_property_5_artifact_storage_commit_sha_isolation():
    """
    Property 5: Artifact storage and retrieval (commit SHA isolation)
    
    Artifacts from different commits should be stored in separate S3 paths
    and not interfere with each other.
    
    Validates: Requirements 2.4
    """
    try:
        from moto import mock_aws
        import boto3
    except ImportError:
        pytest.skip("moto not installed, skipping S3 tests")
    
    with mock_aws():
        bucket_name = "test-artifacts-bucket"
        s3_client = boto3.client('s3', region_name='us-east-1')
        s3_client.create_bucket(Bucket=bucket_name)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Upload artifacts for first commit
            workspace1 = Path(temp_dir) / "workspace1"
            artifacts1 = Path(temp_dir) / "artifacts1"
            workspace1.mkdir(parents=True)
            artifacts1.mkdir(parents=True)
            
            (artifacts1 / "artifact.txt").write_text("commit 1 content")
            
            commit_sha1 = "a" * 40
            build_stage1 = BuildStage(
                repo_url="https://github.com/test/repo.git",
                commit_sha=commit_sha1,
                build_commands=[],
                workspace_dir=str(workspace1),
                artifacts_dir=str(artifacts1)
            )
            s3_path1 = build_stage1.upload_artifacts_to_s3(bucket_name)
            
            # Upload artifacts for second commit
            workspace2 = Path(temp_dir) / "workspace2"
            artifacts2 = Path(temp_dir) / "artifacts2"
            workspace2.mkdir(parents=True)
            artifacts2.mkdir(parents=True)
            
            (artifacts2 / "artifact.txt").write_text("commit 2 content")
            
            commit_sha2 = "b" * 40
            build_stage2 = BuildStage(
                repo_url="https://github.com/test/repo.git",
                commit_sha=commit_sha2,
                build_commands=[],
                workspace_dir=str(workspace2),
                artifacts_dir=str(artifacts2)
            )
            s3_path2 = build_stage2.upload_artifacts_to_s3(bucket_name)
            
            # Verify paths are different
            assert s3_path1 != s3_path2
            assert commit_sha1 in s3_path1
            assert commit_sha2 in s3_path2
            
            # Download both artifacts and verify they have different content
            download1 = Path(temp_dir) / "download1.txt"
            download2 = Path(temp_dir) / "download2.txt"
            
            s3_client.download_file(
                bucket_name,
                f"{commit_sha1}/artifact.txt",
                str(download1)
            )
            s3_client.download_file(
                bucket_name,
                f"{commit_sha2}/artifact.txt",
                str(download2)
            )
            
            # Content should be different
            assert download1.read_text() == "commit 1 content"
            assert download2.read_text() == "commit 2 content"
            assert download1.read_text() != download2.read_text()
