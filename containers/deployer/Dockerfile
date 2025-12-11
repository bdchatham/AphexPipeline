# Deployer Container Image for AphexPipeline
#
# This container is used in Pipeline Deployment and Environment Stages to:
# - Clone the repository at a specific commit
# - Synthesize CDK stacks just-in-time
# - Deploy CDK stacks via CloudFormation
# - Generate and apply WorkflowTemplates using kubectl
# - Download artifacts from S3
#
# Requirements: CDK CLI, kubectl, Python, AWS CLI, YAML processing

FROM node:20-bullseye

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    AWS_DEFAULT_REGION=us-east-1 \
    KUBECTL_VERSION=v1.28.0

# Install system dependencies
RUN apt-get update && apt-get install -y \
    # Version control
    git \
    # Python and pip
    python3 \
    python3-pip \
    python3-venv \
    # Build essentials (needed for CDK synthesis)
    build-essential \
    gcc \
    g++ \
    make \
    # Utilities
    curl \
    wget \
    unzip \
    jq \
    # Clean up
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create symlink for python command
RUN ln -s /usr/bin/python3 /usr/bin/python

# Install AWS CLI v2
RUN curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" \
    && unzip awscliv2.zip \
    && ./aws/install \
    && rm -rf aws awscliv2.zip

# Install kubectl
RUN curl -LO "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/amd64/kubectl" \
    && chmod +x kubectl \
    && mv kubectl /usr/local/bin/kubectl

# Install AWS CDK CLI globally
RUN npm install -g aws-cdk

# Install Python packages for YAML processing and AWS operations
RUN pip3 install --no-cache-dir \
    pyyaml \
    boto3 \
    requests \
    jsonschema

# Create workspace directory
RUN mkdir -p /workspace
WORKDIR /workspace

# Verify installations
RUN node --version && \
    npm --version && \
    python --version && \
    git --version && \
    aws --version && \
    cdk --version && \
    kubectl version --client

# Default command (will be overridden by Argo Workflow)
CMD ["/bin/bash"]
