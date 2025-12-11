import * as cdk from 'aws-cdk-lib';
import { Template, Match } from 'aws-cdk-lib/assertions';
import { AphexPipelineStack } from '../lib/aphex-pipeline-stack';

describe('AphexPipelineStack', () => {
  let app: cdk.App;
  let stack: AphexPipelineStack;
  let template: Template;

  beforeEach(() => {
    app = new cdk.App();
    stack = new AphexPipelineStack(app, 'TestStack', {
      env: {
        account: '123456789012',
        region: 'us-east-1',
      },
    });
    template = Template.fromStack(stack);
  });

  test('Stack is created', () => {
    expect(template).toBeDefined();
  });

  describe('EKS Cluster Configuration', () => {
    test('Creates EKS cluster with correct version', () => {
      template.hasResourceProperties('Custom::AWSCDK-EKS-Cluster', {
        Config: Match.objectLike({
          version: '1.28',
        }),
      });
    });

    test('Creates VPC with public and private subnets', () => {
      template.resourceCountIs('AWS::EC2::VPC', 1);
      template.resourceCountIs('AWS::EC2::Subnet', 6); // 3 AZs * 2 subnet types
    });

    test('Creates managed node group', () => {
      template.hasResourceProperties('AWS::EKS::Nodegroup', {
        ScalingConfig: {
          MinSize: 2,
          MaxSize: 10,
          DesiredSize: 3,
        },
      });
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
    test('Outputs cluster name', () => {
      template.hasOutput('ClusterName', {
        Description: 'EKS Cluster Name',
      });
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
  });
});
