#!/bin/bash
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

# Deployment script for Prebid Server on AWS
# This script handles AMT bidder file copying and CDK deployment
# Two-step deployment: BidderSimulatorStack first, then PrebidServerStack with outputs as parameters

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
DEPLOY_BIDDING_SIMULATOR="false"
ENABLE_LOG_ANALYTICS="false"
ENABLE_RTB_REQUESTER_GATEWAY="false"
SIMULATOR_CONNECTIVITY="rtb-fabric"
CONTAINER_IMAGE=""
AWS_PROFILE=""
AWS_REGION=""
CDK_COMMAND="deploy"
SKIP_COPY="false"

# Function to print colored messages
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to authenticate container runtime with ECR public registry
authenticate_ecr_public() {
    local container_runtime=$1
    
    print_info "Authenticating $container_runtime with ECR public registry..."
    
    local login_cmd
    if [ -n "$AWS_PROFILE" ]; then
        login_cmd="aws ecr-public get-login-password --region us-east-1 --profile $AWS_PROFILE"
    else
        login_cmd="aws ecr-public get-login-password --region us-east-1"
    fi
    
    if $login_cmd 2>/dev/null | $container_runtime login --username AWS --password-stdin public.ecr.aws > /dev/null 2>&1; then
        print_info "Successfully authenticated with ECR public registry"
    else
        print_warn "Failed to authenticate with ECR public registry - continuing anyway"
    fi
}

# Function to authenticate container runtime with ECR private registry
authenticate_ecr_private() {
    local container_runtime=$1
    
    print_info "Authenticating $container_runtime with ECR private registry..."
    
    # Get AWS account ID and region
    local aws_account_id
    local aws_region="${AWS_REGION:-us-east-1}"
    
    if [ -n "$AWS_PROFILE" ]; then
        aws_account_id=$(aws sts get-caller-identity --profile "$AWS_PROFILE" --query Account --output text 2>/dev/null)
    else
        aws_account_id=$(aws sts get-caller-identity --query Account --output text 2>/dev/null)
    fi
    
    if [ -z "$aws_account_id" ]; then
        print_error "Failed to get AWS account ID"
        print_error "Please verify AWS credentials are configured correctly"
        return 1
    fi
    
    local ecr_registry="${aws_account_id}.dkr.ecr.${aws_region}.amazonaws.com"
    
    local login_cmd
    if [ -n "$AWS_PROFILE" ]; then
        login_cmd="aws ecr get-login-password --region $aws_region --profile $AWS_PROFILE"
    else
        login_cmd="aws ecr get-login-password --region $aws_region"
    fi
    
    if $login_cmd 2>/dev/null | $container_runtime login --username AWS --password-stdin "$ecr_registry" > /dev/null 2>&1; then
        print_info "Successfully authenticated with ECR private registry ($ecr_registry)"
        return 0
    else
        print_error "Failed to authenticate with ECR private registry"
        print_error "This will cause CDK deployment to fail when pushing container images"
        return 1
    fi
}

# Function to get CloudFormation stack output value
get_stack_output() {
    local stack_name=$1
    local output_key=$2
    local aws_args=""
    
    if [ -n "$AWS_PROFILE" ]; then
        aws_args="$aws_args --profile $AWS_PROFILE"
    fi
    if [ -n "$AWS_REGION" ]; then
        aws_args="$aws_args --region $AWS_REGION"
    fi
    
    aws cloudformation describe-stacks \
        --stack-name "$stack_name" \
        $aws_args \
        --query "Stacks[0].Outputs[?OutputKey=='$output_key'].OutputValue" \
        --output text 2>/dev/null
}

# Function to display usage
usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Deployment script for Prebid Server on AWS. Handles two-step deployment:
1. BidderSimulatorStack (optional) — deploys the bidder simulator
2. PrebidServerStack — deploys Prebid Server with CF parameters from step 1

OPTIONS:
    --deploy-bidding-simulator    Deploy the bidding simulator stack (default: false)
    --simulator-connectivity MODE Connectivity model: 'rtb-fabric' (default) or 'vpc-peering'
    --enable-log-analytics        Enable log analytics (default: false)
    --enable-rtb-requester-gateway  Provision RTB Fabric Requester Gateway for partner onboarding
    --container-image PATH_OR_URI Container image: tar.gz file path (load/push to ECR) or ECR URI
    --profile PROFILE             AWS profile to use
    --region REGION               AWS region to deploy to
    --synth                       Run 'cdk synth' instead of 'cdk deploy'
    --skip-copy                   Skip AMT bidder file copying (for testing)
    -h, --help                    Display this help message

EXAMPLES:
    # Deploy Prebid Server only (no simulator)
    $0 --profile rtb --region us-east-1

    # Deploy with bidding simulator (RTB Fabric connectivity - default)
    $0 --deploy-bidding-simulator --profile rtb --region us-east-1

    # Deploy with bidding simulator (VPC peering fallback for non-RTB regions)
    $0 --deploy-bidding-simulator --simulator-connectivity vpc-peering --profile rtb --region us-east-1

    # Deploy with RTB Fabric gateway for future partner onboarding (no simulator)
    $0 --enable-rtb-requester-gateway --profile rtb --region us-east-1

    # Deploy with a pre-built container image (tar.gz)
    $0 --container-image deployment/container/prebid-server-v1.0.0.tar.gz --profile rtb --region us-east-1

    # Deploy with an existing ECR image URI
    $0 --container-image 123456789012.dkr.ecr.us-east-1.amazonaws.com/prebid-server:latest --profile rtb --region us-east-1

    # Deploy with analytics enabled
    $0 --enable-log-analytics --profile rtb --region us-east-1

    # Synthesize CloudFormation templates
    $0 --synth --profile rtb --region us-east-1

EOF
    exit 1
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --deploy-bidding-simulator)
            DEPLOY_BIDDING_SIMULATOR="true"
            shift
            ;;
        --simulator-connectivity)
            SIMULATOR_CONNECTIVITY="$2"
            if [[ "$SIMULATOR_CONNECTIVITY" != "rtb-fabric" && "$SIMULATOR_CONNECTIVITY" != "vpc-peering" ]]; then
                print_error "Invalid --simulator-connectivity value: $SIMULATOR_CONNECTIVITY"
                print_error "Must be 'rtb-fabric' or 'vpc-peering'"
                exit 1
            fi
            shift 2
            ;;
        --enable-log-analytics)
            ENABLE_LOG_ANALYTICS="true"
            shift
            ;;
        --enable-rtb-requester-gateway)
            ENABLE_RTB_REQUESTER_GATEWAY="true"
            shift
            ;;
        --container-image)
            CONTAINER_IMAGE="$2"
            shift 2
            ;;
        --profile)
            AWS_PROFILE="$2"
            shift 2
            ;;
        --region)
            AWS_REGION="$2"
            shift 2
            ;;
        --synth)
            CDK_COMMAND="synth"
            shift
            ;;
        --skip-copy)
            SKIP_COPY="true"
            shift
            ;;
        -h|--help)
            usage
            ;;
        *)
            print_error "Unknown option: $1"
            usage
            ;;
    esac
done

# Get script directory and project root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$SCRIPT_DIR"

print_info "Project root: $PROJECT_ROOT"
print_info "Deploy bidding simulator: $DEPLOY_BIDDING_SIMULATOR"
print_info "Simulator connectivity: $SIMULATOR_CONNECTIVITY"
print_info "Enable log analytics: $ENABLE_LOG_ANALYTICS"
print_info "Enable RTB Requester Gateway: $ENABLE_RTB_REQUESTER_GATEWAY"
if [ -n "$CONTAINER_IMAGE" ]; then
    print_info "Container image: $CONTAINER_IMAGE"
fi

# Check if Docker or Finch daemon is running (required for CDK Docker builds)
print_info "Checking container runtime status..."

# Check if CDK_DOCKER is explicitly set to finch
if [ "$CDK_DOCKER" = "finch" ]; then
    if ! finch info > /dev/null 2>&1; then
        print_error "Finch is not running!"
        print_error "CDK deployment requires Finch for building container images."
        print_error "Please start Finch with 'finch vm start' and try again."
        exit 1
    fi
    print_info "Finch is running"
    authenticate_ecr_public "finch"
    authenticate_ecr_private "finch"
# Check if finch is available (preferred over docker)
elif command -v finch > /dev/null 2>&1; then
    if ! finch info > /dev/null 2>&1; then
        print_warn "Finch is installed but not running, checking for Docker..."
    else
        print_info "Finch is running (setting CDK_DOCKER=finch)"
        export CDK_DOCKER=finch
        authenticate_ecr_public "finch"
        authenticate_ecr_private "finch"
    fi
fi

# If Finch is not available or not running, check for Docker
if [ "$CDK_DOCKER" != "finch" ]; then
    if command -v docker > /dev/null 2>&1; then
        if ! docker info > /dev/null 2>&1; then
            print_error "Docker daemon is not running!"
            print_error "CDK deployment requires Docker for building container images."
            print_error "Please start Docker and try again."
            print_error ""
            print_info "Alternatively, you can use Finch by setting: export CDK_DOCKER=finch"
            exit 1
        fi
        print_info "Docker daemon is running"
        authenticate_ecr_public "docker"
        authenticate_ecr_private "docker"
    else
        print_error "No container runtime found!"
        print_error "Please install Docker Desktop or Finch:"
        print_error "  - Finch: https://github.com/runfinch/finch (recommended)"
        print_error "  - Docker Desktop: https://docs.docker.com/engine/"
        exit 1
    fi
fi

# Step 1: Handle --container-image flag
if [ -n "$CONTAINER_IMAGE" ]; then
    if [[ "$CONTAINER_IMAGE" == *.tar.gz ]] && [ -f "$CONTAINER_IMAGE" ]; then
        # tar.gz path: docker load, create ECR repo, tag, push
        print_info "Loading container image from tar.gz: $CONTAINER_IMAGE"
        
        CONTAINER_RUNTIME="${CDK_DOCKER:-docker}"
        
        # Load the image and capture the image name
        LOAD_OUTPUT=$($CONTAINER_RUNTIME load -i "$CONTAINER_IMAGE" 2>&1)
        LOADED_IMAGE=$(echo "$LOAD_OUTPUT" | sed -n 's/.*Loaded image: //p')
        
        if [ -z "$LOADED_IMAGE" ]; then
            # Try alternate format: "Loaded image ID: sha256:..."
            LOADED_IMAGE=$(echo "$LOAD_OUTPUT" | sed -n 's/.*Loaded image ID: //p')
        fi
        
        if [ -z "$LOADED_IMAGE" ]; then
            print_error "Failed to load container image from $CONTAINER_IMAGE"
            print_error "Output: $LOAD_OUTPUT"
            exit 1
        fi
        print_info "Loaded image: $LOADED_IMAGE"
        
        # Get AWS account ID and region for ECR
        AWS_ARGS=""
        if [ -n "$AWS_PROFILE" ]; then
            AWS_ARGS="$AWS_ARGS --profile $AWS_PROFILE"
        fi
        if [ -n "$AWS_REGION" ]; then
            AWS_ARGS="$AWS_ARGS --region $AWS_REGION"
        fi
        
        ECR_REGION="${AWS_REGION:-us-east-1}"
        ECR_ACCOUNT_ID=$(aws sts get-caller-identity $AWS_ARGS --query Account --output text 2>/dev/null)
        
        if [ -z "$ECR_ACCOUNT_ID" ]; then
            print_error "Failed to get AWS account ID for ECR push"
            exit 1
        fi
        
        ECR_REPO_NAME="prebid-server-on-aws"
        ECR_REGISTRY="${ECR_ACCOUNT_ID}.dkr.ecr.${ECR_REGION}.amazonaws.com"
        ECR_IMAGE_URI="${ECR_REGISTRY}/${ECR_REPO_NAME}:latest"
        
        # Create ECR repository if it doesn't exist
        print_info "Ensuring ECR repository exists: $ECR_REPO_NAME"
        aws ecr describe-repositories --repository-names "$ECR_REPO_NAME" $AWS_ARGS > /dev/null 2>&1 || \
            aws ecr create-repository --repository-name "$ECR_REPO_NAME" --image-scanning-configuration scanOnPush=true $AWS_ARGS > /dev/null 2>&1
        
        # Tag and push
        print_info "Tagging image as: $ECR_IMAGE_URI"
        $CONTAINER_RUNTIME tag "$LOADED_IMAGE" "$ECR_IMAGE_URI"
        
        print_info "Pushing image to ECR..."
        set +e
        $CONTAINER_RUNTIME push "$ECR_IMAGE_URI"
        PUSH_EXIT=$?
        set -e
        
        if [ $PUSH_EXIT -ne 0 ]; then
            print_error "Failed to push container image to ECR"
            exit 1
        fi
        
        print_info "Container image pushed successfully: $ECR_IMAGE_URI"
        export OVERRIDE_ECR_REGISTRY="$ECR_IMAGE_URI"
        
    elif [[ "$CONTAINER_IMAGE" == *.tar.gz ]] && [ ! -f "$CONTAINER_IMAGE" ]; then
        # tar.gz path specified but file doesn't exist
        print_error "Container image file not found: $CONTAINER_IMAGE"
        print_error "Please provide a valid path to a tar.gz container image file"
        exit 1
    else
        # ECR URI: pass through directly
        print_info "Using provided ECR image URI: $CONTAINER_IMAGE"
        export OVERRIDE_ECR_REGISTRY="$CONTAINER_IMAGE"
    fi
fi

# Step 2: Copy AMT bidder files if deploying simulator
if [ "$DEPLOY_BIDDING_SIMULATOR" = "true" ] && [ "$SKIP_COPY" = "false" ]; then
    print_info "Copying AMT bidder files for Docker build..."
    
    SOURCE_DIR="$PROJECT_ROOT/source/loadtest/amt-bidder"
    DEST_DIR="$PROJECT_ROOT/deployment/ecr/prebid-server/amt-bidder"
    
    # Verify source directory exists
    if [ ! -d "$SOURCE_DIR" ]; then
        print_error "Source directory not found: $SOURCE_DIR"
        exit 1
    fi
    
    # Remove existing destination if it exists
    if [ -d "$DEST_DIR" ]; then
        print_warn "Removing existing AMT bidder directory at $DEST_DIR"
        rm -rf "$DEST_DIR"
    fi
    
    # Copy the directory
    print_info "Copying from $SOURCE_DIR to $DEST_DIR"
    cp -r "$SOURCE_DIR" "$DEST_DIR"
    
    # Ensure .gitkeep exists even after recreate
    touch "$DEST_DIR/.gitkeep"
    
    # Verify the copy
    if [ ! -d "$DEST_DIR" ]; then
        print_error "Failed to copy AMT bidder files"
        exit 1
    fi
    
    FILE_COUNT=$(find "$DEST_DIR" -type f | wc -l)
    print_info "Successfully copied AMT bidder files ($FILE_COUNT files)"
else
    if [ "$DEPLOY_BIDDING_SIMULATOR" = "false" ]; then
        print_info "Skipping AMT bidder file copy (simulator not being deployed)"
    else
        print_warn "Skipping AMT bidder file copy (--skip-copy flag set)"
    fi
fi

# Step 3: Build demo website if deploying simulator
if [ "$DEPLOY_BIDDING_SIMULATOR" = "true" ]; then
    print_info "Building demo website..."
    
    cd "$PROJECT_ROOT/source/loadtest/demo/"

    npm install
    npm run build
    
    print_info "Demo build complete"
else
    print_info "Skipping demo build (simulator not being deployed)"
fi

# Step 4: Set up Python virtual environment
print_info "Setting up Python virtual environment..."

cd "$PROJECT_ROOT"

if [ ! -d ".venv" ]; then
    print_info "Creating virtual environment..."
    python3 -m venv .venv
fi

print_info "Activating virtual environment..."
source .venv/bin/activate

# Step 5: Install dependencies
print_info "Installing Python dependencies..."
cd "$PROJECT_ROOT/source"

if [ ! -f "requirements-poetry.txt" ]; then
    print_error "requirements-poetry.txt not found in source directory"
    exit 1
fi

pip install -q -r requirements-poetry.txt
poetry install

# Step 6: Navigate to infrastructure directory
cd "$PROJECT_ROOT/source/infrastructure"

# Step 7: Build common CDK args
CDK_COMMON_ARGS=""

if [ -n "$AWS_PROFILE" ]; then
    CDK_COMMON_ARGS="$CDK_COMMON_ARGS --profile $AWS_PROFILE"
fi

if [ -n "$AWS_REGION" ]; then
    CDK_COMMON_ARGS="$CDK_COMMON_ARGS --region $AWS_REGION"
fi

# Step 8: Two-step deployment
if [ "$CDK_COMMAND" = "deploy" ]; then

    # Step 8a: Deploy BidderSimulatorStack first (if requested)
    if [ "$DEPLOY_BIDDING_SIMULATOR" = "true" ]; then
        print_info "=== Step 1/2: Deploying BidderSimulatorStack ==="
        
        BSS_PARAMS=""
        if [ "$SIMULATOR_CONNECTIVITY" = "rtb-fabric" ]; then
            BSS_PARAMS="--parameters BiddingServerSimulator:EnableRtbFabric=true"
        else
            BSS_PARAMS="--parameters BiddingServerSimulator:EnableRtbFabric=false"
        fi
        
        print_info "Running: cdk deploy BiddingServerSimulator --context deployBiddingSimulator=true --require-approval never $BSS_PARAMS $CDK_COMMON_ARGS"
        echo ""
        cdk deploy BiddingServerSimulator \
            --context deployBiddingSimulator=true \
            --require-approval never \
            $BSS_PARAMS \
            $CDK_COMMON_ARGS
        
        print_info "BidderSimulatorStack deployed. Reading outputs..."
        
        # Read BidderSimulatorStack outputs
        BSS_STACK_NAME="BiddingServerSimulator"
        
        # Build PrebidServerStack parameters from BSS outputs
        PSS_PARAMS=""
        
        if [ "$SIMULATOR_CONNECTIVITY" = "rtb-fabric" ]; then
            # RTB Fabric path: enable requester gateway (link managed by simulator_fabric_link.py)
            RESPONDER_GW_ID=$(get_stack_output "$BSS_STACK_NAME" "ResponderGatewayId")
            if [ -z "$RESPONDER_GW_ID" ] || [ "$RESPONDER_GW_ID" = "None" ]; then
                print_error "Failed to get ResponderGatewayId from BidderSimulatorStack outputs"
                print_error "Ensure BidderSimulatorStack was deployed with EnableRtbFabric=true"
                exit 1
            fi
            print_info "ResponderGatewayId: $RESPONDER_GW_ID"
            PSS_PARAMS="$PSS_PARAMS --parameters prebid-server-deployment-on-aws:EnableRtbRequesterGateway=true"
        else
            # VPC Peering path: pass VPC ID, ALB SG ID, route table IDs, endpoint
            SIMULATOR_VPC_ID=$(get_stack_output "$BSS_STACK_NAME" "BidderSimulatorVpcId")
            SIMULATOR_ALB_SG_ID=$(get_stack_output "$BSS_STACK_NAME" "BidderSimulatorAlbSecurityGroupId")
            SIMULATOR_RT_ID_1=$(get_stack_output "$BSS_STACK_NAME" "BidderSimulatorRouteTableId1")
            SIMULATOR_RT_ID_2=$(get_stack_output "$BSS_STACK_NAME" "BidderSimulatorRouteTableId2")
            SIMULATOR_ENDPOINT=$(get_stack_output "$BSS_STACK_NAME" "BidderSimulatorAlbEndpoint")
            
            if [ -z "$SIMULATOR_VPC_ID" ] || [ "$SIMULATOR_VPC_ID" = "None" ]; then
                print_error "Failed to get BidderSimulatorVpcId from BidderSimulatorStack outputs"
                exit 1
            fi
            
            print_info "SimulatorVpcId: $SIMULATOR_VPC_ID"
            print_info "SimulatorAlbSgId: $SIMULATOR_ALB_SG_ID"
            print_info "SimulatorRouteTableId1: $SIMULATOR_RT_ID_1"
            print_info "SimulatorRouteTableId2: $SIMULATOR_RT_ID_2"
            print_info "SimulatorEndpoint: $SIMULATOR_ENDPOINT"
            
            PSS_PARAMS="$PSS_PARAMS --parameters prebid-server-deployment-on-aws:SimulatorVpcId=$SIMULATOR_VPC_ID"
            PSS_PARAMS="$PSS_PARAMS --parameters prebid-server-deployment-on-aws:SimulatorAlbSgId=$SIMULATOR_ALB_SG_ID"
            PSS_PARAMS="$PSS_PARAMS --parameters prebid-server-deployment-on-aws:SimulatorRouteTableId1=$SIMULATOR_RT_ID_1"
            PSS_PARAMS="$PSS_PARAMS --parameters prebid-server-deployment-on-aws:SimulatorRouteTableId2=$SIMULATOR_RT_ID_2"
            PSS_PARAMS="$PSS_PARAMS --parameters prebid-server-deployment-on-aws:SimulatorEndpoint=$SIMULATOR_ENDPOINT"
        fi
        
        print_info "=== Step 2/2: Deploying PrebidServerStack ==="
    else
        PSS_PARAMS=""
        print_info "=== Deploying PrebidServerStack ==="
    fi
    
    # Add EnableRtbRequesterGateway if explicitly requested
    if [ "$ENABLE_RTB_REQUESTER_GATEWAY" = "true" ]; then
        PSS_PARAMS="$PSS_PARAMS --parameters prebid-server-deployment-on-aws:EnableRtbRequesterGateway=true"
    fi
    
    # Add EnableLogAnalytics as CF parameter
    if [ "$ENABLE_LOG_ANALYTICS" = "true" ]; then
        PSS_PARAMS="$PSS_PARAMS --parameters prebid-server-deployment-on-aws:EnableLogAnalytics=true"
    fi
    
    # Deploy PrebidServerStack
    print_info "Running: cdk deploy prebid-server-deployment-on-aws --context deployBiddingSimulator=$DEPLOY_BIDDING_SIMULATOR --require-approval never $PSS_PARAMS $CDK_COMMON_ARGS"
    echo ""
    cdk deploy prebid-server-deployment-on-aws \
        --context deployBiddingSimulator=$DEPLOY_BIDDING_SIMULATOR \
        --require-approval never \
        $PSS_PARAMS \
        $CDK_COMMON_ARGS

    # Step: Create Fabric Link (after both stacks deployed, RTB Fabric path only)
    if [ "$DEPLOY_BIDDING_SIMULATOR" = "true" ] && [ "$SIMULATOR_CONNECTIVITY" = "rtb-fabric" ]; then
        print_info "Installing fabric-link script dependencies..."
        pip install -q -r "$PROJECT_ROOT/deployment/requirements-fabric-link.txt" 2>&1 | grep -v "already satisfied" || true

        print_info "Creating Fabric Link..."
        set +e
        LINK_URL=$(python3 "$PROJECT_ROOT/deployment/simulator_fabric_link.py" create \
            --stack-name "prebid-server-deployment-on-aws" \
            --responder-gateway-id "$RESPONDER_GW_ID" \
            ${AWS_PROFILE:+--profile "$AWS_PROFILE"} \
            ${AWS_REGION:+--region "$AWS_REGION"})
        LINK_EXIT=$?
        set -e

        if [ $LINK_EXIT -ne 0 ]; then
            print_error "Fabric Link creation failed"
            exit 1
        fi
        print_info "Fabric Link URL: $LINK_URL"
    fi

else
    # Synth mode — synthesize all stacks
    print_info "Running: cdk synth --all --context deployBiddingSimulator=$DEPLOY_BIDDING_SIMULATOR $CDK_COMMON_ARGS"
    echo ""
    cdk synth --all --context deployBiddingSimulator=$DEPLOY_BIDDING_SIMULATOR $CDK_COMMON_ARGS
fi

# Step 9: Cleanup message
echo ""
if [ "$CDK_COMMAND" = "deploy" ]; then
    print_info "Deployment complete!"
    
    if [ "$DEPLOY_BIDDING_SIMULATOR" = "true" ]; then
        print_info "Bidding simulator stack has been deployed"
        if [ "$SIMULATOR_CONNECTIVITY" = "rtb-fabric" ]; then
            print_info "RTB Fabric connectivity configured"
            print_info "Fabric Link created and accepted via simulator_fabric_link.py"
        else
            print_info "VPC peering connectivity configured"
        fi
    fi
    
    if [ "$ENABLE_LOG_ANALYTICS" = "true" ]; then
        print_info "Log analytics has been enabled"
    fi
    
    if [ "$ENABLE_RTB_REQUESTER_GATEWAY" = "true" ]; then
        print_info "RTB Fabric Requester Gateway has been provisioned"
        print_info "Create Fabric Links manually for partner onboarding"
    fi
else
    print_info "Synthesis complete!"
fi
print_info "Follow the readme for post deployment validation steps"
