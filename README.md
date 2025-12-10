# AphexPipeline

A self-modifying CDK deployment platform built on Amazon EKS, Argo Workflows, and Argo Events.

## Overview

AphexPipeline is a generic, reusable CI/CD platform that:
- Automatically triggers on code changes via GitHub webhooks
- Synthesizes and deploys CDK stacks just-in-time at each stage
- Dynamically modifies its own workflow topology based on configuration
- Supports multi-environment, multi-account deployments
- Provides comprehensive logging and monitoring

## Project Structure

```
.
├── pipeline-infra/          # CDK infrastructure for the pipeline itself
│   ├── bin/                 # CDK app entry point
│   ├── lib/                 # CDK stack definitions
│   └── test/                # Infrastructure tests
├── pipeline-scripts/        # Python scripts for workflow generation
│   └── tests/               # Script tests
├── .argo/                   # Argo Workflows and Events configurations
├── aphex-config.yaml        # Pipeline configuration
└── aphex-config.schema.json # Configuration schema
```

## Prerequisites

- AWS CLI configured with appropriate credentials
- Node.js 18+ and npm
- Python 3.9+
- AWS CDK CLI (`npm install -g aws-cdk`)
- kubectl (for EKS cluster management)

## Getting Started

### 1. Install Dependencies

```bash
# Install CDK dependencies
cd pipeline-infra
npm install
cd ..

# Install Python dependencies
cd pipeline-scripts
pip install -r requirements.txt
cd ..
```

### 2. Configure

Edit `aphex-config.yaml` to define your environments and build process.

### 3. Bootstrap

See the design document for detailed bootstrap instructions.

## Development

### Running Tests

```bash
# CDK infrastructure tests
cd pipeline-infra
npm test

# Python script tests
cd pipeline-scripts
pytest
```

### Building

```bash
# Compile TypeScript
cd pipeline-infra
npm run build
```

## Documentation

- [Requirements](.kiro/specs/aphex-pipeline/requirements.md)
- [Design](.kiro/specs/aphex-pipeline/design.md)
- [Tasks](.kiro/specs/aphex-pipeline/tasks.md)

## License

MIT
