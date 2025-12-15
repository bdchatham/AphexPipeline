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
  
  // ===== Required Parameters =====
  // Customize for your GitHub repository
  githubOwner: process.env.GITHUB_OWNER || 'my-org',
  githubRepo: process.env.GITHUB_REPO || 'my-repo',
  githubTokenSecretName: process.env.GITHUB_TOKEN_SECRET || 'github-token',
  
  // ===== Cluster Reference =====
  // The pipeline references an existing EKS cluster via CloudFormation exports
  // Specify the name of the cluster deployed via arbiter-pipeline-infrastructure
  clusterName: process.env.CLUSTER_NAME || 'my-company-pipelines',
  
  // ===== Optional Parameters =====
  githubBranch: process.env.GITHUB_BRANCH || 'main',
  
  // Argo namespaces (defaults: 'argo' and 'argo-events')
  // These should match the namespaces used by your cluster setup
  argoNamespace: process.env.ARGO_NAMESPACE,
  argoEventsNamespace: process.env.ARGO_EVENTS_NAMESPACE,
  
  // Artifact storage configuration
  // artifactBucketName: 'my-custom-artifacts-bucket',
  // artifactRetentionDays: 90,
  
  // Pipeline naming (useful for multiple pipelines on same cluster)
  // workflowTemplateName: 'my-app-pipeline-template',
  // eventSourceName: 'my-app-github',
  // sensorName: 'my-app-pipeline-sensor',
});

app.synth();
