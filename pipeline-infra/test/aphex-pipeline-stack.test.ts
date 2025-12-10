import * as cdk from 'aws-cdk-lib';
import { Template } from 'aws-cdk-lib/assertions';
import { AphexPipelineStack } from '../lib/aphex-pipeline-stack';

describe('AphexPipelineStack', () => {
  test('Stack is created', () => {
    const app = new cdk.App();
    const stack = new AphexPipelineStack(app, 'TestStack');
    const template = Template.fromStack(stack);
    
    // Basic test to ensure stack can be synthesized
    expect(template).toBeDefined();
  });
});
