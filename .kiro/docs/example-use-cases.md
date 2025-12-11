# Example Use Cases

This document provides real-world examples of how to use AphexPipeline for different scenarios.

## Use Case 1: Simple Web Application

### Scenario

Deploy a serverless web application with:
- Lambda functions for API
- DynamoDB for data storage
- CloudFront for content delivery
- Single environment (production)

### Configuration

**aphex-config.yaml**:
```yaml
version: "1.0"

build:
  commands:
    - npm install
    - npm run build
    - npm run test

environments:
  - name: production
    region: us-east-1
    account: "123456789012"
    stacks:
      - name: WebAppStack
        path: lib/web-app-stack.ts
    tests:
      commands:
        - npm run integration-test
```

**lib/web-app-stack.ts**:
```typescript
import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront';

export class WebAppStack extends cdk.Stack {
  constructor(scope: cdk.App, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // DynamoDB table
    const table = new dynamodb.Table(this, 'DataTable', {
      partitionKey: { name: 'id', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
    });

    // Lambda function
    const apiFunction = new lambda.Function(this, 'ApiFunction', {
      runtime: lambda.Runtime.NODEJS_18_X,
      handler: 'index.handler',
      code: lambda.Code.fromAsset('dist/lambda'),
      environment: {
        TABLE_NAME: table.tableName,
      },
    });

    table.grantReadWriteData(apiFunction);

    // CloudFront distribution
    const distribution = new cloudfront.Distribution(this, 'Distribution', {
      defaultBehavior: {
        origin: new origins.HttpOrigin('example.com'),
      },
    });

    new cdk.CfnOutput(this, 'ApiUrl', {
      value: apiFunction.functionUrl?.url || 'N/A',
    });
  }
}
```

### Workflow

1. Developer pushes code to main branch
2. Validation stage checks configuration and credentials
3. Build stage runs `npm install`, `npm run build`, `npm run test`
4. Pipeline deployment stage updates AphexPipeline (if needed)
5. Production environment stage:
   - Synthesizes WebAppStack
   - Deploys to us-east-1
   - Runs integration tests
6. Workflow completes, notification sent

## Use Case 2: Multi-Environment Microservices

### Scenario

Deploy a microservices application with:
- Multiple services (API, Worker, Frontend)
- Three environments (dev, staging, prod)
- Different AWS accounts for staging and prod
- Post-deployment smoke tests

### Configuration

**aphex-config.yaml**:
```yaml
version: "1.0"

build:
  commands:
    - npm install
    - npm run build:all
    - npm run test:unit

environments:
  - name: dev
    region: us-east-1
    account: "111111111111"
    stacks:
      - name: NetworkStack
        path: lib/network-stack.ts
      - name: DatabaseStack
        path: lib/database-stack.ts
      - name: ApiStack
        path: lib/api-stack.ts
      - name: WorkerStack
        path: lib/worker-stack.ts
      - name: FrontendStack
        path: lib/frontend-stack.ts
    tests:
      commands:
        - npm run test:smoke -- --env=dev

  - name: staging
    region: us-west-2
    account: "222222222222"
    stacks:
      - name: NetworkStack
        path: lib/network-stack.ts
      - name: DatabaseStack
        path: lib/database-stack.ts
      - name: ApiStack
        path: lib/api-stack.ts
      - name: WorkerStack
        path: lib/worker-stack.ts
      - name: FrontendStack
        path: lib/frontend-stack.ts
    tests:
      commands:
        - npm run test:smoke -- --env=staging
        - npm run test:integration -- --env=staging

  - name: prod
    region: us-east-1
    account: "333333333333"
    stacks:
      - name: NetworkStack
        path: lib/network-stack.ts
      - name: DatabaseStack
        path: lib/database-stack.ts
      - name: ApiStack
        path: lib/api-stack.ts
      - name: WorkerStack
        path: lib/worker-stack.ts
      - name: FrontendStack
        path: lib/frontend-stack.ts
    tests:
      commands:
        - npm run test:smoke -- --env=prod
```

### Stack Dependencies

**lib/network-stack.ts**:
```typescript
export class NetworkStack extends cdk.Stack {
  public readonly vpc: ec2.Vpc;

  constructor(scope: cdk.App, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    this.vpc = new ec2.Vpc(this, 'Vpc', {
      maxAzs: 2,
      natGateways: 1,
    });

    new cdk.CfnOutput(this, 'VpcId', {
      value: this.vpc.vpcId,
      exportName: `${this.stackName}-VpcId`,
    });
  }
}
```

**lib/database-stack.ts**:
```typescript
export class DatabaseStack extends cdk.Stack {
  constructor(scope: cdk.App, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // Import VPC from NetworkStack
    const vpcId = cdk.Fn.importValue(`NetworkStack-VpcId`);
    const vpc = ec2.Vpc.fromLookup(this, 'Vpc', { vpcId });

    const cluster = new rds.DatabaseCluster(this, 'Database', {
      engine: rds.DatabaseClusterEngine.auroraPostgres({
        version: rds.AuroraPostgresEngineVersion.VER_14_6,
      }),
      vpc,
      instanceProps: {
        instanceType: ec2.InstanceType.of(
          ec2.InstanceClass.T3,
          ec2.InstanceSize.MEDIUM
        ),
      },
    });

    new cdk.CfnOutput(this, 'ClusterEndpoint', {
      value: cluster.clusterEndpoint.hostname,
      exportName: `${this.stackName}-ClusterEndpoint`,
    });
  }
}
```

### Workflow

1. Developer pushes code to main branch
2. Validation stage checks configuration and credentials for all 3 accounts
3. Build stage runs build and unit tests
4. Pipeline deployment stage updates AphexPipeline
5. Dev environment stage:
   - Deploys 5 stacks in order (Network → Database → API → Worker → Frontend)
   - Runs smoke tests
6. Staging environment stage:
   - Assumes cross-account role for account 222222222222
   - Deploys 5 stacks in order
   - Runs smoke tests and integration tests
7. Prod environment stage:
   - Assumes cross-account role for account 333333333333
   - Deploys 5 stacks in order
   - Runs smoke tests
8. Workflow completes, notification sent

## Use Case 3: Infrastructure with Manual Approval

### Scenario

Deploy infrastructure with:
- Automatic deployment to dev
- Manual approval before prod deployment
- Rollback capability

### Configuration

**aphex-config.yaml**:
```yaml
version: "1.0"

build:
  commands:
    - npm install
    - npm run build

environments:
  - name: dev
    region: us-east-1
    account: "123456789012"
    stacks:
      - name: InfraStack
        path: lib/infra-stack.ts
    tests:
      commands:
        - npm run test:dev

  # Manual approval step would be added here via Argo Workflows suspend step
  # This requires customizing the WorkflowTemplate generator

  - name: prod
    region: us-east-1
    account: "987654321098"
    stacks:
      - name: InfraStack
        path: lib/infra-stack.ts
    tests:
      commands:
        - npm run test:prod
```

**Customized WorkflowTemplate** (add suspend step):
```yaml
# In workflow_template_generator.py, add:
- name: approval
  suspend: {}
  
# Then continue with prod deployment
```

### Workflow

1. Developer pushes code to main branch
2. Validation and build stages complete
3. Dev environment deploys automatically
4. Workflow suspends and waits for manual approval
5. Operator reviews changes and approves via Argo UI
6. Prod environment deploys
7. Workflow completes

## Use Case 4: Multi-Region Deployment

### Scenario

Deploy application to multiple regions for:
- High availability
- Disaster recovery
- Geographic distribution

### Configuration

**aphex-config.yaml**:
```yaml
version: "1.0"

build:
  commands:
    - npm install
    - npm run build

environments:
  - name: us-east
    region: us-east-1
    account: "123456789012"
    stacks:
      - name: AppStack
        path: lib/app-stack.ts
    tests:
      commands:
        - npm run test:region -- --region=us-east-1

  - name: us-west
    region: us-west-2
    account: "123456789012"
    stacks:
      - name: AppStack
        path: lib/app-stack.ts
    tests:
      commands:
        - npm run test:region -- --region=us-west-2

  - name: eu-west
    region: eu-west-1
    account: "123456789012"
    stacks:
      - name: AppStack
        path: lib/app-stack.ts
    tests:
      commands:
        - npm run test:region -- --region=eu-west-1
```

**lib/app-stack.ts** (region-aware):
```typescript
export class AppStack extends cdk.Stack {
  constructor(scope: cdk.App, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // Use region-specific configuration
    const region = this.region;
    
    const bucket = new s3.Bucket(this, 'Bucket', {
      bucketName: `my-app-${region}`,
      versioned: true,
    });

    const distribution = new cloudfront.Distribution(this, 'Distribution', {
      defaultBehavior: {
        origin: new origins.S3Origin(bucket),
      },
      // Route 53 would handle multi-region routing
    });

    new cdk.CfnOutput(this, 'DistributionUrl', {
      value: distribution.distributionDomainName,
    });
  }
}
```

### Workflow

1. Developer pushes code to main branch
2. Validation and build stages complete
3. us-east environment deploys to us-east-1
4. us-west environment deploys to us-west-2
5. eu-west environment deploys to eu-west-1
6. All regions tested independently
7. Workflow completes

## Use Case 5: Data Pipeline with Dependencies

### Scenario

Deploy a data processing pipeline with:
- S3 buckets for data storage
- Lambda functions for processing
- Step Functions for orchestration
- Glue jobs for ETL
- Athena for querying

### Configuration

**aphex-config.yaml**:
```yaml
version: "1.0"

build:
  commands:
    - pip install -r requirements.txt
    - python -m pytest tests/

environments:
  - name: production
    region: us-east-1
    account: "123456789012"
    stacks:
      - name: DataStorageStack
        path: lib/data-storage-stack.ts
      - name: ProcessingStack
        path: lib/processing-stack.ts
      - name: OrchestrationStack
        path: lib/orchestration-stack.ts
      - name: AnalyticsStack
        path: lib/analytics-stack.ts
    tests:
      commands:
        - python -m pytest tests/integration/
```

**Stack Order** (dependencies):
1. DataStorageStack - Creates S3 buckets
2. ProcessingStack - Creates Lambda functions (depends on buckets)
3. OrchestrationStack - Creates Step Functions (depends on Lambdas)
4. AnalyticsStack - Creates Glue/Athena (depends on buckets)

### Workflow

1. Developer pushes code to main branch
2. Validation checks Python dependencies
3. Build stage runs unit tests
4. Pipeline deployment stage updates AphexPipeline
5. Production environment stage:
   - Deploys DataStorageStack (S3 buckets)
   - Deploys ProcessingStack (Lambda functions)
   - Deploys OrchestrationStack (Step Functions)
   - Deploys AnalyticsStack (Glue/Athena)
   - Runs integration tests
6. Workflow completes

## Use Case 6: Adding a New Environment

### Scenario

Start with dev and staging, then add production later.

### Initial Configuration

**aphex-config.yaml** (v1):
```yaml
version: "1.0"

build:
  commands:
    - npm install
    - npm run build

environments:
  - name: dev
    region: us-east-1
    account: "123456789012"
    stacks:
      - name: AppStack
        path: lib/app-stack.ts

  - name: staging
    region: us-west-2
    account: "123456789012"
    stacks:
      - name: AppStack
        path: lib/app-stack.ts
```

### Workflow (Initial)

1. Push triggers workflow
2. Deploys to dev and staging
3. WorkflowTemplate has 2 environment stages

### Adding Production

**aphex-config.yaml** (v2):
```yaml
version: "1.0"

build:
  commands:
    - npm install
    - npm run build

environments:
  - name: dev
    region: us-east-1
    account: "123456789012"
    stacks:
      - name: AppStack
        path: lib/app-stack.ts

  - name: staging
    region: us-west-2
    account: "123456789012"
    stacks:
      - name: AppStack
        path: lib/app-stack.ts

  - name: prod  # NEW ENVIRONMENT
    region: us-east-1
    account: "987654321098"
    stacks:
      - name: AppStack
        path: lib/app-stack.ts
    tests:
      commands:
        - npm run test:prod
```

### Workflow (After Adding Prod)

**First workflow after config change**:
1. Push triggers workflow
2. Pipeline deployment stage reads new config
3. Generates WorkflowTemplate with 3 environment stages
4. Applies updated WorkflowTemplate
5. Current workflow still deploys to dev and staging only (old template)

**Second workflow** (self-modification takes effect):
1. Push triggers workflow
2. Uses new WorkflowTemplate with 3 environment stages
3. Deploys to dev, staging, and prod
4. Production environment deployed for the first time!

This demonstrates AphexPipeline's self-modification capability.

## Best Practices

### 1. Stack Ordering

Order stacks by dependencies:
```yaml
stacks:
  - name: NetworkStack      # No dependencies
  - name: DatabaseStack     # Depends on NetworkStack
  - name: ApiStack          # Depends on DatabaseStack
  - name: FrontendStack     # Depends on ApiStack
```

### 2. Environment Progression

Deploy to environments in order of risk:
```yaml
environments:
  - name: dev       # Lowest risk
  - name: staging   # Medium risk
  - name: prod      # Highest risk
```

### 3. Testing Strategy

Add appropriate tests for each environment:
- **Dev**: Smoke tests only
- **Staging**: Smoke + integration tests
- **Prod**: Smoke tests only (avoid heavy testing in prod)

### 4. Cross-Account Setup

Use CDK bootstrap for cross-account deployments:
```bash
cdk bootstrap aws://TARGET_ACCOUNT/REGION \
  --trust PIPELINE_ACCOUNT \
  --cloudformation-execution-policies 'arn:aws:iam::aws:policy/AdministratorAccess'
```

### 5. Configuration Validation

Always validate configuration before committing:
```bash
python pipeline-scripts/validation_stage.py \
  --config aphex-config.yaml \
  --skip-aws-validation
```

### 6. Artifact Management

Implement S3 lifecycle policies to clean up old artifacts:
```typescript
artifactBucket.addLifecycleRule({
  expiration: Duration.days(90),
});
```

### 7. Monitoring

Set up CloudWatch alarms for:
- Workflow failures
- Deployment failures
- Resource exhaustion

### 8. Documentation

Document your stacks and their dependencies:
```typescript
/**
 * NetworkStack creates the VPC and networking infrastructure.
 * 
 * Outputs:
 * - VpcId: ID of the created VPC
 * 
 * Dependencies: None
 */
export class NetworkStack extends cdk.Stack {
  // ...
}
```

## Troubleshooting Examples

### Example 1: Build Failure

**Symptom**: Workflow fails at build stage

**Diagnosis**:
```bash
# View build logs
kubectl logs -n argo <workflow-pod> -c build
```

**Solution**: Fix build command or add missing tool to builder image

### Example 2: Cross-Account Deployment Failure

**Symptom**: Workflow fails when deploying to different account

**Diagnosis**:
```bash
# Test role assumption
aws sts assume-role \
  --role-arn arn:aws:iam::TARGET_ACCOUNT:role/cdk-hnb659fds-deploy-role-TARGET_ACCOUNT-REGION \
  --role-session-name test
```

**Solution**: Verify CDK bootstrap trust relationship

### Example 3: Self-Modification Not Working

**Symptom**: Config changes don't appear in next workflow

**Diagnosis**:
```bash
# Check current WorkflowTemplate
kubectl get workflowtemplate -n argo aphex-pipeline-template -o yaml
```

**Solution**: Verify pipeline deployment stage completed successfully

## References

- [Architecture Documentation](architecture.md)
- [Operations Guide](operations.md)
- [Validation Usage](../pipeline-scripts/VALIDATION_USAGE.md)
- [Requirements](../.kiro/specs/aphex-pipeline/requirements.md)
- [Design](../.kiro/specs/aphex-pipeline/design.md)
