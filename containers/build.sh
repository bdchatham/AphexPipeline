#!/bin/bash
#
# Build script for AphexPipeline container images
#
# This script builds both the builder and deployer container images
# and optionally pushes them to Amazon ECR.
#
# Usage:
#   ./build.sh [OPTIONS]
#
# Options:
#   --push              Push images to ECR after building
#   --region REGION     AWS region for ECR (default: us-east-1)
#   --account ACCOUNT   AWS account ID (required for --push)
#   --tag TAG           Image tag (default: latest)
#   --builder-only      Build only the builder image
#   --deployer-only     Build only the deployer image
#   --help              Show this help message

set -e

# Default values
PUSH=false
REGION="us-east-1"
ACCOUNT=""
TAG="latest"
BUILD_BUILDER=true
BUILD_DEPLOYER=true

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --push)
            PUSH=true
            shift
            ;;
        --region)
            REGION="$2"
            shift 2
            ;;
        --account)
            ACCOUNT="$2"
            shift 2
            ;;
        --tag)
            TAG="$2"
            shift 2
            ;;
        --builder-only)
            BUILD_DEPLOYER=false
            shift
            ;;
        --deployer-only)
            BUILD_BUILDER=false
            shift
            ;;
        --help)
            grep '^#' "$0" | grep -v '#!/bin/bash' | sed 's/^# //'
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Validate required parameters for push
if [ "$PUSH" = true ] && [ -z "$ACCOUNT" ]; then
    echo "Error: --account is required when using --push"
    echo "Use --help for usage information"
    exit 1
fi

# Set image names
if [ "$PUSH" = true ]; then
    ECR_REGISTRY="${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com"
    BUILDER_IMAGE="${ECR_REGISTRY}/aphex-pipeline/builder:${TAG}"
    DEPLOYER_IMAGE="${ECR_REGISTRY}/aphex-pipeline/deployer:${TAG}"
else
    BUILDER_IMAGE="aphex-pipeline/builder:${TAG}"
    DEPLOYER_IMAGE="aphex-pipeline/deployer:${TAG}"
fi

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=========================================="
echo "AphexPipeline Container Image Build"
echo "=========================================="
echo "Region:  ${REGION}"
echo "Tag:     ${TAG}"
echo "Push:    ${PUSH}"
if [ "$PUSH" = true ]; then
    echo "Account: ${ACCOUNT}"
    echo "Registry: ${ECR_REGISTRY}"
fi
echo "=========================================="
echo ""

# Build builder image
if [ "$BUILD_BUILDER" = true ]; then
    echo "Building builder image..."
    docker build \
        -t "${BUILDER_IMAGE}" \
        -f "${SCRIPT_DIR}/builder/Dockerfile" \
        "${SCRIPT_DIR}/builder"
    echo "✓ Builder image built: ${BUILDER_IMAGE}"
    echo ""
fi

# Build deployer image
if [ "$BUILD_DEPLOYER" = true ]; then
    echo "Building deployer image..."
    docker build \
        -t "${DEPLOYER_IMAGE}" \
        -f "${SCRIPT_DIR}/deployer/Dockerfile" \
        "${SCRIPT_DIR}/deployer"
    echo "✓ Deployer image built: ${DEPLOYER_IMAGE}"
    echo ""
fi

# Push to ECR if requested
if [ "$PUSH" = true ]; then
    echo "Logging in to ECR..."
    aws ecr get-login-password --region "${REGION}" | \
        docker login --username AWS --password-stdin "${ECR_REGISTRY}"
    echo "✓ Logged in to ECR"
    echo ""
    
    # Create ECR repositories if they don't exist
    if [ "$BUILD_BUILDER" = true ]; then
        echo "Ensuring ECR repository exists for builder..."
        aws ecr describe-repositories \
            --repository-names aphex-pipeline/builder \
            --region "${REGION}" 2>/dev/null || \
        aws ecr create-repository \
            --repository-name aphex-pipeline/builder \
            --region "${REGION}" \
            --image-scanning-configuration scanOnPush=true \
            --encryption-configuration encryptionType=AES256
        echo "✓ ECR repository ready for builder"
        echo ""
    fi
    
    if [ "$BUILD_DEPLOYER" = true ]; then
        echo "Ensuring ECR repository exists for deployer..."
        aws ecr describe-repositories \
            --repository-names aphex-pipeline/deployer \
            --region "${REGION}" 2>/dev/null || \
        aws ecr create-repository \
            --repository-name aphex-pipeline/deployer \
            --region "${REGION}" \
            --image-scanning-configuration scanOnPush=true \
            --encryption-configuration encryptionType=AES256
        echo "✓ ECR repository ready for deployer"
        echo ""
    fi
    
    # Push images
    if [ "$BUILD_BUILDER" = true ]; then
        echo "Pushing builder image to ECR..."
        docker push "${BUILDER_IMAGE}"
        echo "✓ Builder image pushed: ${BUILDER_IMAGE}"
        echo ""
    fi
    
    if [ "$BUILD_DEPLOYER" = true ]; then
        echo "Pushing deployer image to ECR..."
        docker push "${DEPLOYER_IMAGE}"
        echo "✓ Deployer image pushed: ${DEPLOYER_IMAGE}"
        echo ""
    fi
fi

echo "=========================================="
echo "Build complete!"
echo "=========================================="
echo ""
echo "Images built:"
if [ "$BUILD_BUILDER" = true ]; then
    echo "  - ${BUILDER_IMAGE}"
fi
if [ "$BUILD_DEPLOYER" = true ]; then
    echo "  - ${DEPLOYER_IMAGE}"
fi
echo ""

if [ "$PUSH" = false ]; then
    echo "To push these images to ECR, run:"
    echo "  ./build.sh --push --account <your-account-id> --region ${REGION}"
    echo ""
fi
