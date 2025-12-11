import * as fc from 'fast-check';
import { WorkflowTemplateGenerator } from '../lib/workflow-template-generator';
import { AphexConfig, EnvironmentConfig, StackConfig } from '../lib/config-parser';

/**
 * Feature: aphex-pipeline, Property 9: Stack deployment ordering
 * 
 * For any environment configuration with an ordered list of stacks, the stacks should be
 * deployed in that exact order.
 * 
 * Validates: Requirements 4.3, 5.2
 */
describe('Property 9: Stack deployment ordering', () => {
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
    stacks: fc.array(stackConfigArb, { minLength: 2, maxLength: 5 }), // At least 2 stacks to test ordering
    tests: fc.constant(undefined),
  });

  // Arbitrary for generating valid AphexConfig with unique environment names
  const aphexConfigArb = fc
    .record({
      version: fc.constant('1.0'),
      build: fc.record({
        commands: fc.array(fc.string(), { minLength: 1, maxLength: 3 }),
      }),
      environments: fc.array(environmentConfigArb, { minLength: 1, maxLength: 5 }),
    })
    .filter((config) => {
      // Ensure environment names are unique
      const envNames = config.environments.map((env) => env.name);
      const uniqueNames = new Set(envNames);
      return envNames.length === uniqueNames.size;
    });

  test('Stack deployment commands appear in the same order as configured', () => {
    fc.assert(
      fc.property(aphexConfigArb, (config: AphexConfig) => {
        const generator = new WorkflowTemplateGenerator(
          config,
          'test-bucket',
          'test-service-account'
        );
        const workflowTemplate = generator.generate();

        // For each environment, verify stack deployment order
        config.environments.forEach((env) => {
          const stageName = `deploy-${env.name}`;
          const stage = workflowTemplate.spec.templates.find(
            (template: any) => template.name === stageName
          );

          expect(stage).toBeDefined();

          // Get the deployment script from the container args
          const deploymentScript = stage.container.args[1];

          // Extract the order of stack deployments from the script
          // Look for "Deploying stack: <name>..." patterns
          const deploymentMatches = Array.from(
            deploymentScript.matchAll(/Deploying stack: ([A-Za-z0-9-]+)\.\.\./g)
          ) as RegExpMatchArray[];

          // Should have as many deployment commands as stacks
          expect(deploymentMatches.length).toBe(env.stacks.length);

          // Verify the order matches the configuration
          deploymentMatches.forEach((match, index) => {
            const stackNameInScript = match[1];
            const expectedStackName = env.stacks[index].name;
            expect(stackNameInScript).toBe(expectedStackName);
          });
        });
      }),
      { numRuns: 100 }
    );
  });

  test('Stack synthesis commands appear before deployment commands in the same order', () => {
    fc.assert(
      fc.property(aphexConfigArb, (config: AphexConfig) => {
        const generator = new WorkflowTemplateGenerator(
          config,
          'test-bucket',
          'test-service-account'
        );
        const workflowTemplate = generator.generate();

        // For each environment, verify synthesis happens before deployment
        config.environments.forEach((env) => {
          const stageName = `deploy-${env.name}`;
          const stage = workflowTemplate.spec.templates.find(
            (template: any) => template.name === stageName
          );

          expect(stage).toBeDefined();

          // Get the deployment script from the container args
          const deploymentScript = stage.container.args[1];

          // Extract all stack-related commands (synthesis and deployment)
          const synthMatches = Array.from(
            deploymentScript.matchAll(/Synthesizing stack: ([A-Za-z0-9-]+)\.\.\./g)
          ) as RegExpMatchArray[];
          const deployMatches = Array.from(
            deploymentScript.matchAll(/Deploying stack: ([A-Za-z0-9-]+)\.\.\./g)
          ) as RegExpMatchArray[];

          // Should have as many synthesis commands as stacks
          expect(synthMatches.length).toBe(env.stacks.length);
          expect(deployMatches.length).toBe(env.stacks.length);

          // Verify synthesis and deployment order matches configuration
          env.stacks.forEach((stack, index) => {
            expect(synthMatches[index][1]).toBe(stack.name);
            expect(deployMatches[index][1]).toBe(stack.name);
          });

          // Verify that for each stack, synthesis appears before deployment
          env.stacks.forEach((stack) => {
            const synthIndex = deploymentScript.indexOf(`Synthesizing stack: ${stack.name}`);
            const deployIndex = deploymentScript.indexOf(`Deploying stack: ${stack.name}`);
            expect(synthIndex).toBeLessThan(deployIndex);
          });
        });
      }),
      { numRuns: 100 }
    );
  });

  test('Stack output capture commands appear after deployment in the same order', () => {
    fc.assert(
      fc.property(aphexConfigArb, (config: AphexConfig) => {
        const generator = new WorkflowTemplateGenerator(
          config,
          'test-bucket',
          'test-service-account'
        );
        const workflowTemplate = generator.generate();

        // For each environment, verify output capture happens after deployment
        config.environments.forEach((env) => {
          const stageName = `deploy-${env.name}`;
          const stage = workflowTemplate.spec.templates.find(
            (template: any) => template.name === stageName
          );

          expect(stage).toBeDefined();

          // Get the deployment script from the container args
          const deploymentScript = stage.container.args[1];

          // Extract output capture commands
          const outputMatches = Array.from(
            deploymentScript.matchAll(/Capturing outputs for stack: ([A-Za-z0-9-]+)\.\.\./g)
          ) as RegExpMatchArray[];

          // Should have as many output capture commands as stacks
          expect(outputMatches.length).toBe(env.stacks.length);

          // Verify output capture order matches configuration
          outputMatches.forEach((match, index) => {
            const stackNameInScript = match[1];
            const expectedStackName = env.stacks[index].name;
            expect(stackNameInScript).toBe(expectedStackName);
          });

          // Verify that for each stack, deployment appears before output capture
          env.stacks.forEach((stack) => {
            const deployIndex = deploymentScript.indexOf(`Deploying stack: ${stack.name}`);
            const outputIndex = deploymentScript.indexOf(`Capturing outputs for stack: ${stack.name}`);
            expect(deployIndex).toBeLessThan(outputIndex);
          });
        });
      }),
      { numRuns: 100 }
    );
  });

  test('Stacks are deployed sequentially, not in parallel', () => {
    fc.assert(
      fc.property(aphexConfigArb, (config: AphexConfig) => {
        const generator = new WorkflowTemplateGenerator(
          config,
          'test-bucket',
          'test-service-account'
        );
        const workflowTemplate = generator.generate();

        // For each environment, verify stacks are deployed in a single container
        // (not as separate parallel steps)
        config.environments.forEach((env) => {
          const stageName = `deploy-${env.name}`;
          const stage = workflowTemplate.spec.templates.find(
            (template: any) => template.name === stageName
          );

          expect(stage).toBeDefined();

          // Should have a single container, not multiple steps
          expect(stage.container).toBeDefined();
          expect(stage.steps).toBeUndefined();

          // The container should have all stack deployments in sequence
          const deploymentScript = stage.container.args[1];
          
          // Verify all stacks are mentioned in the script
          env.stacks.forEach((stack) => {
            expect(deploymentScript).toContain(`Deploying stack: ${stack.name}`);
          });
        });
      }),
      { numRuns: 100 }
    );
  });
});
