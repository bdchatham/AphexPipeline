# Implementation Plan

- [x] 1. Set up project structure and core infrastructure
  - Create directory structure for pipeline-infra, scripts, and configuration
  - Initialize CDK project for Pipeline CDK Stack
  - Set up TypeScript/Python tooling and dependencies
  - _Requirements: 10.1, 11.1_

- [x] 2. Implement Pipeline CDK Stack for EKS cluster
- [x] 2.1 Create EKS cluster construct
  - Define EKS cluster with appropriate node groups
  - Configure VPC and networking for cluster
  - Set up cluster autoscaling
  - _Requirements: 10.1_

- [x] 2.2 Add Argo Workflows installation via Helm
  - Create Helm chart resource for Argo Workflows
  - Configure Argo Workflows namespace and RBAC
  - Set up Argo Workflows UI ingress
  - _Requirements: 10.2_

- [x] 2.3 Add Argo Events installation via Helm
  - Create Helm chart resource for Argo Events
  - Configure Argo Events namespace and RBAC
  - Set up EventBus and webhook endpoint
  - _Requirements: 10.2_

- [x] 2.4 Configure IRSA for AWS access
  - Create IAM role for workflow execution
  - Set up IRSA trust relationship with EKS
  - Add policies for S3, CloudFormation, IAM access
  - _Requirements: 7.1, 10.3_

- [x] 2.5 Create S3 bucket for artifacts
  - Define S3 bucket with encryption enabled
  - Enable versioning on bucket
  - Set up lifecycle policies for artifact cleanup
  - _Requirements: 7.4_

- [x] 2.6 Add CDK Stack outputs
  - Output cluster name, Argo URLs, S3 bucket name
  - Output IAM role ARNs for reference
  - _Requirements: 10.5_

- [x] 2.7 Write unit tests for Pipeline CDK Stack
  - Test EKS cluster configuration
  - Test IAM role policies
  - Test S3 bucket encryption and versioning
  - _Requirements: 10.1-10.5_

- [x] 3. Create configuration schema and validation
- [x] 3.1 Define JSON schema for aphex-config.yaml
  - Specify required fields (version, build, environments)
  - Define environment schema (name, region, account, stacks)
  - Add optional fields (tests, hooks)
  - _Requirements: 4.1, 4.2, 4.3, 4.4_

- [x] 3.2 Implement configuration parser
  - Parse YAML configuration file
  - Validate against JSON schema
  - Return structured AphexConfig object
  - _Requirements: 4.1, 9.1_

- [x] 3.3 Write property test for configuration validation
  - **Property 19: Configuration schema validation**
  - **Validates: Requirements 9.1**

- [x] 3.4 Write property test for environment schema compliance
  - **Property 8: Environment configuration schema compliance**
  - **Validates: Requirements 4.2**

- [x] 3.5 Write property test for credential absence
  - **Property 15: Credential absence in configuration**
  - **Validates: Requirements 7.5**

- [x] 4. Implement Argo Events configuration
- [x] 4.1 Create EventSource for GitHub webhooks
  - Define GitHub EventSource YAML
  - Configure webhook endpoint and authentication
  - Specify events to listen for (push, pull_request)
  - _Requirements: 1.1, 1.2_

- [x] 4.2 Create Sensor for workflow triggering
  - Define Sensor YAML with event filters
  - Filter for main branch pushes
  - Configure workflow creation trigger
  - Pass commit SHA, branch, repo URL to workflow
  - _Requirements: 1.1, 1.2, 1.3_

- [x] 4.3 Write property test for git commit extraction
  - **Property 1: Git commit extraction**
  - **Validates: Requirements 1.3**

- [x] 5. Create container images for pipeline stages
- [x] 5.1 Create builder container image
  - Base image with Node.js, Python, build tools
  - Install AWS CLI and CDK CLI
  - Add git for repository cloning
  - _Requirements: 2.1, 2.2_

- [x] 5.2 Create deployer container image
  - Base image with CDK CLI, kubectl, Python
  - Install AWS CLI for CloudFormation operations
  - Add YAML processing libraries
  - _Requirements: 3.2, 5.1_

- [x] 5.3 Create Dockerfiles and build scripts
  - Write Dockerfiles for both images
  - Create build script to push to ECR
  - Tag images with version numbers
  - _Requirements: 2.1, 3.2_

- [x] 6. Implement WorkflowTemplate generator
- [x] 6.1 Create WorkflowTemplate generator script
  - Parse aphex-config.yaml
  - Generate build stage YAML
  - Generate pipeline deployment stage YAML
  - Generate environment stages for each configured environment
  - _Requirements: 3.5, 4.1_

- [x] 6.2 Write property test for WorkflowTemplate generation
  - **Property 6: WorkflowTemplate generation from configuration**
  - **Validates: Requirements 3.5**

- [x] 6.3 Write property test for stack deployment ordering
  - **Property 9: Stack deployment ordering**
  - **Validates: Requirements 4.3, 5.2**

- [x] 6.4 Implement kubectl apply logic
  - Apply generated WorkflowTemplate to Argo
  - Handle errors from kubectl
  - _Requirements: 3.6_

- [x] 7. Implement build stage logic
- [x] 7.1 Create build stage script
  - Clone repository at specific commit SHA
  - Execute user-defined build commands
  - Package artifacts
  - _Requirements: 1.5, 2.1, 2.2_

- [x] 7.2 Write property test for repository cloning
  - **Property 2: Repository cloning at specific commit**
  - **Validates: Requirements 1.5**

- [x] 7.3 Write property test for build command execution
  - **Property 3: Build command execution**
  - **Validates: Requirements 2.2**

- [x] 7.4 Implement artifact tagging
  - Tag artifacts with commit SHA
  - Add timestamp to artifact metadata
  - _Requirements: 2.3_

- [x] 7.5 Write property test for artifact tagging
  - **Property 4: Artifact tagging**
  - **Validates: Requirements 2.3**

- [x] 7.6 Implement S3 artifact upload
  - Upload artifacts to S3 bucket
  - Use commit SHA in S3 path
  - _Requirements: 2.4_

- [x] 7.7 Write property test for artifact storage and retrieval
  - **Property 5: Artifact storage and retrieval**
  - **Validates: Requirements 2.4**

- [x] 7.8 Add error handling for build failures
  - Capture stderr and stdout
  - Store error logs in S3
  - Fail workflow on build error
  - _Requirements: 2.5_

- [x] 8. Implement pipeline deployment stage logic
- [x] 8.1 Create pipeline deployment script
  - Clone repository at commit SHA
  - Synthesize Pipeline CDK Stack
  - Deploy Pipeline CDK Stack
  - _Requirements: 3.1, 3.2, 3.3_

- [x] 8.2 Add configuration reading logic
  - Read aphex-config.yaml after deployment
  - Parse and validate configuration
  - _Requirements: 3.4_

- [x] 8.3 Integrate WorkflowTemplate generator
  - Call generator with parsed configuration
  - Apply generated WorkflowTemplate
  - _Requirements: 3.5, 3.6_

- [x] 8.4 Write property test for self-modification visibility
  - **Property 7: Self-modification visibility**
  - **Validates: Requirements 3.7, 4.5**

- [x] 8.5 Add error handling for pipeline deployment failures
  - Capture CDK errors
  - Continue with existing topology on failure
  - Log errors for debugging
  - _Requirements: 3.3_

- [x] 9. Implement environment stage logic
- [x] 9.1 Create environment deployment script
  - Clone repository at commit SHA
  - Download artifacts from S3
  - Set AWS region and account context
  - _Requirements: 5.1, 7.2_

- [x] 9.2 Implement CDK stack synthesis
  - Synthesize each Application CDK Stack just-in-time
  - Use commit-specific CDK code
  - _Requirements: 5.1, 12.1, 12.5_

- [x] 9.3 Write property test for CDK stack synthesis completeness
  - **Property 10: CDK stack synthesis completeness**
  - **Validates: Requirements 5.1**

- [x] 9.4 Write property test for just-in-time synthesis
  - **Property 23: Just-in-time synthesis**
  - **Validates: Requirements 12.1, 12.2**

- [x] 9.5 Write property test for commit-specific CDK code usage
  - **Property 25: Commit-specific CDK code usage**
  - **Validates: Requirements 12.5**

- [x] 9.6 Implement CDK stack deployment
  - Deploy stacks in configured order
  - Wait for each stack to complete before next
  - _Requirements: 5.2_

- [x] 9.7 Implement stack output capture
  - Query CloudFormation for stack outputs
  - Store outputs for subsequent stages
  - _Requirements: 5.3_

- [x] 9.8 Write property test for stack output capture
  - **Property 11: Stack output capture**
  - **Validates: Requirements 5.3**

- [x] 9.9 Write property test for stage output propagation
  - **Property 24: Stage output propagation**
  - **Validates: Requirements 12.3**

- [x] 9.10 Add error handling for CDK deployment failures
  - Capture CloudFormation error events
  - Halt workflow on stack failure
  - Store error details
  - _Requirements: 5.4_

- [x] 10. Implement test execution logic
- [x] 10.1 Create test execution script
  - Execute user-defined test commands
  - Capture test output and exit codes
  - _Requirements: 6.1_

- [x] 10.2 Write property test for test command execution
  - **Property 12: Test command execution**
  - **Validates: Requirements 6.1**

- [x] 10.3 Implement test result capture
  - Store test results (pass/fail status)
  - Store test logs
  - _Requirements: 6.3_

- [x] 10.4 Write property test for test result capture
  - **Property 13: Test result capture**
  - **Validates: Requirements 6.3**

- [x] 10.5 Add error handling for test failures
  - Fail workflow on test failure
  - Store test failure details
  - _Requirements: 6.2_

- [ ] 11. Implement cross-account IAM role assumption
- [ ] 11.1 Add cross-account role assumption logic
  - Detect when deploying to different account
  - Assume configured cross-account role
  - Use assumed role credentials for deployment
  - _Requirements: 7.2_

- [ ] 11.2 Write property test for cross-account role assumption
  - **Property 14: Cross-account role assumption**
  - **Validates: Requirements 7.2**

- [ ] 11.3 Add IAM policy for cross-account access
  - Update workflow execution role
  - Add sts:AssumeRole permission
  - _Requirements: 7.2_

- [ ] 12. Implement monitoring and logging
- [ ] 12.1 Add workflow metadata recording
  - Record workflow ID, commit SHA, timestamps
  - Store metadata in DynamoDB or S3
  - _Requirements: 8.2_

- [ ] 12.2 Write property test for workflow metadata recording
  - **Property 16: Workflow metadata recording**
  - **Validates: Requirements 8.2**

- [ ] 12.3 Implement CloudWatch metrics emission
  - Emit metrics for deployment success/failure
  - Emit metrics for workflow duration
  - _Requirements: 8.3_

- [ ] 12.4 Write property test for deployment metrics emission
  - **Property 17: Deployment metrics emission**
  - **Validates: Requirements 8.3**

- [ ] 12.5 Add notification logic
  - Send alerts on workflow completion/failure
  - Include workflow status and Argo UI link
  - Support multiple notification channels (Slack, email)
  - _Requirements: 8.5_

- [ ] 12.6 Write property test for notification delivery
  - **Property 18: Notification delivery**
  - **Validates: Requirements 8.5**

- [ ] 12.7 Configure Argo Workflows logging
  - Ensure all stage outputs logged to Argo UI
  - Configure log retention
  - _Requirements: 8.1_

- [ ] 13. Implement validation logic
- [ ] 13.1 Write property test for AWS credential validation
  - **Property 20: AWS credential validation**
  - **Validates: Requirements 9.3**

- [ ] 13.2 Write property test for CDK context validation
  - **Property 21: CDK context validation**
  - **Validates: Requirements 9.4**

- [ ] 13.3 Write property test for build tool validation
  - **Property 22: Build tool validation**
  - **Validates: Requirements 9.5**

- [ ] 13.4 Add validation to workflow start
  - Validate configuration schema
  - Validate AWS credentials
  - Validate CDK context
  - Validate build tools
  - Fail fast if validation fails
  - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

- [ ] 14. Create bootstrap script and documentation
- [ ] 14.1 Create bootstrap script
  - Script to deploy Pipeline CDK Stack
  - Script to configure kubectl
  - Script to apply initial WorkflowTemplate
  - _Requirements: 11.1, 11.2_

- [ ] 14.2 Add GitHub webhook configuration helper
  - Script or instructions to configure webhook
  - Include webhook URL from CDK outputs
  - _Requirements: 11.4_

- [ ] 14.3 Write bootstrap documentation
  - Prerequisites and setup steps
  - Step-by-step bootstrap instructions
  - Verification steps
  - _Requirements: 11.5_

- [ ] 14.4 Create example aphex-config.yaml
  - Example with single environment
  - Example with multiple environments
  - Comments explaining each field
  - _Requirements: 4.1_

- [ ] 15. Create initial WorkflowTemplate
- [ ] 15.1 Write initial WorkflowTemplate YAML
  - Define build stage
  - Define pipeline deployment stage
  - Define single dev environment stage
  - _Requirements: 11.3_

- [ ] 15.2 Test WorkflowTemplate manually
  - Apply to test cluster
  - Trigger workflow manually
  - Verify stages execute correctly
  - _Requirements: 11.3_

- [ ] 16. Integration testing
- [ ] 16.1 Set up test environment
  - Deploy test instance of AphexPipeline
  - Create test GitHub repository
  - Configure test webhook
  - _Requirements: All_

- [ ] 16.2 Test full pipeline execution
  - Trigger workflow with test commit
  - Verify build stage completes
  - Verify pipeline deployment stage completes
  - Verify environment stage completes
  - _Requirements: 1.1, 2.1, 3.1, 5.1_

- [ ] 16.3 Test self-modification
  - Add new environment to config
  - Trigger workflow
  - Verify new environment stage appears in next run
  - _Requirements: 3.7, 4.5_

- [ ] 16.4 Test error handling
  - Trigger workflow with failing build
  - Verify workflow halts and sends notification
  - Trigger workflow with failing CDK deployment
  - Verify workflow halts appropriately
  - _Requirements: 2.5, 5.4, 6.2_

- [ ] 16.5 Clean up test resources
  - Delete test workflows
  - Delete test artifacts from S3
  - Optionally tear down test pipeline
  - _Requirements: All_

- [ ] 17. Documentation and final polish
- [ ] 17.1 Write operational documentation
  - Monitoring guide
  - Troubleshooting guide
  - Maintenance procedures
  - _Requirements: All_

- [ ] 17.2 Create architecture diagrams
  - Update .kiro/docs/architecture.md
  - Include Mermaid diagrams
  - _Requirements: All_

- [ ] 17.3 Write README
  - Overview of AphexPipeline
  - Quick start guide
  - Link to detailed documentation
  - _Requirements: All_

- [ ] 17.4 Add example use case
  - Example project using AphexPipeline
  - Show how to configure for different scenarios
  - _Requirements: 13.1-13.5_

- [ ] 18. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.
