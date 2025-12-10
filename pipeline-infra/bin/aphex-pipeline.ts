#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { AphexPipelineStack } from '../lib/aphex-pipeline-stack';

const app = new cdk.App();

new AphexPipelineStack(app, 'AphexPipelineStack', {
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT || process.env.AWS_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION || process.env.AWS_REGION || 'us-east-1',
  },
  description: 'AphexPipeline - Self-modifying CDK deployment platform',
});

app.synth();
