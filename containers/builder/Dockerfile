# Builder Container Image for AphexPipeline
# 
# This container is used in the Build Stage to:
# - Clone the repository at a specific commit
# - Execute user-defined build commands
# - Package and upload artifacts to S3
#
# Requirements: Node.js, Python, build tools, AWS CLI, CDK CLI, git

FROM node:20-bullseye

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    AWS_DEFAULT_REGION=us-east-1

# Install system dependencies and build tools
RUN apt-get update && apt-get install -y \
    # Version control
    git \
    # Python and pip
    python3 \
    python3-pip \
    python3-venv \
    # Build essentials
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

# Install AWS CDK CLI globally
RUN npm install -g aws-cdk

# Install common Python packages for build scripts
RUN pip3 install --no-cache-dir \
    pyyaml \
    boto3 \
    requests

# Create workspace directory
RUN mkdir -p /workspace
WORKDIR /workspace

# Verify installations
RUN node --version && \
    npm --version && \
    python --version && \
    git --version && \
    aws --version && \
    cdk --version

# Default command (will be overridden by Argo Workflow)
CMD ["/bin/bash"]
