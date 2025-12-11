"""
Configuration parser for AphexPipeline.

This module provides functionality to parse and validate aphex-config.yaml files
against the JSON schema.
"""

import json
import yaml
from dataclasses import dataclass
from typing import List, Optional
from pathlib import Path
from jsonschema import validate, ValidationError


@dataclass
class StackConfig:
    """Configuration for a CDK stack."""
    name: str
    path: str


@dataclass
class TestConfig:
    """Configuration for test execution."""
    commands: List[str]


@dataclass
class EnvironmentConfig:
    """Configuration for a deployment environment."""
    name: str
    region: str
    account: str
    stacks: List[StackConfig]
    tests: Optional[TestConfig] = None


@dataclass
class BuildConfig:
    """Configuration for build stage."""
    commands: List[str]


@dataclass
class AphexConfig:
    """Complete AphexPipeline configuration."""
    version: str
    build: BuildConfig
    environments: List[EnvironmentConfig]


class ConfigParser:
    """Parser for AphexPipeline configuration files."""
    
    def __init__(self, schema_path: str = "aphex-config.schema.json"):
        """
        Initialize the configuration parser.
        
        Args:
            schema_path: Path to the JSON schema file
        """
        self.schema_path = schema_path
        self.schema = self._load_schema()
    
    def _load_schema(self) -> dict:
        """Load the JSON schema from file."""
        schema_file = Path(self.schema_path)
        if not schema_file.exists():
            raise FileNotFoundError(f"Schema file not found: {self.schema_path}")
        
        with open(schema_file, 'r') as f:
            return json.load(f)
    
    def parse(self, config_path: str) -> AphexConfig:
        """
        Parse and validate a configuration file.
        
        Args:
            config_path: Path to the aphex-config.yaml file
            
        Returns:
            Parsed and validated AphexConfig object
            
        Raises:
            FileNotFoundError: If config file doesn't exist
            ValidationError: If config doesn't match schema
            yaml.YAMLError: If YAML is malformed
        """
        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        # Load YAML
        with open(config_file, 'r') as f:
            config_data = yaml.safe_load(f)
        
        # Validate against schema
        validate(instance=config_data, schema=self.schema)
        
        # Parse into structured objects
        return self._parse_config(config_data)
    
    def _parse_config(self, config_data: dict) -> AphexConfig:
        """Convert raw config data into AphexConfig object."""
        # Parse build config
        build_config = BuildConfig(
            commands=config_data['build']['commands']
        )
        
        # Parse environments
        environments = []
        for env_data in config_data['environments']:
            # Parse stacks
            stacks = [
                StackConfig(name=stack['name'], path=stack['path'])
                for stack in env_data['stacks']
            ]
            
            # Parse optional tests
            tests = None
            if 'tests' in env_data and 'commands' in env_data['tests']:
                tests = TestConfig(commands=env_data['tests']['commands'])
            
            environments.append(EnvironmentConfig(
                name=env_data['name'],
                region=env_data['region'],
                account=env_data['account'],
                stacks=stacks,
                tests=tests
            ))
        
        return AphexConfig(
            version=config_data['version'],
            build=build_config,
            environments=environments
        )


def parse_config(config_path: str, schema_path: str = "aphex-config.schema.json") -> AphexConfig:
    """
    Convenience function to parse a configuration file.
    
    Args:
        config_path: Path to the aphex-config.yaml file
        schema_path: Path to the JSON schema file
        
    Returns:
        Parsed and validated AphexConfig object
    """
    parser = ConfigParser(schema_path=schema_path)
    return parser.parse(config_path)
