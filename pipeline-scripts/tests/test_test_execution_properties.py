"""
Property-based tests for test execution stage operations.

These tests verify that the test execution stage correctly handles test command
execution, result capture, and error handling across a wide range of inputs.
"""

import pytest
import tempfile
import json
from pathlib import Path
from hypothesis import given, strategies as st, settings
from test_execution_stage import (
    TestExecutionStage,
    TestExecutionError,
    TestCommandResult,
    TestExecutionResult
)


# Hypothesis strategies for generating test data

@st.composite
def valid_test_commands(draw):
    """Generate a list of valid test commands."""
    # Generate simple, safe commands for testing
    num_commands = draw(st.integers(min_value=0, max_value=5))
    
    commands = []
    for _ in range(num_commands):
        command_type = draw(st.sampled_from([
            'echo',
            'test',
            'true',
            'ls'
        ]))
        
        if command_type == 'echo':
            message = draw(st.text(
                alphabet='abcdefghijklmnopqrstuvwxyz0123456789 ',
                min_size=1,
                max_size=20
            ))
            commands.append(f'echo "Test: {message}"')
        elif command_type == 'test':
            # Simple test commands that will pass
            test_type = draw(st.sampled_from([
                'test -d .',
                'test -f /dev/null',
                '[ 1 -eq 1 ]',
                '[ "a" = "a" ]'
            ]))
            commands.append(test_type)
        elif command_type == 'true':
            commands.append('true')
        else:  # ls
            commands.append('ls -la')
    
    return commands


@st.composite
def valid_commit_sha(draw):
    """Generate a valid git commit SHA (40 character hex string)."""
    return draw(st.text(
        alphabet='0123456789abcdef',
        min_size=40,
        max_size=40
    ))


@st.composite
def valid_environment_name(draw):
    """Generate a valid environment name."""
    return draw(st.text(
        alphabet='abcdefghijklmnopqrstuvwxyz0123456789-',
        min_size=1,
        max_size=20
    ))


# Feature: aphex-pipeline, Property 12: Test command execution
@settings(max_examples=100)
@given(
    test_commands=valid_test_commands(),
    environment_name=valid_environment_name(),
    commit_sha=valid_commit_sha()
)
def test_property_12_test_command_execution(test_commands, environment_name, commit_sha):
    """
    Property 12: Test command execution
    
    For any list of test commands in an environment configuration, all commands
    should be executed in the order specified.
    
    Validates: Requirements 6.1
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir) / "workspace"
        workspace.mkdir(parents=True)
        
        # Create a TestExecutionStage instance
        stage = TestExecutionStage(
            test_commands=test_commands,
            environment_name=environment_name,
            commit_sha=commit_sha,
            workspace_dir=str(workspace)
        )
        
        # Execute all test commands
        results = stage.execute_all_tests()
        
        # Verify the number of results matches the number of commands
        assert len(results) == len(test_commands)
        
        # Verify each command was executed
        for i, (command, result) in enumerate(zip(test_commands, results)):
            # The command in the result should match the input command
            assert result.command == command
            
            # Each result should have an exit code
            assert isinstance(result.exit_code, int)
            
            # Each result should have stdout and stderr (even if empty)
            assert isinstance(result.stdout, str)
            assert isinstance(result.stderr, str)
            
            # Each result should have a status
            assert result.status in ["passed", "failed"]
            
            # Each result should have a duration
            assert isinstance(result.duration_seconds, float)
            assert result.duration_seconds >= 0


# Feature: aphex-pipeline, Property 12: Test command execution (ordering)
def test_property_12_test_command_execution_ordering():
    """
    Property 12: Test command execution (ordering)
    
    Verify that test commands are executed in the exact order specified,
    not in parallel or in a different order.
    
    Validates: Requirements 6.1
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir) / "workspace"
        workspace.mkdir(parents=True)
        
        # Create commands that write to a file in order
        commands = [
            'echo "1" > order.txt',
            'echo "2" >> order.txt',
            'echo "3" >> order.txt',
        ]
        
        stage = TestExecutionStage(
            test_commands=commands,
            environment_name="test-env",
            commit_sha="a" * 40,
            workspace_dir=str(workspace)
        )
        
        # Execute commands
        results = stage.execute_all_tests()
        
        # Verify all commands executed
        assert len(results) == 3
        
        # Verify order by reading the file
        order_file = workspace / "order.txt"
        assert order_file.exists()
        
        content = order_file.read_text()
        lines = content.strip().split('\n')
        
        # Should have executed in order: 1, 2, 3
        assert lines == ['1', '2', '3']
        
        # All commands should have passed
        for result in results:
            assert result.status == "passed"
            assert result.exit_code == 0


# Feature: aphex-pipeline, Property 12: Test command execution (empty list)
def test_property_12_test_command_execution_empty_list():
    """
    Property 12: Test command execution (empty list)
    
    When no test commands are specified, the system should handle it gracefully
    without errors.
    
    Validates: Requirements 6.1
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir) / "workspace"
        workspace.mkdir(parents=True)
        
        stage = TestExecutionStage(
            test_commands=[],
            environment_name="test-env",
            commit_sha="a" * 40,
            workspace_dir=str(workspace)
        )
        
        # Should not raise an error
        results = stage.execute_all_tests()
        
        # Should return empty list
        assert results == []


# Feature: aphex-pipeline, Property 12: Test command execution (failure handling)
def test_property_12_test_command_execution_failure_handling():
    """
    Property 12: Test command execution (failure handling)
    
    When a test command fails, the system should capture the failure but
    continue executing remaining tests to get complete results.
    
    Validates: Requirements 6.1, 6.2
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir) / "workspace"
        workspace.mkdir(parents=True)
        
        # Create commands where the second one will fail
        commands = [
            'echo "first test"',
            'exit 1',  # This will fail
            'echo "third test"',  # This should still execute
        ]
        
        stage = TestExecutionStage(
            test_commands=commands,
            environment_name="test-env",
            commit_sha="a" * 40,
            workspace_dir=str(workspace)
        )
        
        # Execute all tests
        results = stage.execute_all_tests()
        
        # All three commands should have been executed
        assert len(results) == 3
        
        # First command should pass
        assert results[0].status == "passed"
        assert results[0].exit_code == 0
        
        # Second command should fail
        assert results[1].status == "failed"
        assert results[1].exit_code == 1
        
        # Third command should still execute and pass
        assert results[2].status == "passed"
        assert results[2].exit_code == 0


# Feature: aphex-pipeline, Property 12: Test command execution (exit code capture)
@settings(max_examples=100)
@given(exit_code=st.integers(min_value=0, max_value=255))
def test_property_12_test_command_execution_exit_code_capture(exit_code):
    """
    Property 12: Test command execution (exit code capture)
    
    For any test command with any exit code, the system should capture the
    exact exit code.
    
    Validates: Requirements 6.1
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir) / "workspace"
        workspace.mkdir(parents=True)
        
        # Create a command that exits with the specified code
        commands = [f'exit {exit_code}']
        
        stage = TestExecutionStage(
            test_commands=commands,
            environment_name="test-env",
            commit_sha="a" * 40,
            workspace_dir=str(workspace)
        )
        
        # Execute test
        results = stage.execute_all_tests()
        
        # Verify exit code was captured correctly
        assert len(results) == 1
        assert results[0].exit_code == exit_code
        
        # Verify status matches exit code
        if exit_code == 0:
            assert results[0].status == "passed"
        else:
            assert results[0].status == "failed"


# Feature: aphex-pipeline, Property 12: Test command execution (output capture)
@settings(max_examples=100)
@given(
    stdout_message=st.text(
        alphabet='abcdefghijklmnopqrstuvwxyz0123456789 ',
        min_size=1,
        max_size=50
    ),
    stderr_message=st.text(
        alphabet='abcdefghijklmnopqrstuvwxyz0123456789 ',
        min_size=1,
        max_size=50
    )
)
def test_property_12_test_command_execution_output_capture(stdout_message, stderr_message):
    """
    Property 12: Test command execution (output capture)
    
    For any test command that produces stdout and stderr output, the system
    should capture both outputs completely.
    
    Validates: Requirements 6.1
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir) / "workspace"
        workspace.mkdir(parents=True)
        
        # Create a command that writes to both stdout and stderr
        commands = [
            f'echo "{stdout_message}" && echo "{stderr_message}" >&2'
        ]
        
        stage = TestExecutionStage(
            test_commands=commands,
            environment_name="test-env",
            commit_sha="a" * 40,
            workspace_dir=str(workspace)
        )
        
        # Execute test
        results = stage.execute_all_tests()
        
        # Verify output was captured
        assert len(results) == 1
        
        # Verify stdout contains the message
        assert stdout_message in results[0].stdout
        
        # Verify stderr contains the message
        assert stderr_message in results[0].stderr


# Feature: aphex-pipeline, Property 12: Test command execution (duration tracking)
def test_property_12_test_command_execution_duration_tracking():
    """
    Property 12: Test command execution (duration tracking)
    
    For any test command, the system should track how long it takes to execute.
    
    Validates: Requirements 6.1
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir) / "workspace"
        workspace.mkdir(parents=True)
        
        # Create a command that takes a measurable amount of time
        commands = ['sleep 0.1']
        
        stage = TestExecutionStage(
            test_commands=commands,
            environment_name="test-env",
            commit_sha="a" * 40,
            workspace_dir=str(workspace)
        )
        
        # Execute test
        results = stage.execute_all_tests()
        
        # Verify duration was tracked
        assert len(results) == 1
        assert results[0].duration_seconds >= 0.1
        assert results[0].duration_seconds < 1.0  # Should not take too long


# Feature: aphex-pipeline, Property 12: Test command execution (workspace context)
def test_property_12_test_command_execution_workspace_context():
    """
    Property 12: Test command execution (workspace context)
    
    For any test command, it should be executed in the workspace directory,
    not in some other location.
    
    Validates: Requirements 6.1
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir) / "workspace"
        workspace.mkdir(parents=True)
        
        # Create a marker file in the workspace
        marker_file = workspace / "workspace_marker.txt"
        marker_file.write_text("marker")
        
        # Create a command that checks for the marker file
        commands = ['test -f workspace_marker.txt']
        
        stage = TestExecutionStage(
            test_commands=commands,
            environment_name="test-env",
            commit_sha="a" * 40,
            workspace_dir=str(workspace)
        )
        
        # Execute test
        results = stage.execute_all_tests()
        
        # The test should pass because the file exists in the workspace
        assert len(results) == 1
        assert results[0].status == "passed"
        assert results[0].exit_code == 0


# Feature: aphex-pipeline, Property 12: Test command execution (all commands executed)
@settings(max_examples=100)
@given(
    num_commands=st.integers(min_value=1, max_value=10)
)
def test_property_12_test_command_execution_all_commands_executed(num_commands):
    """
    Property 12: Test command execution (all commands executed)
    
    For any number of test commands, all should be executed even if some fail.
    
    Validates: Requirements 6.1
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir) / "workspace"
        workspace.mkdir(parents=True)
        
        # Create commands that write to individual files
        commands = []
        for i in range(num_commands):
            # Some commands will fail (odd numbers), some will pass (even numbers)
            if i % 2 == 0:
                commands.append(f'echo "test {i}" > test_{i}.txt')
            else:
                commands.append(f'echo "test {i}" > test_{i}.txt && exit 1')
        
        stage = TestExecutionStage(
            test_commands=commands,
            environment_name="test-env",
            commit_sha="a" * 40,
            workspace_dir=str(workspace)
        )
        
        # Execute all tests
        results = stage.execute_all_tests()
        
        # All commands should have been executed
        assert len(results) == num_commands
        
        # Verify all files were created (proving all commands ran)
        for i in range(num_commands):
            test_file = workspace / f"test_{i}.txt"
            assert test_file.exists()
            assert f"test {i}" in test_file.read_text()
        
        # Verify status matches expectations
        for i, result in enumerate(results):
            if i % 2 == 0:
                assert result.status == "passed"
            else:
                assert result.status == "failed"


# Feature: aphex-pipeline, Property 12: Test command execution (command preservation)
@settings(max_examples=100)
@given(
    test_commands=valid_test_commands()
)
def test_property_12_test_command_execution_command_preservation(test_commands):
    """
    Property 12: Test command execution (command preservation)
    
    For any list of test commands, the exact command strings should be preserved
    in the results without modification.
    
    Validates: Requirements 6.1
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir) / "workspace"
        workspace.mkdir(parents=True)
        
        stage = TestExecutionStage(
            test_commands=test_commands,
            environment_name="test-env",
            commit_sha="a" * 40,
            workspace_dir=str(workspace)
        )
        
        # Execute tests
        results = stage.execute_all_tests()
        
        # Verify commands are preserved exactly
        assert len(results) == len(test_commands)
        
        for original_command, result in zip(test_commands, results):
            assert result.command == original_command



# Feature: aphex-pipeline, Property 13: Test result capture
@settings(max_examples=100)
@given(
    test_commands=valid_test_commands(),
    environment_name=valid_environment_name(),
    commit_sha=valid_commit_sha()
)
def test_property_13_test_result_capture(test_commands, environment_name, commit_sha):
    """
    Property 13: Test result capture
    
    For any test execution, the results (pass/fail status and logs) should be
    captured and stored.
    
    Validates: Requirements 6.3
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir) / "workspace"
        workspace.mkdir(parents=True)
        
        # Create a TestExecutionStage instance
        stage = TestExecutionStage(
            test_commands=test_commands,
            environment_name=environment_name,
            commit_sha=commit_sha,
            workspace_dir=str(workspace)
        )
        
        # Execute tests and store results
        stage.test_results = stage.execute_all_tests()
        
        # Save test results to file
        output_file = Path(temp_dir) / "test-results.json"
        stage.save_test_results(str(output_file))
        
        # Verify file was created
        assert output_file.exists()
        
        # Read and verify content
        with open(output_file, 'r') as f:
            data = json.load(f)
        
        # Verify all required fields are present
        assert 'environment_name' in data
        assert 'commit_sha' in data
        assert 'timestamp' in data
        assert 'test_results' in data
        assert 'overall_status' in data
        assert 'total_duration_seconds' in data
        
        # Verify values match input
        assert data['environment_name'] == environment_name
        assert data['commit_sha'] == commit_sha
        
        # Verify test results array has correct length
        assert len(data['test_results']) == len(test_commands)
        
        # Verify each test result has required fields
        for test_result in data['test_results']:
            assert 'command' in test_result
            assert 'exit_code' in test_result
            assert 'stdout' in test_result
            assert 'stderr' in test_result
            assert 'status' in test_result
            assert 'duration_seconds' in test_result
            
            # Verify status is valid
            assert test_result['status'] in ['passed', 'failed']
            
            # Verify exit code is an integer
            assert isinstance(test_result['exit_code'], int)
            
            # Verify duration is a number
            assert isinstance(test_result['duration_seconds'], (int, float))
            assert test_result['duration_seconds'] >= 0
        
        # Verify overall status is valid
        assert data['overall_status'] in ['passed', 'failed']
        
        # Verify total duration is a number
        assert isinstance(data['total_duration_seconds'], (int, float))
        assert data['total_duration_seconds'] >= 0


# Feature: aphex-pipeline, Property 13: Test result capture (log files)
@settings(max_examples=100)
@given(
    test_commands=valid_test_commands(),
    environment_name=valid_environment_name(),
    commit_sha=valid_commit_sha()
)
def test_property_13_test_result_capture_log_files(test_commands, environment_name, commit_sha):
    """
    Property 13: Test result capture (log files)
    
    For any test execution, individual test logs should be stored in separate
    files with all relevant information.
    
    Validates: Requirements 6.3
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir) / "workspace"
        workspace.mkdir(parents=True)
        
        # Create a TestExecutionStage instance
        stage = TestExecutionStage(
            test_commands=test_commands,
            environment_name=environment_name,
            commit_sha=commit_sha,
            workspace_dir=str(workspace)
        )
        
        # Execute tests and store results
        stage.test_results = stage.execute_all_tests()
        
        # Save test logs
        log_dir = Path(temp_dir) / "test-logs"
        stage.save_test_logs(str(log_dir))
        
        if test_commands:
            # Verify log directory was created
            assert log_dir.exists()
            
            # Verify correct number of log files
            log_files = list(log_dir.glob('test-*.log'))
            assert len(log_files) == len(test_commands)
            
            # Verify each log file contains required information
            for log_file in log_files:
                content = log_file.read_text()
                
                # Verify all required sections are present
                assert 'Command:' in content
                assert 'Exit Code:' in content
                assert 'Status:' in content
                assert 'Duration:' in content
                assert 'STDOUT:' in content
                assert 'STDERR:' in content


# Feature: aphex-pipeline, Property 13: Test result capture (round-trip)
def test_property_13_test_result_capture_round_trip():
    """
    Property 13: Test result capture (round-trip)
    
    For any test execution, the saved results should be readable back with
    all information preserved (round-trip property).
    
    Validates: Requirements 6.3
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir) / "workspace"
        workspace.mkdir(parents=True)
        
        # Create test commands with known outputs
        test_commands = [
            'echo "stdout message" && echo "stderr message" >&2',
            'exit 0',
            'exit 1'
        ]
        
        stage = TestExecutionStage(
            test_commands=test_commands,
            environment_name="test-env",
            commit_sha="a" * 40,
            workspace_dir=str(workspace)
        )
        
        # Execute tests and store results
        stage.test_results = stage.execute_all_tests()
        
        # Save original results
        original_results = [
            {
                'command': r.command,
                'exit_code': r.exit_code,
                'status': r.status,
                'stdout': r.stdout,
                'stderr': r.stderr,
                'duration_seconds': r.duration_seconds
            }
            for r in stage.test_results
        ]
        
        # Save to file
        output_file = Path(temp_dir) / "test-results.json"
        stage.save_test_results(str(output_file))
        
        # Read back from file
        with open(output_file, 'r') as f:
            saved_data = json.load(f)
        
        # Verify all test results are preserved
        assert len(saved_data['test_results']) == len(original_results)
        
        for original, saved in zip(original_results, saved_data['test_results']):
            # Verify all fields match
            assert saved['command'] == original['command']
            assert saved['exit_code'] == original['exit_code']
            assert saved['status'] == original['status']
            assert saved['stdout'] == original['stdout']
            assert saved['stderr'] == original['stderr']
            assert saved['duration_seconds'] == original['duration_seconds']


# Feature: aphex-pipeline, Property 13: Test result capture (failure status)
def test_property_13_test_result_capture_failure_status():
    """
    Property 13: Test result capture (failure status)
    
    For any test execution with failures, the overall status should be "failed"
    and individual failure details should be captured.
    
    Validates: Requirements 6.3
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir) / "workspace"
        workspace.mkdir(parents=True)
        
        # Create test commands where some fail
        test_commands = [
            'echo "test 1"',  # Pass
            'exit 1',         # Fail
            'echo "test 3"',  # Pass
            'exit 2',         # Fail
        ]
        
        stage = TestExecutionStage(
            test_commands=test_commands,
            environment_name="test-env",
            commit_sha="a" * 40,
            workspace_dir=str(workspace)
        )
        
        # Execute tests and store results
        stage.test_results = stage.execute_all_tests()
        
        # Save results
        output_file = Path(temp_dir) / "test-results.json"
        stage.save_test_results(str(output_file))
        
        # Read back
        with open(output_file, 'r') as f:
            data = json.load(f)
        
        # Overall status should be "failed" because some tests failed
        assert data['overall_status'] == 'failed'
        
        # Verify individual test statuses
        assert data['test_results'][0]['status'] == 'passed'
        assert data['test_results'][0]['exit_code'] == 0
        
        assert data['test_results'][1]['status'] == 'failed'
        assert data['test_results'][1]['exit_code'] == 1
        
        assert data['test_results'][2]['status'] == 'passed'
        assert data['test_results'][2]['exit_code'] == 0
        
        assert data['test_results'][3]['status'] == 'failed'
        assert data['test_results'][3]['exit_code'] == 2


# Feature: aphex-pipeline, Property 13: Test result capture (success status)
def test_property_13_test_result_capture_success_status():
    """
    Property 13: Test result capture (success status)
    
    For any test execution where all tests pass, the overall status should be
    "passed".
    
    Validates: Requirements 6.3
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir) / "workspace"
        workspace.mkdir(parents=True)
        
        # Create test commands that all pass
        test_commands = [
            'echo "test 1"',
            'true',
            'test -d .',
        ]
        
        stage = TestExecutionStage(
            test_commands=test_commands,
            environment_name="test-env",
            commit_sha="a" * 40,
            workspace_dir=str(workspace)
        )
        
        # Execute tests and store results
        stage.test_results = stage.execute_all_tests()
        
        # Save results
        output_file = Path(temp_dir) / "test-results.json"
        stage.save_test_results(str(output_file))
        
        # Read back
        with open(output_file, 'r') as f:
            data = json.load(f)
        
        # Overall status should be "passed" because all tests passed
        assert data['overall_status'] == 'passed'
        
        # Verify all individual test statuses are "passed"
        for test_result in data['test_results']:
            assert test_result['status'] == 'passed'
            assert test_result['exit_code'] == 0


# Feature: aphex-pipeline, Property 13: Test result capture (duration accumulation)
def test_property_13_test_result_capture_duration_accumulation():
    """
    Property 13: Test result capture (duration accumulation)
    
    For any test execution, the total duration should be the sum of all
    individual test durations.
    
    Validates: Requirements 6.3
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir) / "workspace"
        workspace.mkdir(parents=True)
        
        # Create test commands with measurable durations
        test_commands = [
            'sleep 0.1',
            'sleep 0.1',
            'sleep 0.1',
        ]
        
        stage = TestExecutionStage(
            test_commands=test_commands,
            environment_name="test-env",
            commit_sha="a" * 40,
            workspace_dir=str(workspace)
        )
        
        # Execute tests and store results
        stage.test_results = stage.execute_all_tests()
        
        # Save results
        output_file = Path(temp_dir) / "test-results.json"
        stage.save_test_results(str(output_file))
        
        # Read back
        with open(output_file, 'r') as f:
            data = json.load(f)
        
        # Calculate sum of individual durations
        individual_sum = sum(r['duration_seconds'] for r in data['test_results'])
        
        # Total duration should match (within small tolerance for rounding)
        assert abs(data['total_duration_seconds'] - individual_sum) < 0.01
        
        # Total duration should be at least 0.3 seconds (3 * 0.1)
        assert data['total_duration_seconds'] >= 0.3


# Feature: aphex-pipeline, Property 13: Test result capture (empty test list)
def test_property_13_test_result_capture_empty_test_list():
    """
    Property 13: Test result capture (empty test list)
    
    For any test execution with no tests, the results should still be captured
    with appropriate empty values.
    
    Validates: Requirements 6.3
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir) / "workspace"
        workspace.mkdir(parents=True)
        
        stage = TestExecutionStage(
            test_commands=[],
            environment_name="test-env",
            commit_sha="a" * 40,
            workspace_dir=str(workspace)
        )
        
        # Execute tests (none) and store results
        stage.test_results = stage.execute_all_tests()
        
        # Save results
        output_file = Path(temp_dir) / "test-results.json"
        stage.save_test_results(str(output_file))
        
        # Read back
        with open(output_file, 'r') as f:
            data = json.load(f)
        
        # Verify structure is still valid
        assert data['environment_name'] == 'test-env'
        assert data['commit_sha'] == 'a' * 40
        assert data['test_results'] == []
        assert data['overall_status'] == 'passed'  # No failures means passed
        assert data['total_duration_seconds'] == 0.0
