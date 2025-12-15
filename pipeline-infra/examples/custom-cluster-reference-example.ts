#!/usr/bin/env node
/**
 * Custom Cluster Reference Example
 * 
 * This example demonstrates how to reference an existing EKS cluster
 * that uses a custom CloudFormation export name (not the default).
 * 
 * Use this when:
 * - Your cluster was deployed with a custom export name
 * - You have multiple clusters and need to specify which one to use
 * - You're using a cluster not deployed by the aphex-cluster package
 */

import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { AphexPipelineStack } from '../lib/aphex-pipeline-stack';

const app = new cdk.App();

// ===== Example 1: Specific Cluster Name =====
// Reference a cluster with a specific name
new AphexPipelineStack(app, 'PipelineWithSpecificCluster', {
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: 'us-east-1',
  },
  
  // Reference cluster by name
  clusterName: 'my-company-eks-cluster',
  
  // GitHub configuration
  githubOwner: 'my-org',
  githubRepo: 'my-app',
  githubTokenSecretName: 'github-token',
});

// ===== Example 2: Production vs Development Clusters =====
// Deploy to different clusters based on environment
const isProd = process.env.ENVIRONMENT === 'production';

new AphexPipelineStack(app, isProd ? 'ProdPipeline' : 'DevPipeline', {
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: 'us-east-1',
  },
  
  // Different clusters for prod and dev
  clusterName: isProd ? 'prod-cluster' : 'dev-cluster',
  
  // GitHub configuration
  githubOwner: 'my-org',
  githubRepo: 'my-app',
  githubTokenSecretName: isProd ? 'github-token-prod' : 'github-token-dev',
  githubBranch: isProd ? 'main' : 'develop',
  
  // Different naming for prod and dev
  workflowTemplateName: isProd 
    ? 'prod-pipeline-template' 
    : 'dev-pipeline-template',
  eventSourceName: isProd ? 'prod-github' : 'dev-github',
  sensorName: isProd ? 'prod-pipeline-sensor' : 'dev-pipeline-sensor',
});

// ===== Example 3: Multi-Region Deployment =====
// Deploy pipelines to clusters in different regions
const regions = ['us-east-1', 'us-west-2', 'eu-west-1'];

regions.forEach((region) => {
  new AphexPipelineStack(app, `Pipeline-${region}`, {
    env: {
      account: process.env.CDK_DEFAULT_ACCOUNT,
      region: region,
    },
    
    // Region-specific cluster
    clusterName: `company-pipelines-${region}`,
    
    // GitHub configuration
    githubOwner: 'my-org',
    githubRepo: 'my-app',
    githubTokenSecretName: 'github-token',
    
    // Region-specific naming
    workflowTemplateName: `pipeline-${region}-template`,
    eventSourceName: `github-${region}`,
    sensorName: `pipeline-${region}-sensor`,
    
    // Region-specific artifact bucket
    artifactBucketName: `artifacts-${region}-${process.env.CDK_DEFAULT_ACCOUNT}`,
  });
});

app.synth();

/**
 * Finding Your Cluster Name:
 * 
 * The cluster name is the name you gave when deploying via arbiter-pipeline-infrastructure.
 * You can find it by listing CloudFormation exports:
 * 
 *   # List all CloudFormation exports
 *   aws cloudformation list-exports --region us-east-1
 * 
 *   # Filter for cluster-related exports
 *   aws cloudformation list-exports --region us-east-1 \
 *     --query 'Exports[?contains(Name, `AphexCluster`)].{Name:Name,Value:Value}'
 * 
 * Look for exports with pattern:
 * - "AphexCluster-{clusterName}-ClusterName"
 * - "AphexCluster-{clusterName}-OIDCProviderArn"
 * - "AphexCluster-{clusterName}-KubectlRoleArn"
 * 
 * The {clusterName} part is what you pass to the clusterName prop.
 * 
 * Required Exports:
 * 
 * Your cluster must export (provided by arbiter-pipeline-infrastructure):
 * 1. AphexCluster-{clusterName}-ClusterName
 * 2. AphexCluster-{clusterName}-OIDCProviderArn
 * 3. AphexCluster-{clusterName}-KubectlRoleArn
 * 4. AphexCluster-{clusterName}-ClusterSecurityGroupId
 * 
 * Deployment:
 * 
 *   # Deploy with environment variable
 *   ENVIRONMENT=production cdk deploy ProdPipeline
 *   ENVIRONMENT=development cdk deploy DevPipeline
 * 
 *   # Deploy all regional pipelines
 *   cdk deploy --all
 */
