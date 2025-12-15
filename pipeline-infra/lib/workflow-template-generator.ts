import { AphexConfig, EnvironmentConfig } from './config-parser';

/**
 * Generates Argo WorkflowTemplate manifests from AphexPipeline configuration.
 */
export class WorkflowTemplateGenerator {
  private config: AphexConfig;
  private artifactBucketName: string;
  private serviceAccountName: string;
  private builderImage: string;
  private deployerImage: string;
  private workflowExecutionRoleArn: string;

  constructor(
    config: AphexConfig,
    artifactBucketName: string,
    serviceAccountName: string = 'workflow-executor',
    builderImage: string = 'public.ecr.aws/aphex/builder:latest',
    deployerImage: string = 'public.ecr.aws/aphex/deployer:latest',
    workflowExecutionRoleArn?: string
  ) {
    this.config = config;
    this.artifactBucketName = artifactBucketName;
    this.serviceAccountName = serviceAccountName;
    this.builderImage = builderImage;
    this.deployerImage = deployerImage;
    this.workflowExecutionRoleArn = workflowExecutionRoleArn || '';
  }

  /**
   * Generate the complete WorkflowTemplate manifest.
   */
  generate(): any {
    const stages = [
      this.generateBuildStage(),
      this.generatePipelineDeploymentStage(),
      ...this.generateEnvironmentStages(),
    ];

    return {
      apiVersion: 'argoproj.io/v1alpha1',
      kind: 'WorkflowTemplate',
      metadata: {
        name: 'aphex-pipeline-template',
        namespace: 'argo',
      },
      spec: {
        serviceAccountName: this.serviceAccountName,
        entrypoint: 'main',
        arguments: {
          parameters: [
            { name: 'commit-sha' },
            { name: 'branch' },
            { name: 'repo-url' },
            { name: 'repo-name' },
            { name: 'pusher' },
          ],
        },
        templates: [
          {
            name: 'main',
            steps: stages.map((stage, index) => [
              {
                name: stage.name,
                template: stage.name,
                arguments: stage.arguments,
              },
            ]),
          },
          ...stages,
        ],
      },
    };
  }

  /**
   * Generate the build stage template.
   */
  private generateBuildStage(): any {
    const buildCommands = this.config.build.commands.join('\n        ');

    return {
      name: 'build',
      inputs: {
        parameters: [
          { name: 'commit-sha' },
          { name: 'repo-url' },
        ],
      },
      outputs: {
        parameters: [
          {
            name: 'artifact-path',
            value: `s3://${this.artifactBucketName}/{{inputs.parameters.commit-sha}}/`,
          },
        ],
      },
      container: {
        image: this.builderImage,
        command: ['/bin/bash'],
        args: [
          '-c',
          `
        set -e
        echo "Cloning repository..."
        git clone {{inputs.parameters.repo-url}} /workspace
        cd /workspace
        git checkout {{inputs.parameters.commit-sha}}
        
        echo "Executing build commands..."
        ${buildCommands}
        
        echo "Uploading artifacts to S3..."
        if [ -d ./artifacts ]; then
          aws s3 sync ./artifacts s3://${this.artifactBucketName}/{{inputs.parameters.commit-sha}}/
        else
          echo "No artifacts directory found, skipping upload"
        fi
        
        echo "Build stage complete"
        `,
        ],
        env: [
          {
            name: 'AWS_ROLE_ARN',
            value: this.workflowExecutionRoleArn,
          },
          {
            name: 'AWS_WEB_IDENTITY_TOKEN_FILE',
            value: '/var/run/secrets/eks.amazonaws.com/serviceaccount/token',
          },
          {
            name: 'ARTIFACT_BUCKET',
            value: this.artifactBucketName,
          },
        ],
      },
      arguments: {
        parameters: [
          { name: 'commit-sha', value: '{{workflow.parameters.commit-sha}}' },
          { name: 'repo-url', value: '{{workflow.parameters.repo-url}}' },
        ],
      },
    };
  }

  /**
   * Generate the pipeline deployment stage template.
   * 
   * This stage updates pipeline-specific resources only:
   * - WorkflowTemplate (defines pipeline topology)
   * - EventSource (GitHub webhook receiver)
   * - Sensor (workflow trigger)
   * - Service Account (IRSA for AWS access)
   * - S3 Bucket (artifact storage)
   * 
   * It does NOT modify cluster infrastructure (EKS, Argo Workflows, Argo Events).
   * WorkflowTemplate updates take effect on the next workflow run, not the current one.
   */
  private generatePipelineDeploymentStage(): any {
    return {
      name: 'pipeline-deployment',
      inputs: {
        parameters: [
          { name: 'commit-sha' },
          { name: 'repo-url' },
        ],
      },
      container: {
        image: this.deployerImage,
        command: ['/bin/bash'],
        args: [
          '-c',
          `
        set -e
        
        echo "Cloning repository..."
        git clone {{inputs.parameters.repo-url}} /workspace
        cd /workspace
        git checkout {{inputs.parameters.commit-sha}}
        
        echo "Synthesizing Pipeline CDK Stack (pipeline-specific resources only)..."
        cd pipeline-infra
        npm install
        npx cdk synth AphexPipelineStack
        
        echo "Deploying Pipeline CDK Stack (updates WorkflowTemplate, EventSource, Sensor, etc.)..."
        echo "Note: This does NOT modify cluster infrastructure (EKS, Argo Workflows, Argo Events)"
        npx cdk deploy AphexPipelineStack --require-approval never
        
        echo "Pipeline deployment stage complete - changes will take effect in next workflow run"
        `,
        ],
        env: [
          {
            name: 'AWS_ROLE_ARN',
            value: this.workflowExecutionRoleArn,
          },
          {
            name: 'AWS_WEB_IDENTITY_TOKEN_FILE',
            value: '/var/run/secrets/eks.amazonaws.com/serviceaccount/token',
          },
        ],
      },
      arguments: {
        parameters: [
          { name: 'commit-sha', value: '{{workflow.parameters.commit-sha}}' },
          { name: 'repo-url', value: '{{workflow.parameters.repo-url}}' },
        ],
      },
    };
  }

  /**
   * Generate environment stage templates for each configured environment.
   */
  private generateEnvironmentStages(): any[] {
    const stages: any[] = [];

    for (const env of this.config.environments) {
      // Generate deployment stage for this environment
      stages.push(this.generateEnvironmentDeploymentStage(env));

      // Generate test stage if tests are configured
      if (env.tests) {
        stages.push(this.generateEnvironmentTestStage(env));
      }
    }

    return stages;
  }

  /**
   * Generate a deployment stage for a specific environment.
   */
  private generateEnvironmentDeploymentStage(env: EnvironmentConfig): any {
    // Generate stack deployment commands in order
    const stackDeployments = env.stacks
      .map(
        (stack) => `
        echo "Synthesizing stack: ${stack.name}..."
        npx cdk synth ${stack.name}
        
        echo "Deploying stack: ${stack.name}..."
        npx cdk deploy ${stack.name} --require-approval never
        
        echo "Capturing outputs for stack: ${stack.name}..."
        aws cloudformation describe-stacks \\
          --stack-name ${stack.name} \\
          --region ${env.region} \\
          --query 'Stacks[0].Outputs' \\
          > /tmp/${stack.name}-outputs.json || echo "No outputs for ${stack.name}"
        `
      )
      .join('\n        ');

    return {
      name: `deploy-${env.name}`,
      inputs: {
        parameters: [
          { name: 'commit-sha' },
          { name: 'repo-url' },
          { name: 'artifact-path' },
        ],
      },
      outputs: {
        parameters: [
          {
            name: 'stack-outputs',
            valueFrom: {
              path: '/tmp/stack-outputs.json',
            },
          },
        ],
      },
      container: {
        image: this.deployerImage,
        command: ['/bin/bash'],
        args: [
          '-c',
          `
        set -e
        echo "Cloning repository..."
        git clone {{inputs.parameters.repo-url}} /workspace
        cd /workspace
        git checkout {{inputs.parameters.commit-sha}}
        
        echo "Downloading artifacts from S3..."
        mkdir -p ./artifacts
        aws s3 sync {{inputs.parameters.artifact-path}} ./artifacts/ || echo "No artifacts to download"
        
        echo "Setting AWS region and account..."
        export AWS_REGION=${env.region}
        export AWS_ACCOUNT=${env.account}
        
        echo "Installing dependencies..."
        npm install
        
        echo "Deploying stacks for environment: ${env.name}..."
        ${stackDeployments}
        
        echo "Consolidating stack outputs..."
        echo "[]" > /tmp/stack-outputs.json
        
        echo "Environment ${env.name} deployment complete"
        `,
        ],
        env: [
          {
            name: 'AWS_ROLE_ARN',
            value: this.workflowExecutionRoleArn,
          },
          {
            name: 'AWS_WEB_IDENTITY_TOKEN_FILE',
            value: '/var/run/secrets/eks.amazonaws.com/serviceaccount/token',
          },
          {
            name: 'AWS_REGION',
            value: env.region,
          },
          {
            name: 'AWS_ACCOUNT',
            value: env.account,
          },
        ],
      },
      arguments: {
        parameters: [
          { name: 'commit-sha', value: '{{workflow.parameters.commit-sha}}' },
          { name: 'repo-url', value: '{{workflow.parameters.repo-url}}' },
          { name: 'artifact-path', value: '{{steps.build.outputs.parameters.artifact-path}}' },
        ],
      },
    };
  }

  /**
   * Generate a test stage for a specific environment.
   */
  private generateEnvironmentTestStage(env: EnvironmentConfig): any {
    if (!env.tests) {
      throw new Error(`No tests configured for environment: ${env.name}`);
    }

    const testCommands = env.tests.commands.join('\n        ');

    return {
      name: `test-${env.name}`,
      inputs: {
        parameters: [
          { name: 'commit-sha' },
          { name: 'repo-url' },
          { name: 'stack-outputs' },
        ],
      },
      container: {
        image: this.deployerImage,
        command: ['/bin/bash'],
        args: [
          '-c',
          `
        set -e
        echo "Cloning repository..."
        git clone {{inputs.parameters.repo-url}} /workspace
        cd /workspace
        git checkout {{inputs.parameters.commit-sha}}
        
        echo "Installing dependencies..."
        npm install
        
        echo "Running tests for environment: ${env.name}..."
        ${testCommands}
        
        echo "Tests for environment ${env.name} complete"
        `,
        ],
        env: [
          {
            name: 'AWS_ROLE_ARN',
            value: this.workflowExecutionRoleArn,
          },
          {
            name: 'AWS_WEB_IDENTITY_TOKEN_FILE',
            value: '/var/run/secrets/eks.amazonaws.com/serviceaccount/token',
          },
          {
            name: 'AWS_REGION',
            value: env.region,
          },
          {
            name: 'STACK_OUTPUTS',
            value: '{{inputs.parameters.stack-outputs}}',
          },
        ],
      },
      arguments: {
        parameters: [
          { name: 'commit-sha', value: '{{workflow.parameters.commit-sha}}' },
          { name: 'repo-url', value: '{{workflow.parameters.repo-url}}' },
          { name: 'stack-outputs', value: `{{steps.deploy-${env.name}.outputs.parameters.stack-outputs}}` },
        ],
      },
    };
  }
}
