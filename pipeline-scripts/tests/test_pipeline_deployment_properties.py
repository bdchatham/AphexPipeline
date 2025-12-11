"""
Property-based tests for AphexPipeline deployment stage.

These tests verify universal properties that should hold for pipeline
deployment and self-modification behavior.
"""

import json
import tempfile
import yaml
from pathlib import Path
from hypothesis import given, strategies as st, settings, assume
import pytest

from config_parser import ConfigParser
from pipeline_deployment_stage import PipelineDeploymentStage


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


# Feature: aphex-pipeline, Property 7: Self-modification visibility
@settings(max_examples=100)
@given(
    initial_config=valid_config(),
    modified_config=valid_config()
)
def test_property_7_self_modification_visibility(initial_config, modified_config):
    """
    Property 7: Self-modification visibility
    
    For any configuration change that adds or removes an environment, the next
    workflow run after the pipeline deployment stage should reflect that change
    in its topology.
    
    This test verifies that:
    1. The WorkflowTemplate generator produces different templates for different configs
    2. The number of environment stages matches the number of configured environments
    3. Each environment in the config has a corresponding deployment stage
    
    Validates: Requirements 3.7, 4.5
    """
    # Ensure the configs are actually different
    assume(len(initial_config['environments']) != len(modified_config['environments']))
    
    # Create temporary directory for test files
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        
        # Create schema file (copy from project root)
        schema_path = tmpdir_path / 'aphex-config.schema.json'
        project_schema_path = Path(__file__).parent.parent.parent / 'aphex-config.schema.json'
        with open(project_schema_path, 'r') as src:
            schema_content = json.load(src)
        with open(schema_path, 'w') as dst:
            json.dump(schema_content, dst)
        
        # Test with initial configuration
        initial_config_path = tmpdir_path / 'aphex-config-initial.yaml'
        with open(initial_config_path, 'w') as f:
            yaml.dump(initial_config, f)
        
        # Create a mock deployment stage (without actual git operations)
        stage_initial = PipelineDeploymentStage(
            repo_url="https://github.com/test/repo.git",
            commit_sha="abc123",
            workspace_dir=str(tmpdir_path),
            config_file=str(initial_config_path.name),
            schema_file=str(schema_path.name)
        )
        
        # Read and parse initial configuration
        initial_parsed = stage_initial.read_configuration()
        
        # Generate WorkflowTemplate for initial config
        # Mock the artifact bucket name
        stage_initial._get_artifact_bucket_name = lambda: "test-artifact-bucket"
        initial_template_yaml = stage_initial.generate_workflow_template()
        initial_template = yaml.safe_load(initial_template_yaml)
        
        # Test with modified configuration
        modified_config_path = tmpdir_path / 'aphex-config-modified.yaml'
        with open(modified_config_path, 'w') as f:
            yaml.dump(modified_config, f)
        
        stage_modified = PipelineDeploymentStage(
            repo_url="https://github.com/test/repo.git",
            commit_sha="def456",
            workspace_dir=str(tmpdir_path),
            config_file=str(modified_config_path.name),
            schema_file=str(schema_path.name)
        )
        
        # Read and parse modified configuration
        modified_parsed = stage_modified.read_configuration()
        
        # Generate WorkflowTemplate for modified config
        stage_modified._get_artifact_bucket_name = lambda: "test-artifact-bucket"
        modified_template_yaml = stage_modified.generate_workflow_template()
        modified_template = yaml.safe_load(modified_template_yaml)
        
        # Property 1: Number of environment stages should match number of environments
        initial_env_count = len(initial_parsed.environments)
        modified_env_count = len(modified_parsed.environments)
        
        # Count deployment stages in templates (excluding build and pipeline-deployment)
        initial_deploy_stages = [
            t for t in initial_template['spec']['templates']
            if t['name'].startswith('deploy-')
        ]
        modified_deploy_stages = [
            t for t in modified_template['spec']['templates']
            if t['name'].startswith('deploy-')
        ]
        
        assert len(initial_deploy_stages) == initial_env_count, \
            f"Initial template should have {initial_env_count} deployment stages, got {len(initial_deploy_stages)}"
        
        assert len(modified_deploy_stages) == modified_env_count, \
            f"Modified template should have {modified_env_count} deployment stages, got {len(modified_deploy_stages)}"
        
        # Property 2: Each environment should have a corresponding deployment stage
        for env in initial_parsed.environments:
            stage_name = f"deploy-{env.name}"
            assert any(t['name'] == stage_name for t in initial_template['spec']['templates']), \
                f"Initial template missing deployment stage for environment: {env.name}"
        
        for env in modified_parsed.environments:
            stage_name = f"deploy-{env.name}"
            assert any(t['name'] == stage_name for t in modified_template['spec']['templates']), \
                f"Modified template missing deployment stage for environment: {env.name}"
        
        # Property 3: Templates should be different when environment counts differ
        assert len(initial_deploy_stages) != len(modified_deploy_stages), \
            "Templates should have different numbers of deployment stages"
        
        # Property 4: The main workflow steps should reflect the environment changes
        initial_main_template = next(t for t in initial_template['spec']['templates'] if t['name'] == 'main')
        modified_main_template = next(t for t in modified_template['spec']['templates'] if t['name'] == 'main')
        
        # Count steps (each step is a list with one item)
        initial_steps = initial_main_template['steps']
        modified_steps = modified_main_template['steps']
        
        # Steps include: build, pipeline-deployment, and one per environment (plus optional test stages)
        # At minimum, we should have different step counts if environment counts differ
        # (This may be equal if one config has tests and the other doesn't, but the stages themselves differ)
        
        # Verify that the environment-specific steps are different
        initial_env_step_names = [
            step[0]['name'] for step in initial_steps
            if step[0]['name'].startswith('deploy-') or step[0]['name'].startswith('test-')
        ]
        modified_env_step_names = [
            step[0]['name'] for step in modified_steps
            if step[0]['name'].startswith('deploy-') or step[0]['name'].startswith('test-')
        ]
        
        assert initial_env_step_names != modified_env_step_names, \
            "Environment-specific steps should differ between templates"


# Feature: aphex-pipeline, Property 6: WorkflowTemplate generation from configuration
@settings(max_examples=100)
@given(config_data=valid_config())
def test_property_6_workflow_template_generation(config_data):
    """
    Property 6: WorkflowTemplate generation from configuration
    
    For any configuration with N environments, the generated WorkflowTemplate
    should contain exactly N environment stages.
    
    Validates: Requirements 3.5
    """
    # Create temporary directory for test files
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        
        # Create schema file
        schema_path = tmpdir_path / 'aphex-config.schema.json'
        project_schema_path = Path(__file__).parent.parent.parent / 'aphex-config.schema.json'
        with open(project_schema_path, 'r') as src:
            schema_content = json.load(src)
        with open(schema_path, 'w') as dst:
            json.dump(schema_content, dst)
        
        # Create config file
        config_path = tmpdir_path / 'aphex-config.yaml'
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f)
        
        # Create deployment stage
        stage = PipelineDeploymentStage(
            repo_url="https://github.com/test/repo.git",
            commit_sha="abc123",
            workspace_dir=str(tmpdir_path),
            config_file=str(config_path.name),
            schema_file=str(schema_path.name)
        )
        
        # Read configuration
        parsed_config = stage.read_configuration()
        
        # Generate WorkflowTemplate
        stage._get_artifact_bucket_name = lambda: "test-artifact-bucket"
        template_yaml = stage.generate_workflow_template()
        template = yaml.safe_load(template_yaml)
        
        # Count environments in config
        env_count = len(parsed_config.environments)
        
        # Count deployment stages in template
        deploy_stages = [
            t for t in template['spec']['templates']
            if t['name'].startswith('deploy-')
        ]
        
        # Property: Number of deployment stages should equal number of environments
        assert len(deploy_stages) == env_count, \
            f"Template should have {env_count} deployment stages, got {len(deploy_stages)}"
        
        # Verify each environment has a corresponding stage
        for env in parsed_config.environments:
            stage_name = f"deploy-{env.name}"
            assert any(t['name'] == stage_name for t in template['spec']['templates']), \
                f"Template missing deployment stage for environment: {env.name}"
            
            # Verify the stage has correct environment configuration
            stage_template = next(t for t in template['spec']['templates'] if t['name'] == stage_name)
            
            # Check that the stage container has the correct environment variables
            container = stage_template['container']
            env_vars = {e['name']: e['value'] for e in container.get('env', [])}
            
            assert env_vars.get('AWS_REGION') == env.region, \
                f"Stage {stage_name} should have AWS_REGION={env.region}"
            assert env_vars.get('AWS_ACCOUNT') == env.account, \
                f"Stage {stage_name} should have AWS_ACCOUNT={env.account}"
