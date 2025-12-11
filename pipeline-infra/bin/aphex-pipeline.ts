#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { AphexPipelineStack } from '../lib/aphex-pipeline-stack';

const app = new cdk.App();

// Example instantiation - users should customize these values
// In a real deployment, these would come from context variables or environment
new AphexPipelineStack(app, 'AphexPipelineStack', {
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT || process.env.AWS_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION || process.env.AWS_REGION || 'us-east-1',
  },
  description: 'AphexPipeline - Self-modifying CDK deployment platform',
  
  // Required parameters - customize for your repository
  githubOwner: process.env.GITHUB_OWNER || 'bdchatham',
  githubRepo: process.env.GITHUB_REPO || 'my-repo',
  githubTokenSecretName: process.env.GITHUB_TOKEN_SECRET || 'github-token',
  
  // Optional parameters with sensible defaults
  githubBranch: process.env.GITHUB_BRANCH || 'main',
  clusterName: process.env.CLUSTER_NAME,
  argoNamespace: process.env.ARGO_NAMESPACE,
  argoEventsNamespace: process.env.ARGO_EVENTS_NAMESPACE,
});

app.synth();
