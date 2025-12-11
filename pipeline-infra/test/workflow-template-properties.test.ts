import * as fc from 'fast-check';
import { WorkflowTemplateGenerator } from '../lib/workflow-template-generator';
import { AphexConfig, EnvironmentConfig, StackConfig, BuildConfig } from '../lib/config-parser';

/**
 * Feature: aphex-pipeline, Property 6: WorkflowTemplate generation from configuration
 * 
 * For any configuration with N environments, the generated WorkflowTemplate should contain
 * exactly N environment stages.
 * 
 * Validates: Requirements 3.5
 */
describe('Property 6: WorkflowTemplate generation from configuration', () => {
  // Arbitrary for generating valid stack configurations
  const stackConfigArb = fc.record({
    name: fc.stringMatching(/^[A-Za-z][A-Za-z0-9-]*$/),
    path: fc.stringMatching(/^[a-z0-9-/]+\.ts$/),
  });

  // Arbitrary for generating valid environment configurations
  const environmentConfigArb = fc.record({
    name: fc.stringMatching(/^[a-z][a-z0-9-]*$/),
    region: fc.constantFrom('us-east-1', 'us-west-2', 'eu-west-1', 'ap-southeast-1'),
    account: fc.stringMatching(/^[0-9]{12}$/),
    stacks: fc.array(stackConfigArb, { minLength: 1, maxLength: 5 }),
    tests: fc.option(
      fc.record({
        commands: fc.array(fc.string(), { minLength: 1, maxLength: 3 }),
      }),
      { nil: undefined }
    ),
  });

  // Arbitrary for generating valid AphexConfig
  const aphexConfigArb = fc.record({
    version: fc.constant('1.0'),
    build: fc.record({
      commands: fc.array(fc.string(), { minLength: 1, maxLength: 5 }),
    }),
    environments: fc.array(environmentConfigArb, { minLength: 1, maxLength: 10 }),
  });

  test('Generated WorkflowTemplate contains exactly N environment deployment stages for N environments', () => {
    fc.assert(
      fc.property(aphexConfigArb, (config: AphexConfig) => {
        const generator = new WorkflowTemplateGenerator(
          config,
          'test-bucket',
          'test-service-account'
        );
        const workflowTemplate = generator.generate();

        // Count environment deployment stages
        const deploymentStages = workflowTemplate.spec.templates.filter((template: any) =>
          template.name.startsWith('deploy-')
        );

        // Should have exactly N deployment stages for N environments
        expect(deploymentStages.length).toBe(config.environments.length);

        // Verify each environment has a corresponding deployment stage
        config.environments.forEach((env) => {
          const stageName = `deploy-${env.name}`;
          const stage = workflowTemplate.spec.templates.find(
            (template: any) => template.name === stageName
          );
          expect(stage).toBeDefined();
        });
      }),
      { numRuns: 100 }
    );
  });

  test('Generated WorkflowTemplate contains test stages only for environments with tests configured', () => {
    fc.assert(
      fc.property(aphexConfigArb, (config: AphexConfig) => {
        const generator = new WorkflowTemplateGenerator(
          config,
          'test-bucket',
          'test-service-account'
        );
        const workflowTemplate = generator.generate();

        // Count test stages
        const testStages = workflowTemplate.spec.templates.filter((template: any) =>
          template.name.startsWith('test-')
        );

        // Count environments with tests configured
        const envsWithTests = config.environments.filter((env) => env.tests !== undefined);

        // Should have exactly as many test stages as environments with tests
        expect(testStages.length).toBe(envsWithTests.length);

        // Verify each environment with tests has a corresponding test stage
        envsWithTests.forEach((env) => {
          const stageName = `test-${env.name}`;
          const stage = workflowTemplate.spec.templates.find(
            (template: any) => template.name === stageName
          );
          expect(stage).toBeDefined();
        });
      }),
      { numRuns: 100 }
    );
  });

  test('Generated WorkflowTemplate always contains build and pipeline-deployment stages', () => {
    fc.assert(
      fc.property(aphexConfigArb, (config: AphexConfig) => {
        const generator = new WorkflowTemplateGenerator(
          config,
          'test-bucket',
          'test-service-account'
        );
        const workflowTemplate = generator.generate();

        // Should always have build stage
        const buildStage = workflowTemplate.spec.templates.find(
          (template: any) => template.name === 'build'
        );
        expect(buildStage).toBeDefined();

        // Should always have pipeline-deployment stage
        const pipelineStage = workflowTemplate.spec.templates.find(
          (template: any) => template.name === 'pipeline-deployment'
        );
        expect(pipelineStage).toBeDefined();
      }),
      { numRuns: 100 }
    );
  });

  test('Generated WorkflowTemplate has correct structure', () => {
    fc.assert(
      fc.property(aphexConfigArb, (config: AphexConfig) => {
        const generator = new WorkflowTemplateGenerator(
          config,
          'test-bucket',
          'test-service-account'
        );
        const workflowTemplate = generator.generate();

        // Verify basic structure
        expect(workflowTemplate.apiVersion).toBe('argoproj.io/v1alpha1');
        expect(workflowTemplate.kind).toBe('WorkflowTemplate');
        expect(workflowTemplate.metadata.name).toBe('aphex-pipeline-template');
        expect(workflowTemplate.metadata.namespace).toBe('argo');
        expect(workflowTemplate.spec.serviceAccountName).toBe('test-service-account');
        expect(workflowTemplate.spec.entrypoint).toBe('main');

        // Verify arguments
        expect(workflowTemplate.spec.arguments.parameters).toHaveLength(5);
        expect(workflowTemplate.spec.arguments.parameters[0].name).toBe('commit-sha');
        expect(workflowTemplate.spec.arguments.parameters[1].name).toBe('branch');
        expect(workflowTemplate.spec.arguments.parameters[2].name).toBe('repo-url');
        expect(workflowTemplate.spec.arguments.parameters[3].name).toBe('repo-name');
        expect(workflowTemplate.spec.arguments.parameters[4].name).toBe('pusher');

        // Verify templates array exists
        expect(Array.isArray(workflowTemplate.spec.templates)).toBe(true);
        expect(workflowTemplate.spec.templates.length).toBeGreaterThan(0);

        // Verify main template exists
        const mainTemplate = workflowTemplate.spec.templates.find(
          (template: any) => template.name === 'main'
        );
        expect(mainTemplate).toBeDefined();
        expect(mainTemplate.steps).toBeDefined();
      }),
      { numRuns: 100 }
    );
  });
});
