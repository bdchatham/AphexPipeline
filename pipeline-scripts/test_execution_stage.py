"""
Test execution stage script for AphexPipeline.

This module provides functionality to execute test stages:
- Execute user-defined test commands
- Capture test output and exit codes
- Store test results (pass/fail status)
- Store test logs
"""

import os
import subprocess
import sys
import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass, asdict


class TestExecutionError(Exception):
    """Exception raised when test execution stage fails."""
    pass


@dataclass
class TestCommandResult:
    """Result of executing a single test command."""
    command: str
    exit_code: int
    stdout: str
    stderr: str
    status: str  # "passed" or "failed"
    duration_seconds: float


@dataclass
class TestExecutionResult:
    """Result of executing all test commands."""
    environment_name: str
    commit_sha: str
    timestamp: str
    test_results: List[TestCommandResult]
    overall_status: str  # "passed" or "failed"
    total_duration_seconds: float


class TestExecutionStage:
    """Handles the test execution stage."""
    
    def __init__(
        self,
        test_commands: List[str],
        environment_name: str,
        commit_sha: str,
        workspace_dir: str = "/workspace"
    ):
        """
        Initialize the test execution stage.
        
        Args:
            test_commands: List of test commands to execute
            environment_name: Name of the environment being tested
            commit_sha: Commit SHA being tested
            workspace_dir: Directory to execute tests in
        """
        self.test_commands = test_commands
        self.environment_name = environment_name
        self.commit_sha = commit_sha
        self.workspace_dir = Path(workspace_dir)
        self.timestamp = datetime.utcnow().isoformat() + "Z"
        self.test_results: List[TestCommandResult] = []
    
    def execute_test_command(self, command: str) -> TestCommandResult:
        """
        Execute a single test command and capture its output and exit code.
        
        Args:
            command: Test command to execute
            
        Returns:
            TestCommandResult with execution details
        """
        print(f"\nExecuting test command: {command}")
        
        start_time = datetime.utcnow()
        
        try:
            # Execute command in workspace directory
            result = subprocess.run(
                command,
                cwd=str(self.workspace_dir),
                shell=True,
                capture_output=True,
                text=True,
                timeout=3600  # 1 hour timeout for tests
            )
            
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            
            # Determine status based on exit code
            status = "passed" if result.returncode == 0 else "failed"
            
            # Print output
            if result.stdout:
                print(result.stdout)
            
            if result.stderr:
                print(result.stderr, file=sys.stderr)
            
            if status == "passed":
                print(f"✓ Test command passed (exit code: {result.returncode})")
            else:
                print(f"✗ Test command failed (exit code: {result.returncode})", file=sys.stderr)
            
            return TestCommandResult(
                command=command,
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                status=status,
                duration_seconds=duration
            )
            
        except subprocess.TimeoutExpired as e:
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            
            error_msg = f"Test command timed out after {duration} seconds"
            print(error_msg, file=sys.stderr)
            
            return TestCommandResult(
                command=command,
                exit_code=-1,
                stdout=e.stdout.decode() if e.stdout else "",
                stderr=error_msg,
                status="failed",
                duration_seconds=duration
            )
        except Exception as e:
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            
            error_msg = f"Failed to execute test command: {str(e)}"
            print(error_msg, file=sys.stderr)
            
            return TestCommandResult(
                command=command,
                exit_code=-1,
                stdout="",
                stderr=error_msg,
                status="failed",
                duration_seconds=duration
            )
    
    def execute_all_tests(self) -> List[TestCommandResult]:
        """
        Execute all test commands in order.
        
        All commands are executed even if some fail, to capture complete results.
        
        Returns:
            List of TestCommandResult for each command
        """
        if not self.test_commands:
            print("No test commands to execute")
            return []
        
        print(f"\n{'='*80}")
        print(f"Executing {len(self.test_commands)} test command(s)")
        print(f"Environment: {self.environment_name}")
        print(f"Commit SHA: {self.commit_sha}")
        print(f"{'='*80}")
        
        results = []
        
        for i, command in enumerate(self.test_commands, 1):
            print(f"\n[{i}/{len(self.test_commands)}] Test command {i}")
            result = self.execute_test_command(command)
            results.append(result)
        
        return results
    
    def save_test_results(self, output_file: str = "/tmp/test-results.json") -> None:
        """
        Store test results (pass/fail status) and logs to a JSON file.
        
        Args:
            output_file: Path to output file
        """
        try:
            # Calculate overall status and total duration
            overall_status = "passed"
            total_duration = 0.0
            
            for result in self.test_results:
                total_duration += result.duration_seconds
                if result.status == "failed":
                    overall_status = "failed"
            
            # Create test execution result
            test_execution_result = TestExecutionResult(
                environment_name=self.environment_name,
                commit_sha=self.commit_sha,
                timestamp=self.timestamp,
                test_results=self.test_results,
                overall_status=overall_status,
                total_duration_seconds=total_duration
            )
            
            # Write to file
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w') as f:
                json.dump(asdict(test_execution_result), f, indent=2)
            
            print(f"\nTest results saved to {output_file}")
            
        except Exception as e:
            error_msg = f"Failed to save test results: {str(e)}"
            print(error_msg, file=sys.stderr)
            raise TestExecutionError(error_msg) from e
    
    def save_test_logs(self, log_dir: str = "/tmp/test-logs") -> None:
        """
        Store individual test logs to separate files.
        
        Args:
            log_dir: Directory to store log files
        """
        try:
            log_path = Path(log_dir)
            log_path.mkdir(parents=True, exist_ok=True)
            
            for i, result in enumerate(self.test_results, 1):
                # Create log file for this test
                log_file = log_path / f"test-{i}.log"
                
                with open(log_file, 'w') as f:
                    f.write(f"Command: {result.command}\n")
                    f.write(f"Exit Code: {result.exit_code}\n")
                    f.write(f"Status: {result.status}\n")
                    f.write(f"Duration: {result.duration_seconds:.2f} seconds\n")
                    f.write(f"\n{'='*80}\n")
                    f.write(f"STDOUT:\n")
                    f.write(f"{'='*80}\n")
                    f.write(result.stdout)
                    f.write(f"\n{'='*80}\n")
                    f.write(f"STDERR:\n")
                    f.write(f"{'='*80}\n")
                    f.write(result.stderr)
                
                print(f"Test log saved to {log_file}")
            
        except Exception as e:
            error_msg = f"Failed to save test logs: {str(e)}"
            print(error_msg, file=sys.stderr)
            # Don't raise exception for log saving failures
    
    def print_summary(self) -> None:
        """Print a summary of test execution results."""
        print(f"\n{'='*80}")
        print(f"Test Execution Summary")
        print(f"{'='*80}")
        
        passed_count = sum(1 for r in self.test_results if r.status == "passed")
        failed_count = sum(1 for r in self.test_results if r.status == "failed")
        total_duration = sum(r.duration_seconds for r in self.test_results)
        
        print(f"Total tests: {len(self.test_results)}")
        print(f"Passed: {passed_count}")
        print(f"Failed: {failed_count}")
        print(f"Total duration: {total_duration:.2f} seconds")
        
        if failed_count > 0:
            print(f"\nFailed tests:")
            for i, result in enumerate(self.test_results, 1):
                if result.status == "failed":
                    print(f"  [{i}] {result.command}")
                    print(f"      Exit code: {result.exit_code}")
        
        print(f"{'='*80}\n")
    
    def run(self) -> TestExecutionResult:
        """
        Execute the complete test execution stage.
        
        Returns:
            TestExecutionResult with test results
            
        Raises:
            TestExecutionError: If tests fail (after capturing results)
        """
        try:
            # Execute all test commands
            self.test_results = self.execute_all_tests()
            
            # Save test results to file
            self.save_test_results()
            
            # Save individual test logs
            self.save_test_logs()
            
            # Print summary
            self.print_summary()
            
            # Check if any tests failed
            failed_tests = [r for r in self.test_results if r.status == "failed"]
            
            if failed_tests:
                error_msg = f"{len(failed_tests)} test(s) failed"
                print(f"\n✗ {error_msg}", file=sys.stderr)
                raise TestExecutionError(error_msg)
            
            print(f"\n✓ All tests passed")
            
            # Calculate overall status and total duration
            overall_status = "passed"
            total_duration = sum(r.duration_seconds for r in self.test_results)
            
            return TestExecutionResult(
                environment_name=self.environment_name,
                commit_sha=self.commit_sha,
                timestamp=self.timestamp,
                test_results=self.test_results,
                overall_status=overall_status,
                total_duration_seconds=total_duration
            )
            
        except TestExecutionError:
            # Re-raise test execution errors
            raise
        except Exception as e:
            error_msg = f"Unexpected error during test execution: {str(e)}"
            print(error_msg, file=sys.stderr)
            raise TestExecutionError(error_msg) from e


def main():
    """
    Main entry point for the test execution stage script.
    
    Expected environment variables:
    - TEST_COMMANDS: JSON array of test commands
    - ENVIRONMENT_NAME: Name of the environment being tested
    - COMMIT_SHA: Commit SHA being tested
    - WORKSPACE_DIR: (Optional) Directory to execute tests in
    """
    # Get parameters from environment variables
    test_commands_json = os.environ.get('TEST_COMMANDS', '[]')
    environment_name = os.environ.get('ENVIRONMENT_NAME', 'unknown')
    commit_sha = os.environ.get('COMMIT_SHA', 'unknown')
    workspace_dir = os.environ.get('WORKSPACE_DIR', '/workspace')
    
    try:
        test_commands = json.loads(test_commands_json)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid TEST_COMMANDS JSON: {e}", file=sys.stderr)
        sys.exit(1)
    
    if not test_commands:
        print("No test commands specified, skipping test execution")
        sys.exit(0)
    
    # Create and run test execution stage
    stage = TestExecutionStage(
        test_commands=test_commands,
        environment_name=environment_name,
        commit_sha=commit_sha,
        workspace_dir=workspace_dir
    )
    
    try:
        result = stage.run()
        print(f"\nTest execution completed successfully")
        sys.exit(0)
    except TestExecutionError as e:
        print(f"\nTest execution failed: {str(e)}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
