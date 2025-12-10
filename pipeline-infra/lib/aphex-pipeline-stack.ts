import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';

export class AphexPipelineStack extends cdk.Stack {
  public readonly clusterName: string;
  public readonly argoWorkflowsUrl: string;
  public readonly argoEventsWebhookUrl: string;
  public readonly artifactBucketName: string;
  public readonly workflowExecutionRoleArn: string;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // Placeholder values - will be implemented in subsequent tasks
    this.clusterName = '';
    this.argoWorkflowsUrl = '';
    this.argoEventsWebhookUrl = '';
    this.artifactBucketName = '';
    this.workflowExecutionRoleArn = '';

    // Stack outputs will be added as components are implemented
  }
}
