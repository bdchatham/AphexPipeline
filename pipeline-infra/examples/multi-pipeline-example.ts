#!/usr/bin/env node
/**
 * Multi-Pipeline Example
 * 
 * This example demonstrates how to deploy multiple AphexPipeline instances
 * to the same EKS cluster with proper resource isolation.
 * 
 * Prerequisites:
 * - An existing EKS cluster with Argo Workflows and Argo Events installed
 *   (deployed via the aphex-cluster package)
 * - The cluster exports its name as "AphexCluster-ClusterName" (default)
 * - GitHub tokens stored in AWS Secrets Manager for each repository
 * 
 * Note: This is a standalone example file. Copy it to your project's bin/ directory
 * and adjust the import path to use the installed package:
 * import { AphexPipelineStack } from '@bdchatham/aphex-pipeline';
 */

import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { AphexPipelineStack } from '../lib/aphex-pipeline-stack';

const app = new cdk.App();

// Common environment configuration
const env = {
  account: process.env.CDK_DEFAULT_ACCOUNT,
  region: process.env.CDK_DEFAULT_REGION || 'us-east-1',
};

// ===== Frontend Pipeline =====
// Deploys frontend application infrastructure
new AphexPipelineStack(app, 'FrontendPipeline', {
  env,
  description: 'Frontend application deployment pipeline',
  
  // Cluster reference (same cluster for all pipelines)
  clusterName: 'company-pipelines',
  
  // GitHub configuration
  githubOwner: 'my-org',
  githubRepo: 'frontend-app',
  githubTokenSecretName: 'github-token-frontend',
  githubBranch: 'main',
  
  // Unique naming to avoid conflicts with other pipelines
  workflowTemplateName: 'frontend-pipeline-template',
  eventSourceName: 'frontend-github',
  sensorName: 'frontend-pipeline-sensor',
  serviceAccountName: 'frontend-workflow-executor',
  workflowNamePrefix: 'frontend-',
  
  // Pipeline-specific artifact bucket
  artifactBucketName: `frontend-artifacts-${process.env.CDK_DEFAULT_ACCOUNT}-${env.region}`,
  artifactRetentionDays: 30, // Shorter retention for frontend assets
});

// ===== Backend API Pipeline =====
// Deploys backend API infrastructure
new AphexPipelineStack(app, 'BackendApiPipeline', {
  env,
  description: 'Backend API deployment pipeline',
  
  // Cluster reference (same cluster as frontend)
  clusterName: 'company-pipelines',
  
  // GitHub configuration
  githubOwner: 'my-org',
  githubRepo: 'backend-api',
  githubTokenSecretName: 'github-token-backend',
  githubBranch: 'main',
  
  // Unique naming to avoid conflicts
  workflowTemplateName: 'backend-api-pipeline-template',
  eventSourceName: 'backend-api-github',
  sensorName: 'backend-api-pipeline-sensor',
  serviceAccountName: 'backend-api-workflow-executor',
  workflowNamePrefix: 'backend-api-',
  
  // Pipeline-specific artifact bucket
  artifactBucketName: `backend-api-artifacts-${process.env.CDK_DEFAULT_ACCOUNT}-${env.region}`,
  artifactRetentionDays: 90, // Longer retention for API artifacts
});

// ===== Data Pipeline =====
// Deploys data processing infrastructure
new AphexPipelineStack(app, 'DataPipeline', {
  env,
  description: 'Data processing deployment pipeline',
  
  // Cluster reference (same cluster as frontend and backend)
  clusterName: 'company-pipelines',
  
  // GitHub configuration
  githubOwner: 'my-org',
  githubRepo: 'data-processing',
  githubTokenSecretName: 'github-token-data',
  githubBranch: 'main',
  
  // Unique naming to avoid conflicts
  workflowTemplateName: 'data-pipeline-template',
  eventSourceName: 'data-github',
  sensorName: 'data-pipeline-sensor',
  serviceAccountName: 'data-workflow-executor',
  workflowNamePrefix: 'data-',
  
  // Pipeline-specific artifact bucket
  artifactBucketName: `data-artifacts-${process.env.CDK_DEFAULT_ACCOUNT}-${env.region}`,
  artifactRetentionDays: 180, // Longest retention for data artifacts
});

app.synth();

/**
 * Resource Isolation Strategy:
 * 
 * 1. Unique Resource Names:
 *    - Each pipeline has unique WorkflowTemplate, EventSource, and Sensor names
 *    - This prevents naming conflicts in the shared Argo namespaces
 * 
 * 2. Separate Service Accounts:
 *    - Each pipeline has its own service account with IRSA
 *    - IAM permissions are scoped to each pipeline's needs
 * 
 * 3. Separate S3 Buckets:
 *    - Each pipeline stores artifacts in its own S3 bucket
 *    - Prevents cross-pipeline artifact access
 * 
 * 4. Shared Cluster Resources:
 *    - All pipelines share the same EKS cluster
 *    - All pipelines share Argo Workflows and Argo Events installations
 *    - All pipelines use the same argo and argo-events namespaces
 * 
 * 5. Pipeline Destruction:
 *    - Destroying one pipeline stack removes only that pipeline's resources
 *    - Other pipelines continue to function normally
 *    - The shared cluster remains intact
 * 
 * Deployment:
 * 
 *   # Deploy all pipelines
 *   cdk deploy --all
 * 
 *   # Deploy specific pipeline
 *   cdk deploy FrontendPipeline
 * 
 *   # Destroy specific pipeline (others remain intact)
 *   cdk destroy BackendApiPipeline
 * 
 * Verification:
 * 
 *   # List all WorkflowTemplates (should see all three)
 *   kubectl get workflowtemplate -n argo
 * 
 *   # List all EventSources (should see all three)
 *   kubectl get eventsource -n argo-events
 * 
 *   # List all Sensors (should see all three)
 *   kubectl get sensor -n argo-events
 * 
 *   # Verify service accounts
 *   kubectl get serviceaccount -n argo
 */
