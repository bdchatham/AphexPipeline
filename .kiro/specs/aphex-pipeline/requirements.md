# Requirements Document

## Introduction

This document specifies the requirements for AphexPipeline, a generic self-modifying CDK deployment platform built on Amazon EKS, Argo Workflows, and Argo Events. AphexPipeline operates as a traditional CI/CD pipeline that synthesizes and deploys CDK infrastructure just-in-time at each stage, with the unique capability to dynamically alter its own workflow topology based on configuration changes. The platform is application-agnostic and designed to be reusable across different projects and teams. After an initial manual bootstrap deployment, AphexPipeline becomes self-managing and can deploy CDK stacks to multiple environments across different AWS regions and accounts.

## Glossary

- **AphexPipeline**: The self-modifying CDK deployment platform consisting of EKS cluster, Argo Workflows, Argo Events, and pipeline logic
- **Pipeline CDK Stack**: The CDK stack that defines the AphexPipeline infrastructure (EKS cluster, Argo Workflows, Argo Events, IAM roles)
- **Application CDK Stack**: Any CDK stack that AphexPipeline deploys (user-defined infrastructure)
- **Workflow**: An Argo Workflows workflow instance that executes pipeline steps
- **WorkflowTemplate**: An Argo Workflows template that defines the pipeline topology and is applied to the cluster
- **Environment**: A deployment target with specific AWS region, account, and CDK stack configuration
- **Stage**: A step in the Argo Workflow that performs a specific action (build, deploy, test)
- **Environment Stage**: A stage that synthesizes and deploys Application CDK Stacks for a specific environment
- **Pipeline Deployment Stage**: The stage that synthesizes and deploys the Pipeline CDK Stack, then generates and applies updated WorkflowTemplates
- **Build Artifact**: Any output from the build stage (compiled code, packaged dependencies)
- **CDK Synthesis**: The process of generating CloudFormation templates from CDK code, performed just-in-time before deployment
- **Just-in-Time Synthesis**: The approach of synthesizing CDK stacks at each stage right before deploying them
- **IRSA**: IAM Roles for Service Accounts, allowing Kubernetes pods to assume AWS IAM roles
- **Argo Events**: The event-driven workflow automation framework that triggers workflows based on GitHub events
- **Bootstrap**: The initial manual deployment of AphexPipeline infrastructure
- **Self-Modification**: The ability of AphexPipeline to update its own WorkflowTemplate topology based on configuration changes

## Requirements

### Requirement 1

**User Story:** As a platform engineer, I want AphexPipeline to automatically trigger on code changes using Argo Events, so that deployments happen without manual intervention.

#### Acceptance Criteria

1. WHEN code is pushed to the main branch, THEN Argo Events SHALL trigger an Argo Workflow automatically via GitHub webhook
2. WHEN a pull request is created, THEN Argo Events SHALL trigger a validation workflow without deploying
3. WHEN a workflow is triggered, THEN AphexPipeline SHALL capture the git commit SHA and branch name from the GitHub event
4. WHEN multiple commits are pushed rapidly, THEN Argo Workflows SHALL queue workflow instances and execute them sequentially
5. WHEN a workflow is triggered, THEN AphexPipeline SHALL clone the repository with the specific commit SHA

### Requirement 2

**User Story:** As a platform engineer, I want a build stage that prepares application artifacts, so that consistent artifacts are deployed across environments.

#### Acceptance Criteria

1. WHEN the workflow starts, THEN AphexPipeline SHALL execute a configurable build stage
2. WHEN the build stage executes, THEN AphexPipeline SHALL run user-defined build commands from configuration
3. WHEN build artifacts are created, THEN AphexPipeline SHALL tag them with the git commit SHA and timestamp
4. WHEN build artifacts are created, THEN AphexPipeline SHALL store them in S3 for later deployment stages
5. WHEN the build stage fails, THEN AphexPipeline SHALL halt the workflow and send notifications

### Requirement 3

**User Story:** As a platform engineer, I want a pipeline deployment stage that updates AphexPipeline itself, so that the pipeline can self-modify based on configuration changes.

#### Acceptance Criteria

1. WHEN the build stage completes, THEN AphexPipeline SHALL execute the pipeline deployment stage
2. WHEN the pipeline deployment stage executes, THEN AphexPipeline SHALL synthesize the Pipeline CDK Stack just-in-time
3. WHEN the Pipeline CDK Stack is synthesized, THEN AphexPipeline SHALL deploy it to update the EKS cluster infrastructure if changes exist
4. WHEN the Pipeline CDK Stack deployment completes, THEN AphexPipeline SHALL read the environment configuration file
5. WHEN the environment configuration is read, THEN AphexPipeline SHALL generate an updated WorkflowTemplate with stages for each configured environment
6. WHEN the new WorkflowTemplate is generated, THEN AphexPipeline SHALL apply it directly to the Argo Workflows server using kubectl
7. WHEN the pipeline deployment stage completes, THEN AphexPipeline SHALL make the updated workflow topology visible in subsequent workflow runs

### Requirement 4

**User Story:** As a platform engineer, I want to define environments as configuration, so that I can add or modify deployment targets without changing code.

#### Acceptance Criteria

1. WHEN AphexPipeline is configured, THEN the System SHALL read environment definitions from a configuration file
2. WHEN an environment is defined, THEN the configuration SHALL specify AWS region, account, and CDK stacks to deploy
3. WHEN an environment is defined, THEN the configuration SHALL specify the order of CDK stack deployments
4. WHEN an environment is defined, THEN the configuration SHALL optionally specify pre-deployment and post-deployment hooks
5. WHEN the configuration changes, THEN AphexPipeline SHALL reflect the changes after the pipeline deployment stage

### Requirement 5

**User Story:** As a platform engineer, I want AphexPipeline to synthesize and deploy Application CDK Stacks just-in-time for each environment, so that infrastructure dependencies are satisfied.

#### Acceptance Criteria

1. WHEN an environment stage executes, THEN AphexPipeline SHALL synthesize all Application CDK Stacks for that environment just-in-time
2. WHEN Application CDK Stacks are synthesized, THEN AphexPipeline SHALL deploy them in the order specified in the environment configuration
3. WHEN a CDK stack deployment completes, THEN AphexPipeline SHALL capture and store stack outputs for use in subsequent stages
4. WHEN any CDK stack deployment fails, THEN AphexPipeline SHALL halt the workflow and prevent subsequent stack deployments
5. WHEN all CDK stacks deploy successfully, THEN AphexPipeline SHALL mark the environment stage as successful and proceed to the next stage

### Requirement 6

**User Story:** As a platform engineer, I want AphexPipeline to run tests at configurable points, so that I can validate deployments before proceeding.

#### Acceptance Criteria

1. WHEN a test stage is configured, THEN AphexPipeline SHALL execute user-defined test commands
2. WHEN tests execute, THEN AphexPipeline SHALL fail the workflow if any test fails
3. WHEN tests execute, THEN AphexPipeline SHALL capture and store test results and logs
4. WHEN tests are configured for an environment, THEN AphexPipeline SHALL run them after that environment's deployment
5. WHEN tests pass, THEN AphexPipeline SHALL proceed to the next stage in the workflow

### Requirement 7

**User Story:** As a platform engineer, I want AphexPipeline to use IAM roles for AWS access, so that deployments follow security best practices.

#### Acceptance Criteria

1. WHEN AphexPipeline executes AWS operations, THEN the System SHALL use IRSA for authentication
2. WHEN deploying to different AWS accounts, THEN AphexPipeline SHALL assume cross-account IAM roles as configured
3. WHEN accessing AWS services, THEN AphexPipeline SHALL follow least-privilege IAM policies
4. WHEN storing artifacts, THEN AphexPipeline SHALL use encrypted S3 buckets with versioning enabled
5. WHEN IAM credentials are needed, THEN AphexPipeline SHALL never store them in code or configuration files

### Requirement 8

**User Story:** As a platform engineer, I want comprehensive logging and monitoring, so that I can troubleshoot failures and track deployment history.

#### Acceptance Criteria

1. WHEN a workflow executes, THEN AphexPipeline SHALL log all step outputs to the Argo Workflows UI
2. WHEN a workflow completes, THEN AphexPipeline SHALL record execution metadata in a persistent store
3. WHEN a deployment occurs, THEN AphexPipeline SHALL emit CloudWatch metrics for deployment success and failure
4. WHEN a workflow fails, THEN AphexPipeline SHALL capture error details and stack traces
5. WHEN notifications are configured, THEN AphexPipeline SHALL send alerts with workflow status and links to the Argo UI

### Requirement 9

**User Story:** As a platform engineer, I want AphexPipeline to validate configuration before execution, so that invalid configurations are caught early.

#### Acceptance Criteria

1. WHEN a workflow starts, THEN AphexPipeline SHALL validate the configuration file against a schema
2. WHEN configuration is invalid, THEN AphexPipeline SHALL fail immediately with clear error messages
3. WHEN environment definitions reference AWS accounts, THEN AphexPipeline SHALL validate that credentials are available
4. WHEN CDK context is required, THEN AphexPipeline SHALL validate that required context values are present
5. WHEN build commands are specified, THEN AphexPipeline SHALL validate that required tools are available in the container

### Requirement 10

**User Story:** As a platform engineer, I want the Pipeline CDK Stack to be defined in code, so that AphexPipeline infrastructure is version-controlled and reproducible.

#### Acceptance Criteria

1. WHEN provisioning AphexPipeline, THEN the System SHALL define the EKS cluster using AWS CDK
2. WHEN the EKS cluster is created, THEN the System SHALL install Argo Workflows and Argo Events using Helm charts
3. WHEN Argo Workflows and Argo Events are installed, THEN the System SHALL configure IRSA for AWS access
4. WHEN the Pipeline CDK Stack is deployed, THEN the System SHALL create necessary IAM roles and policies for CDK deployments
5. WHEN the Pipeline CDK Stack is deployed, THEN the System SHALL output the Argo Workflows UI URL, Argo Events configuration, and access instructions

### Requirement 11

**User Story:** As a platform engineer, I want a manual bootstrap process to initially deploy AphexPipeline, so that the pipeline can subsequently manage itself.

#### Acceptance Criteria

1. WHEN bootstrapping AphexPipeline, THEN the System SHALL provide a script that deploys the Pipeline CDK Stack manually
2. WHEN the bootstrap script executes, THEN the System SHALL create the EKS cluster and install Argo Workflows and Argo Events
3. WHEN the bootstrap completes, THEN the System SHALL deploy the initial WorkflowTemplate and Argo Events configuration to the cluster
4. WHEN the bootstrap completes, THEN the System SHALL configure GitHub webhook integration for Argo Events
5. WHEN the bootstrap completes, THEN the System SHALL output instructions for accessing the Argo UI and verifying webhook configuration

### Requirement 12

**User Story:** As a platform engineer, I want AphexPipeline to synthesize CDK stacks just-in-time at each stage, so that the pipeline operates like a traditional CI/CD pipeline.

#### Acceptance Criteria

1. WHEN a stage requires CDK deployment, THEN AphexPipeline SHALL synthesize the CDK stack immediately before deploying it
2. WHEN synthesizing CDK stacks, THEN AphexPipeline SHALL not pre-synthesize or cache templates across stages
3. WHEN a stage completes, THEN AphexPipeline SHALL pass necessary outputs to subsequent stages via workflow parameters
4. WHEN the workflow executes, THEN AphexPipeline SHALL follow a linear progression through stages without declarative state management
5. WHEN CDK synthesis occurs, THEN AphexPipeline SHALL use the current git commit's CDK code

### Requirement 13

**User Story:** As a platform engineer, I want AphexPipeline to be application-agnostic, so that it can be reused across different projects.

#### Acceptance Criteria

1. WHEN configuring AphexPipeline, THEN the System SHALL not require application-specific code or logic
2. WHEN defining build commands, THEN AphexPipeline SHALL execute arbitrary shell commands from configuration
3. WHEN defining CDK stacks, THEN AphexPipeline SHALL deploy any CDK stack without knowledge of its contents
4. WHEN defining environments, THEN AphexPipeline SHALL support any AWS region and account combination
5. WHEN extending AphexPipeline, THEN the System SHALL provide hooks for custom pre-deployment and post-deployment logic
