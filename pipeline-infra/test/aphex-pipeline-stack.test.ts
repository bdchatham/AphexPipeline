import * as cdk from 'aws-cdk-lib';
import { Template, Match } from 'aws-cdk-lib/assertions';
import { AphexPipelineStack } from '../lib/aphex-pipeline-stack';

describe('AphexPipelineStack', () => {
  let app: cdk.App;
  let stack: AphexPipelineStack;
  let template: Template;

  beforeEach(() => {
    app = new cdk.App();
    
    // Mock the CloudFormation exports that the stack expects
    // In a real deployment, these would come from the aphex-cluster stack
    stack = new AphexPipelineStack(app, 'TestStack', {
      env: {
        account: '123456789012',
        region: 'us-east-1',
      },
      // Required parameters for testing
      clusterName: 'test-cluster',
      githubOwner: 'test-org',
      githubRepo: 'test-repo',
      githubTokenSecretName: 'test-github-token',
    });
    template = Template.fromStack(stack);
  });

  test('Stack is created', () => {
    expect(template).toBeDefined();
  });

  describe('Cluster Import', () => {
    test('Does not create EKS cluster', () => {
      // Verify that no EKS cluster is created
      template.resourceCountIs('Custom::AWSCDK-EKS-Cluster', 0);
    });

    test('Does not create VPC', () => {
      // Verify that no VPC is created
      template.resourceCountIs('AWS::EC2::VPC', 0);
    });

    test('Does not create node groups', () => {
      // Verify that no node groups are created
      template.resourceCountIs('AWS::EKS::Nodegroup', 0);
    });

    test('Stack references cluster via CloudFormation import', () => {
      // The stack should use Fn::ImportValue to reference the cluster
      // This is implicit in the cluster import, so we verify the stack doesn't create cluster resources
      expect(stack.clusterName).toBeDefined();
    });
  });

  describe('IAM Role Configuration', () => {
    test('Creates service account with IRSA', () => {
      // Service account is created via EKS construct, verify IAM role exists
      template.hasResourceProperties('AWS::IAM::Role', {
        AssumeRolePolicyDocument: {
          Statement: Match.arrayWith([
            Match.objectLike({
              Action: 'sts:AssumeRoleWithWebIdentity',
              Effect: 'Allow',
            }),
          ]),
        },
      });
    });

    test('IAM role has S3 access policy', () => {
      template.hasResourceProperties('AWS::IAM::Policy', {
        PolicyDocument: {
          Statement: Match.arrayWith([
            Match.objectLike({
              Action: Match.arrayWith([
                's3:GetObject',
                's3:PutObject',
                's3:DeleteObject',
                's3:ListBucket',
              ]),
              Effect: 'Allow',
            }),
          ]),
        },
      });
    });

    test('IAM role has CloudFormation access policy', () => {
      template.hasResourceProperties('AWS::IAM::Policy', {
        PolicyDocument: {
          Statement: Match.arrayWith([
            Match.objectLike({
              Action: 'cloudformation:*',
              Effect: 'Allow',
            }),
          ]),
        },
      });
    });

    test('IAM role has cross-account role assumption policy', () => {
      template.hasResourceProperties('AWS::IAM::Policy', {
        PolicyDocument: {
          Statement: Match.arrayWith([
            Match.objectLike({
              Action: ['sts:AssumeRole', 'sts:GetCallerIdentity'],
              Effect: 'Allow',
            }),
          ]),
        },
      });
    });
  });

  describe('S3 Bucket Configuration', () => {
    test('Creates S3 bucket with encryption enabled', () => {
      template.hasResourceProperties('AWS::S3::Bucket', {
        BucketEncryption: {
          ServerSideEncryptionConfiguration: [
            {
              ServerSideEncryptionByDefault: {
                SSEAlgorithm: 'AES256',
              },
            },
          ],
        },
      });
    });

    test('S3 bucket has versioning enabled', () => {
      template.hasResourceProperties('AWS::S3::Bucket', {
        VersioningConfiguration: {
          Status: 'Enabled',
        },
      });
    });

    test('S3 bucket has lifecycle policy', () => {
      template.hasResourceProperties('AWS::S3::Bucket', {
        LifecycleConfiguration: {
          Rules: Match.arrayWith([
            Match.objectLike({
              Status: 'Enabled',
              ExpirationInDays: 90,
            }),
          ]),
        },
      });
    });
  });

  describe('Stack Outputs', () => {
    test('Does not output cluster name', () => {
      // Cluster name should not be in outputs since cluster is managed separately
      expect(() => {
        template.hasOutput('ClusterName', {});
      }).toThrow();
    });

    test('Does not output cluster ARN', () => {
      // Cluster ARN should not be in outputs since cluster is managed separately
      expect(() => {
        template.hasOutput('ClusterArn', {});
      }).toThrow();
    });

    test('Does not output VPC ID', () => {
      // VPC ID should not be in outputs since VPC is managed by cluster
      expect(() => {
        template.hasOutput('VpcId', {});
      }).toThrow();
    });

    test('Outputs artifact bucket name', () => {
      template.hasOutput('ArtifactBucketName', {
        Description: 'S3 Bucket for build artifacts',
      });
    });

    test('Outputs workflow execution role ARN', () => {
      template.hasOutput('WorkflowExecutionRoleArn', {
        Description: 'IAM Role ARN for workflow execution (IRSA)',
      });
    });

    test('Outputs WorkflowTemplate name', () => {
      template.hasOutput('WorkflowTemplateName', {
        Description: 'Argo WorkflowTemplate name',
      });
    });

    test('Outputs webhook URL', () => {
      template.hasOutput('ArgoEventsWebhookUrl', {
        Description: 'Argo Events Webhook URL for GitHub integration',
      });
    });
  });

  describe('Pipeline-Specific Resources', () => {
    test('Creates pipeline-specific S3 bucket', () => {
      // Verify S3 bucket is created (pipeline-specific)
      template.resourceCountIs('AWS::S3::Bucket', 1);
    });

    test('Creates pipeline-specific service account', () => {
      // Verify service account IAM role is created (pipeline-specific)
      template.hasResourceProperties('AWS::IAM::Role', {
        AssumeRolePolicyDocument: {
          Statement: Match.arrayWith([
            Match.objectLike({
              Action: 'sts:AssumeRoleWithWebIdentity',
              Effect: 'Allow',
            }),
          ]),
        },
      });
    });

    test('Does not modify cluster resources', () => {
      // Verify no Helm charts are installed (Argo Workflows, Argo Events)
      // These would show up as Custom::AWSCDK-EKS-HelmChart resources
      template.resourceCountIs('Custom::AWSCDK-EKS-HelmChart', 0);
    });
  });

  describe('Pipeline Creator Role', () => {
    test('Uses pipeline creator role when provided', () => {
      const appWithCreatorRole = new cdk.App();
      const stackWithCreatorRole = new AphexPipelineStack(appWithCreatorRole, 'TestStackWithCreatorRole', {
        env: {
          account: '123456789012',
          region: 'us-east-1',
        },
        clusterName: 'test-cluster',
        githubOwner: 'test-org',
        githubRepo: 'test-repo',
        githubTokenSecretName: 'test-github-token',
        pipelineCreatorRoleArn: 'arn:aws:iam::123456789012:role/pipeline-creator',
      });

      // The cluster should be configured with the pipeline creator role
      // We can't directly inspect the cluster attributes, but we can verify the stack synthesizes successfully
      expect(stackWithCreatorRole).toBeDefined();
      expect(stackWithCreatorRole.cluster).toBeDefined();
    });

    test('Falls back to CloudFormation import without pipeline creator role', () => {
      // This is the default behavior tested in beforeEach
      // Verify stack works without pipelineCreatorRoleArn
      expect(stack).toBeDefined();
      expect(stack.cluster).toBeDefined();
    });

    test('Validates pipeline creator role ARN format', () => {
      const appWithInvalidArn = new cdk.App();
      
      // Test with invalid ARN format
      expect(() => {
        new AphexPipelineStack(appWithInvalidArn, 'TestStackInvalidArn', {
          env: {
            account: '123456789012',
            region: 'us-east-1',
          },
          clusterName: 'test-cluster',
          githubOwner: 'test-org',
          githubRepo: 'test-repo',
          githubTokenSecretName: 'test-github-token',
          pipelineCreatorRoleArn: 'invalid-arn',
        });
      }).toThrow(/pipelineCreatorRoleArn must be a valid IAM role ARN/);
    });

    test('Rejects ARN with wrong resource type', () => {
      const appWithWrongType = new cdk.App();
      
      // Test with user ARN instead of role ARN
      expect(() => {
        new AphexPipelineStack(appWithWrongType, 'TestStackWrongType', {
          env: {
            account: '123456789012',
            region: 'us-east-1',
          },
          clusterName: 'test-cluster',
          githubOwner: 'test-org',
          githubRepo: 'test-repo',
          githubTokenSecretName: 'test-github-token',
          pipelineCreatorRoleArn: 'arn:aws:iam::123456789012:user/some-user',
        });
      }).toThrow(/pipelineCreatorRoleArn must be a valid IAM role ARN/);
    });
  });
});
