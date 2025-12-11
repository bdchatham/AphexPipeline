import * as fs from 'fs';
import * as yaml from 'js-yaml';
import * as path from 'path';

/**
 * Configuration for a CDK stack.
 */
export interface StackConfig {
  name: string;
  path: string;
}

/**
 * Configuration for test execution.
 */
export interface TestConfig {
  commands: string[];
}

/**
 * Configuration for a deployment environment.
 */
export interface EnvironmentConfig {
  name: string;
  region: string;
  account: string;
  stacks: StackConfig[];
  tests?: TestConfig;
}

/**
 * Configuration for build stage.
 */
export interface BuildConfig {
  commands: string[];
}

/**
 * Complete AphexPipeline configuration.
 */
export interface AphexConfig {
  version: string;
  build: BuildConfig;
  environments: EnvironmentConfig[];
}

/**
 * Parser for AphexPipeline configuration files.
 */
export class ConfigParser {
  /**
   * Parse and validate a configuration file.
   * 
   * @param configPath Path to the aphex-config.yaml file
   * @returns Parsed and validated AphexConfig object
   */
  static parse(configPath: string): AphexConfig {
    // Check if file exists
    if (!fs.existsSync(configPath)) {
      throw new Error(`Configuration file not found: ${configPath}`);
    }

    // Load YAML
    const fileContents = fs.readFileSync(configPath, 'utf8');
    const configData = yaml.load(fileContents) as any;

    // Basic validation
    if (!configData.version) {
      throw new Error('Configuration missing required field: version');
    }
    if (!configData.build || !configData.build.commands) {
      throw new Error('Configuration missing required field: build.commands');
    }
    if (!configData.environments || !Array.isArray(configData.environments)) {
      throw new Error('Configuration missing required field: environments');
    }

    // Parse build config
    const build: BuildConfig = {
      commands: configData.build.commands,
    };

    // Parse environments
    const environments: EnvironmentConfig[] = configData.environments.map((envData: any) => {
      if (!envData.name || !envData.region || !envData.account || !envData.stacks) {
        throw new Error('Environment missing required fields: name, region, account, stacks');
      }

      const stacks: StackConfig[] = envData.stacks.map((stackData: any) => {
        if (!stackData.name || !stackData.path) {
          throw new Error('Stack missing required fields: name, path');
        }
        return {
          name: stackData.name,
          path: stackData.path,
        };
      });

      const tests: TestConfig | undefined = envData.tests?.commands
        ? { commands: envData.tests.commands }
        : undefined;

      return {
        name: envData.name,
        region: envData.region,
        account: envData.account,
        stacks,
        tests,
      };
    });

    return {
      version: configData.version,
      build,
      environments,
    };
  }
}
