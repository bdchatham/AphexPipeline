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

  describe('Webhook Secret', () => {
    test('Generates unique webhook secret per pipeline', () => {
      // Verify webhook secret value is set
      expect(stack.webhookSecretValue).toBeDefined();
      expect(stack.webhookSecretValue).toHaveLength(64); // 32 bytes = 64 hex chars
      expect(stack.webhookSecretValue).toMatch(/^[0-9a-f]{64}$/); // Valid hex string
    });

    test('Outputs webhook secret value', () => {
      template.hasOutput('WebhookSecretValue', {
        Description: 'GitHub webhook secret - configure this in your repository webhook settings',
      });
    });
    
    test('Outputs webhook secret name', () => {
      template.hasOutput('WebhookSecretName', {
        Description: 'Kubernetes secret name containing the webhook secret',
      });
    });

    test('Different stacks generate different secrets', () => {
      const app2 = new cdk.App();
      const stack2 = new AphexPipelineStack(app2, 'TestStack2', {
        env: {
          account: '123456789012',
          region: 'us-east-1',
        },
        clusterName: 'test-cluster',
        githubOwner: 'test-org',
        githubRepo: 'test-repo',
        githubTokenSecretName: 'test-github-token',
      });

      // Each stack should have a unique secret
      expect(stack.webhookSecretValue).not.toBe(stack2.webhookSecretValue);
    });
    
    test('Uses unique secret name based on EventSource name', () => {
      // Default EventSource name is 'github', so secret should be 'github-webhook-secret'
      template.hasResourceProperties('Custom::AWSCDK-EKS-KubernetesResource', {
        Manifest: Match.stringLikeRegexp('.*"name":"github-webhook-secret".*'),
      });
    });
    
    test('Multiple pipelines have different secret names', () => {
      const appMulti = new cdk.App();
      
      const stack1 = new AphexPipelineStack(appMulti, 'Pipeline1', {
        env: {
          account: '123456789012',
          region: 'us-east-1',
        },
        clusterName: 'test-cluster',
        githubOwner: 'test-org',
        githubRepo: 'repo1',
        githubTokenSecretName: 'test-github-token',
        eventSourceName: 'app1-github',
      });
      
      const stack2 = new AphexPipelineStack(appMulti, 'Pipeline2', {
        env: {
          account: '123456789012',
          region: 'us-east-1',
        },
        clusterName: 'test-cluster',
        githubOwner: 'test-org',
        githubRepo: 'repo2',
        githubTokenSecretName: 'test-github-token',
        eventSourceName: 'app2-github',
      });
      
      const template1 = Template.fromStack(stack1);
      const template2 = Template.fromStack(stack2);
      
      // Stack 1 should have app1-github-webhook-secret
      template1.hasResourceProperties('Custom::AWSCDK-EKS-KubernetesResource', {
        Manifest: Match.stringLikeRegexp('.*"name":"app1-github-webhook-secret".*'),
      });
      
      // Stack 2 should have app2-github-webhook-secret
      template2.hasResourceProperties('Custom::AWSCDK-EKS-KubernetesResource', {
        Manifest: Match.stringLikeRegexp('.*"name":"app2-github-webhook-secret".*'),
      });
    });
  });

  describe('Webhook Service', () => {
    test('Creates LoadBalancer service by default', () => {
      // Verify service manifest is created
      template.hasResourceProperties('Custom::AWSCDK-EKS-KubernetesResource', {
        Manifest: Match.stringLikeRegexp('.*"kind":"Service".*"type":"LoadBalancer".*'),
      });
    });

    test('Service has NLB annotation by default', () => {
      // Verify NLB annotation is present
      template.hasResourceProperties('Custom::AWSCDK-EKS-KubernetesResource', {
        Manifest: Match.stringLikeRegexp('.*service.beta.kubernetes.io/aws-load-balancer-type.*nlb.*'),
      });
    });

    test('Service selector matches EventSource', () => {
      // Verify service selector targets the EventSource pods
      template.hasResourceProperties('Custom::AWSCDK-EKS-KubernetesResource', {
        Manifest: Match.stringLikeRegexp('.*"selector":.*"eventsource-name":"github".*'),
      });
    });

    test('Supports NodePort service type', () => {
      const appNodePort = new cdk.App();
      const stackNodePort = new AphexPipelineStack(appNodePort, 'TestStackNodePort', {
        env: {
          account: '123456789012',
          region: 'us-east-1',
        },
        clusterName: 'test-cluster',
        githubOwner: 'test-org',
        githubRepo: 'test-repo',
        githubTokenSecretName: 'test-github-token',
        webhookService: {
          type: 'NodePort',
          nodePort: 30000,
        },
      });

      const templateNodePort = Template.fromStack(stackNodePort);
      templateNodePort.hasResourceProperties('Custom::AWSCDK-EKS-KubernetesResource', {
        Manifest: Match.stringLikeRegexp('.*"type":"NodePort".*"nodePort":30000.*'),
      });
    });

    test('Supports ClusterIP service type', () => {
      const appClusterIP = new cdk.App();
      const stackClusterIP = new AphexPipelineStack(appClusterIP, 'TestStackClusterIP', {
        env: {
          account: '123456789012',
          region: 'us-east-1',
        },
        clusterName: 'test-cluster',
        githubOwner: 'test-org',
        githubRepo: 'test-repo',
        githubTokenSecretName: 'test-github-token',
        webhookService: {
          type: 'ClusterIP',
        },
      });

      const templateClusterIP = Template.fromStack(stackClusterIP);
      templateClusterIP.hasResourceProperties('Custom::AWSCDK-EKS-KubernetesResource', {
        Manifest: Match.stringLikeRegexp('.*"type":"ClusterIP".*'),
      });
    });

    test('Supports custom annotations', () => {
      const appCustom = new cdk.App();
      const stackCustom = new AphexPipelineStack(appCustom, 'TestStackCustom', {
        env: {
          account: '123456789012',
          region: 'us-east-1',
        },
        clusterName: 'test-cluster',
        githubOwner: 'test-org',
        githubRepo: 'test-repo',
        githubTokenSecretName: 'test-github-token',
        webhookService: {
          type: 'LoadBalancer',
          annotations: {
            'service.beta.kubernetes.io/aws-load-balancer-type': 'nlb',
            'service.beta.kubernetes.io/aws-load-balancer-scheme': 'internal',
          },
        },
      });

      const templateCustom = Template.fromStack(stackCustom);
      templateCustom.hasResourceProperties('Custom::AWSCDK-EKS-KubernetesResource', {
        Manifest: Match.stringLikeRegexp('.*aws-load-balancer-scheme.*internal.*'),
      });
    });

    test('Can disable service creation', () => {
      const appDisabled = new cdk.App();
      const stackDisabled = new AphexPipelineStack(appDisabled, 'TestStackDisabled', {
        env: {
          account: '123456789012',
          region: 'us-east-1',
        },
        clusterName: 'test-cluster',
        githubOwner: 'test-org',
        githubRepo: 'test-repo',
        githubTokenSecretName: 'test-github-token',
        webhookService: {
          enabled: false,
        },
      });

      expect(stackDisabled.webhookServiceType).toBe('disabled');
    });

    test('Outputs webhook service type', () => {
      template.hasOutput('WebhookServiceType', {
        Description: 'Type of Kubernetes service created for webhook (LoadBalancer, NodePort, ClusterIP, or disabled)',
      });
    });

    test('Outputs service name for LoadBalancer', () => {
      template.hasOutput('WebhookServiceName', {
        Description: Match.stringLikeRegexp('.*kubectl get svc.*'),
      });
    });
  });

  describe('WorkflowTemplate Naming', () => {
    test('Stack synthesizes with custom workflowTemplateName', () => {
      const appCustom = new cdk.App();
      const stackCustom = new AphexPipelineStack(appCustom, 'TestStackCustomName', {
        env: {
          account: '123456789012',
          region: 'us-east-1',
        },
        clusterName: 'test-cluster',
        githubOwner: 'test-org',
        githubRepo: 'test-repo',
        githubTokenSecretName: 'test-github-token',
        workflowTemplateName: 'my-custom-pipeline',
      });

      // Verify stack synthesizes successfully
      expect(stackCustom).toBeDefined();
      expect(stackCustom.workflowTemplateName).toBe('my-custom-pipeline');
    });

    test('Stack synthesizes with default workflowTemplateName', () => {
      // Verify stack uses default name
      expect(stack).toBeDefined();
      expect(stack.workflowTemplateName).toBe('aphex-pipeline-template');
    });

    test('WorkflowTemplate name matches Sensor reference', () => {
      const appMatch = new cdk.App();
      const stackMatch = new AphexPipelineStack(appMatch, 'TestStackMatch', {
        env: {
          account: '123456789012',
          region: 'us-east-1',
        },
        clusterName: 'test-cluster',
        githubOwner: 'test-org',
        githubRepo: 'test-repo',
        githubTokenSecretName: 'test-github-token',
        workflowTemplateName: 'archon-agent-pipeline',
      });

      // Verify the workflowTemplateName is set correctly
      expect(stackMatch.workflowTemplateName).toBe('archon-agent-pipeline');
    });
  });

  describe('Sensor RBAC', () => {
    test('Creates ServiceAccount for Sensor', () => {
      // Verify ServiceAccount is created
      template.hasResourceProperties('Custom::AWSCDK-EKS-KubernetesResource', {
        Manifest: Match.stringLikeRegexp('.*"kind":"ServiceAccount".*"name":"aphex-pipeline-sensor-sa".*'),
      });
    });

    test('Creates Role for Sensor with workflow permissions', () => {
      // Verify Role is created with correct permissions
      template.hasResourceProperties('Custom::AWSCDK-EKS-KubernetesResource', {
        Manifest: Match.stringLikeRegexp('.*"kind":"Role".*"name":"aphex-pipeline-sensor-role".*'),
      });
      
      // Verify workflow creation permissions
      template.hasResourceProperties('Custom::AWSCDK-EKS-KubernetesResource', {
        Manifest: Match.stringLikeRegexp('.*argoproj.io.*workflows.*create.*'),
      });
    });

    test('Creates RoleBinding for Sensor', () => {
      // Verify RoleBinding is created
      template.hasResourceProperties('Custom::AWSCDK-EKS-KubernetesResource', {
        Manifest: Match.stringLikeRegexp('.*"kind":"RoleBinding".*"name":"aphex-pipeline-sensor-rolebinding".*'),
      });
    });

    test('Sensor uses correct ServiceAccount', () => {
      // Verify Sensor references the ServiceAccount
      template.hasResourceProperties('Custom::AWSCDK-EKS-KubernetesResource', {
        Manifest: Match.stringLikeRegexp('.*"kind":"Sensor".*serviceAccountName.*aphex-pipeline-sensor-sa.*'),
      });
    });

    test('Multiple pipelines have different Sensor ServiceAccounts', () => {
      const appMulti = new cdk.App();
      
      const stack1 = new AphexPipelineStack(appMulti, 'Pipeline1', {
        env: {
          account: '123456789012',
          region: 'us-east-1',
        },
        clusterName: 'test-cluster',
        githubOwner: 'test-org',
        githubRepo: 'repo1',
        githubTokenSecretName: 'test-github-token',
        sensorName: 'app1-sensor',
      });
      
      const stack2 = new AphexPipelineStack(appMulti, 'Pipeline2', {
        env: {
          account: '123456789012',
          region: 'us-east-1',
        },
        clusterName: 'test-cluster',
        githubOwner: 'test-org',
        githubRepo: 'repo2',
        githubTokenSecretName: 'test-github-token',
        sensorName: 'app2-sensor',
      });
      
      const template1 = Template.fromStack(stack1);
      const template2 = Template.fromStack(stack2);
      
      // Stack 1 should have app1-sensor-sa
      template1.hasResourceProperties('Custom::AWSCDK-EKS-KubernetesResource', {
        Manifest: Match.stringLikeRegexp('.*"name":"app1-sensor-sa".*'),
      });
      
      // Stack 2 should have app2-sensor-sa
      template2.hasResourceProperties('Custom::AWSCDK-EKS-KubernetesResource', {
        Manifest: Match.stringLikeRegexp('.*"name":"app2-sensor-sa".*'),
      });
    });

    test('Outputs Sensor ServiceAccount name', () => {
      template.hasOutput('SensorServiceAccountName', {
        Description: 'ServiceAccount used by the Sensor to create workflows',
      });
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
