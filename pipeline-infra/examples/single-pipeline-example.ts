#!/usr/bin/env node
/**
 * Single Pipeline Example
 * 
 * This example demonstrates the minimal configuration needed to deploy
 * a single AphexPipeline instance to an existing EKS cluster.
 * 
 * Prerequisites:
 * - An existing EKS cluster with Argo Workflows and Argo Events installed
 *   (deployed via the aphex-cluster package)
 * - The cluster exports its name as "AphexCluster-ClusterName" (default)
 * - GitHub token stored in AWS Secrets Manager
 */

import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { AphexPipelineStack } from '../lib/aphex-pipeline-stack';

const app = new cdk.App();

// Minimal configuration - only required parameters
new AphexPipelineStack(app, 'MyAppPipeline', {
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION || 'us-east-1',
  },
  
  // Required: Cluster name (deployed via arbiter-pipeline-infrastructure)
  clusterName: 'company-pipelines',
  
  // Required: GitHub repository configuration
  githubOwner: 'my-org',
  githubRepo: 'my-app',
  githubTokenSecretName: 'github-token',
  
  // Optional: All other parameters use sensible defaults
  // - GitHub branch: 'main'
  // - Argo namespaces: 'argo' and 'argo-events'
  // - Resource names: Default naming conventions
  // - Artifact bucket: Auto-generated name
  // - Container images: Convention-based ECR URIs (account.dkr.ecr.region.amazonaws.com/arbiter-pipeline-*:version)
});

app.synth();

/**
 * What This Creates:
 * 
 * 1. Pipeline-Specific Resources:
 *    - WorkflowTemplate: 'aphex-pipeline-template'
 *    - EventSource: 'github'
 *    - Sensor: 'aphex-pipeline-sensor'
 *    - Service Account: 'workflow-executor' (with IRSA)
 *    - S3 Bucket: 'aphex-pipeline-artifacts-{account}-{region}'
 * 
 * 2. IAM Permissions:
 *    - S3 access for artifacts
 *    - CloudFormation access for CDK deployments
 *    - Cross-account role assumption
 *    - ECR access for container images
 * 
 * 3. Argo Configuration:
 *    - GitHub webhook receiver
 *    - Workflow trigger on main branch pushes
 *    - Logging configuration
 * 
 * Deployment:
 * 
 *   # Ensure you have AWS credentials configured
 *   aws configure
 * 
 *   # Bootstrap CDK (if not already done)
 *   cdk bootstrap
 * 
 *   # Deploy the pipeline
 *   cdk deploy MyAppPipeline
 * 
 *   # After deployment, configure GitHub webhook
 *   # The webhook URL will be in the stack outputs
 * 
 * Verification:
 * 
 *   # Check that resources were created
 *   kubectl get workflowtemplate aphex-pipeline-template -n argo
 *   kubectl get eventsource github -n argo-events
 *   kubectl get sensor aphex-pipeline-sensor -n argo-events
 * 
 *   # Trigger a workflow by pushing to main branch
 *   git commit --allow-empty -m "Test pipeline"
 *   git push origin main
 * 
 *   # Watch workflow execution in Argo UI
 *   kubectl port-forward -n argo svc/argo-server 2746:2746
 *   # Then open http://localhost:2746
 */
