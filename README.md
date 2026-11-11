# Guidance for Deploying a Prebid Server on AWS

## Table of Contents
1. [Overview](#overview)
2. [Cost](#cost)
3. [Prerequisites](#prerequisites)
4. [Deployment Steps](#deployment-steps)
5. [Deployment Scenarios](#deployment-scenarios)
6. [CloudFormation Parameters](#cloudformation-parameters)
7. [Deployment Validation](#deployment-validation)
8. [Running the Guidance](#running-the-guidance)
9. [Next Steps](#next-steps)
10. [Cleanup](#cleanup)
11. [FAQ, Known Issues, Additional Considerations, and Limitations](#faq-known-issues-additional-considerations-and-limitations)
12. [Revisions](#revisions)
13. [Notices](#notices)
14. [Authors](#authors)

## Overview

Guidance for Deploying a Prebid Server on AWS helps customers deploy and operate Prebid Server, an open source solution for real-time ad monetization, in their own AWS environment. The solution enables customers with ad-supported websites to achieve scaled access to advertising revenue through a community of more than 180+ advertising platforms. Customers achieve full control over decision logic and access to transaction data, and realize AWS benefits like global scalability and pay-as-you-go economics.

This solution deploys v3.43.0 of [Prebid Server Java](https://github.com/prebid/prebid-server-java.git) with infrastructure in a single region of the AWS Cloud to handle a wide range of request traffic, and recording of auction and bid transaction data.

### Key Features

- **Prebid Server purpose built for AWS infrastructure**: Deploy Prebid Server in a scalable and cost-efficient manner with production-grade availability, scalability, and low-latency for a variety of request loads (documented up to 100,000 RPS).

- **Built-in observability**: Operational resource metrics, alarms, runtime logs, and business metrics, visualized with the Cost and Usage Dashboard powered by Amazon QuickSight and Service Catalog AppRegistry.

- **Decrease time to market**: Deployment template to establish the necessary infrastructure to get customers running within days instead of months or weeks.

- **Ownership of all operational and business data**: All data from Prebid Server metrics extract, transform, and load (ETL) to AWS Glue Data Catalog for seamless integration with various clients, such as Amazon Athena, Amazon Redshift, and Amazon SageMaker AI.

- **AWS RTB Fabric integration**: Optionally route bid requests through [AWS RTB Fabric](https://aws.amazon.com/rtb-fabric/), a private network purpose-built for real-time bidding. RTB Fabric provides low-latency, cost-optimized connectivity between Prebid Server and bidder endpoints without traversing the public internet. Note: RTB Fabric integration currently covers **outbound** bid requests (Prebid Server → bidders). Using RTB Fabric managed endpoints for **inbound** traffic (replacing ALB/CloudFront) is not yet supported because managed endpoints require EC2 Auto Scaling groups or EKS, and this solution runs on ECS Fargate.

- **Quick start with bidder simulator**: Deploy an optional bidder simulator stack to quickly test and validate your Prebid Server deployment without needing to configure external bidders.

- **Demo page**: Demo page can be used to validate the end-to-end flow from prebid.js through Prebid Server to the bidder simulator (see [README](source/loadtest/demo/README.md)).

**Note**: This solution consists of two CDK stacks:
1. **Main Prebid Server Stack**: The core infrastructure for running Prebid Server (always deployed)
2. **Bidder Simulator Stack**: An optional stack for quick start testing and validation that can be deployed using the `--deploy-bidding-simulator` flag

### Architecture

The solution uses AWS CDK and AWS Solutions Constructs to create well-architected applications. All AWS Solutions Constructs are reviewed by AWS and use best practices established by the AWS Well-Architected Framework. Review the [solutions guidance landing page](https://aws.amazon.com/solutions/guidance/deploying-a-prebid-server-on-aws/) for detailed architecture diagrams.

### Overall Solution Architecture
![Guidance for Deploying a Prebid Server on AWS](docs/prebid-server-deployment-on-aws.png)

### Log Analytics Component Architecture
![Guidance for Deploying a Prebid Server on AWS - Log analytics](docs/prebid-server-deployment-on-aws-log-analytics.png)



## Cost

You are responsible for the cost of the AWS services used while running this Guidance. As of July 2023, the cost for running this Guidance with the default settings in the US East (N. Virginia) Region is approximately $241.50 per month for processing with no incoming bidding traffic to the solution.

We recommend creating a [Budget](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-managing-costs.html) through [AWS Cost Explorer](https://aws.amazon.com/aws-cost-management/aws-cost-explorer/) to help manage costs. Prices are subject to change. For full details, refer to the pricing webpage for each AWS service used in this Guidance.

### Sample Cost Table

The following table provides a sample cost breakdown for deploying this Guidance with the default parameters in the US East (N. Virginia) Region for one month with no incoming bidding traffic:

| AWS service  | Dimensions | Cost [USD] |
| ----------- | ------------ | ------------ |
| Amazon ECS | Operating system (Linux), CPU architecture (x86), Average duration (30 days), Number of tasks or pods (2 per month), Amount of memory allocated (4 GB), Amount of ephemeral storage allocated for Amazon ECS (20 GB) | $54.50 |
| AWS WAF | Number of Web Access Control Lists (Web ACLs) utilized (1 per month), Number of Managed Rule Groups per Web ACL (6 per month) | $15.00 |
| Elastic Load Balancing | Number of Application Load Balancers (1) | $17.00 |
| Amazon EC2 - other | Number of NAT gateways (2) DT inbound: Not selected (0 TB per month), DT outbound: Internet (<50 GB per month), DT Intra-Region: (0 TB per month) | $69.00 |
| Amazon EFS | Desired storage capacity (1 TB per month), Infrequent access requests (<2 GB per month) | $25.00 |
| Amazon S3 | S3 Standard storage | $4.00 |
| Amazon CloudWatch | Number of Standard Resolution Alarm Metrics (20), Standard logs: Data ingested (<20 GB) | $10.00 |
| Other services | Amazon CloudFront, AWS CloudTrail AWS DataSync, IAM, AWS Glue, AWS KMS, AWS Lambda, and Amazon VPC | $47.00 |
| **Total** | | **$241.50** |

**Optional: AWS RTB Fabric cost (when deployed with `--simulator-connectivity rtb-fabric`)**

| AWS service  | Dimensions | Cost [USD] |
| ----------- | ------------ | ------------ |
| AWS RTB Fabric | Requester Gateway, Responder Gateway, Fabric Link — no per-transaction charges with zero traffic. | $0.00 |
| AWS RTB Fabric (with 50GB traffic) | Assuming ~10 KB avg bid request, 3 AWS RTB Fabric linked internal bidders per auction, 50 GB outbound traffic (responses are DT-IN and free), internal transaction pricing ($3/billion), data transfer pricing ($0.02/GB) | $16.00 |

For current RTB Fabric pricing details, see the [AWS RTB Fabric pricing page](https://aws.amazon.com/rtb-fabric/pricing/). With incoming traffic, costs scale based on the volume and size of RTB requests sent through the Fabric Link. Note that bid responses returning to Prebid Server are data transfer IN and incur no charges.

**Cost comparison: RTB Fabric vs NAT Gateway (50GB monthly outbound traffic)**

Assuming 3 bidders per auction with ~10 KB average bid request size per bidder:
- Total data per auction: 10 KB × 3 internal bidders = 30 KB outbound
- Number of auctions: 50 GB / 30 KB ≈ 1.67 million auctions
- Total bid requests: 1.67M auctions × 3 bidders = 5 million requests (0.005 billion)
- RTB Fabric transaction cost: 0.005 billion × $3.00 = $15.00
- RTB Fabric data transfer cost: 50 GB × $0.02 = $1.00
- **Total RTB Fabric cost: $16.00**
- **NAT Gateway cost (baseline): $69.00**
- **Monthly savings: $53.00 (77% reduction)**

## Prerequisites

### Operating System

These deployment instructions are optimized to best work on **macOS, Linux, or Windows**. The following packages and tools are required:

* [AWS Command Line Interface](https://aws.amazon.com/cli/)
* [Python](https://www.python.org/) 3.11 or newer
* [Pypi/Pip](https://pypi.org/project/pip/) 25.0 or newer
* [Poetry](https://python-poetry.org/docs/#installing-with-pipx) 2.0 or newer
* [Node.js](https://nodejs.org/en/) 16.x or newer 
* [AWS CDK](https://aws.amazon.com/cdk/) 2.236.0 or newer 
* [Amazon Corretto OpenJDK](https://docs.aws.amazon.com/corretto/) 21
* [Apache Maven](https://maven.apache.org/) 3.9.9
* [Docker](https://docs.docker.com/engine/). Please ensure docker daemon is running before running cdk deployment.
  * **Alternative**: You can use [Finch](https://github.com/runfinch/finch) as a Docker Desktop alternative. Set `export CDK_DOCKER=finch` in your environment to use Finch with CDK.
* [AWS access key ID and secret access key](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_access-keys.html) configured in your environment with AdministratorAccess equivalent permissions

> **Note:** If you plan to use the pre-built container image (quick-start path), only AWS CLI and Docker/Finch are required. Python, Node.js, CDK, Java, and Maven are only needed when building from source. Download the pre-built container tar.gz from the [GitHub Release](https://github.com/aws-solutions-library-samples/prebid-server-deployment-on-aws/releases) assets.

### AWS account requirements

You need an AWS account with AdministratorAccess equivalent permissions to deploy this solution.

### aws cdk bootstrap

This Guidance uses aws-cdk. If you are using aws-cdk for the first time, please perform the bootstrapping:

```bash
cdk bootstrap --cloudformation-execution-policies arn:aws:iam::aws:policy/AdministratorAccess
```

### RTB Fabric requirements

- AWS RTB Fabric must be available in your deployment region

## Deployment Steps

### 1. Quick Deploy with deploy.sh

For a streamlined deployment experience on Linux/macOS, use the provided `deploy.sh` script:

1. Clone the repo:
   ```bash
   git clone https://github.com/aws-solutions-library-samples/prebid-server-deployment-on-aws.git
   ```

2. Change to the repo folder:
   ```bash
   cd deploying-prebid-server-on-aws
   ```

3. Run the deployment script:
   ```bash
   # Deploy Prebid Server only (no simulator)
   ./deploy.sh --profile <your-aws-cli-profile> --region <your-region>

   # Deploy with analytics
   ./deploy.sh --enable-log-analytics --profile <your-aws-cli-profile> --region <your-region>

   # Deploy with bidder simulator (RTB Fabric connectivity — default)
   ./deploy.sh --deploy-bidding-simulator --profile <your-aws-cli-profile> --region <your-region>

   # Deploy with bidder simulator (VPC peering fallback)
   ./deploy.sh --deploy-bidding-simulator --simulator-connectivity vpc-peering --profile <your-aws-cli-profile> --region <your-region>

   # Deploy with RTB Requester Gateway only (for partner onboarding)
   ./deploy.sh --enable-rtb-requester-gateway --profile <your-aws-cli-profile> --region <your-region>

   # Deploy with a pre-built container image (tar.gz)
   ./deploy.sh --container-image deployment/container/prebid-server.tar.gz --profile <your-aws-cli-profile> --region <your-region>

   # Deploy with an existing ECR image URI
   ./deploy.sh --container-image 123456789012.dkr.ecr.us-east-1.amazonaws.com/prebid-server:latest --profile <your-aws-cli-profile> --region <your-region>

   # Deploy with all features enabled
   ./deploy.sh --deploy-bidding-simulator --enable-log-analytics --profile <your-aws-cli-profile> --region <your-region>
   ```

   The `deploy.sh` script automatically:
   - Copies AMT bidder files to the Docker build context when `--deploy-bidding-simulator` is used
   - Sets up the Python virtual environment and installs dependencies
   - Authenticates with ECR (public and private registries)
   - Deploys BidderSimulatorStack first (if requested), then PrebidServerStack with CF parameter overrides from simulator outputs
   - Handles container image loading/pushing when `--container-image` is a tar.gz path

   For all options, run:
   ```bash
   ./deploy.sh --help
   ```
   > **Note:** The script is for quick start with minimal options. For all CDK stack options, use the manual deployment and refer to the [documentation](https://docs.aws.amazon.com/solutions/latest/prebid-server-deployment-on-aws/stack-parameters.html) for all CDK parameters.

### 2. Customization, Build and Deploy

For customization or manual deployment, follow these steps:

1. Clone the repo:
   ```bash
   git clone https://github.com/aws-solutions-library-samples/prebid-server-deployment-on-aws.git
   ```

2. Change to the repo folder:
   ```bash
   cd deploying-prebid-server-on-aws
   ```

3. Create a Python virtual environment for development:
   ```bash
   python3 -m venv .venv 
   source ./.venv/bin/activate 
   cd ./source 
   pip install -r requirements-poetry.txt
   poetry install
   ```

4. After introducing changes, run the unit tests to make sure the customizations don't break existing functionality:
   ```bash
   cd ../deployment
   sh ./run-unit-tests.sh --in-venv 1
   ```

5. Build and deploy the solution:

   **Prebid Server Container Image**
   
   By default, the Prebid Server container image will be built locally using Docker ([README](deployment/ecr/README.md)). To use a pre-built or custom container image, use the `--container-image` flag with `deploy.sh` or set the `ContainerImage` CloudFormation parameter directly.

   **Manual Deployment with AWS CDK**
   
   If deploying with the bidder simulator, first copy the AMT bidder files:

   ```bash
   # Copy AMT bidder files (only needed when deploying with simulator)
   cp -r source/loadtest/amt-bidder deployment/ecr/prebid-server/
   ```

   Then deploy using CDK (two-step process):

   ```bash
   cd source/infrastructure

   # bootstrap CDK (required once - deploys a CDK bootstrap CloudFormation stack for assets)  
   cdk bootstrap --cloudformation-execution-policies arn:aws:iam::aws:policy/AdministratorAccess

   # Step 1: Deploy BidderSimulatorStack (if using simulator)
   cdk deploy BiddingServerSimulator \
     --context deployBiddingSimulator=true \
     --parameters BiddingServerSimulator:EnableRtbFabric=true \
     --profile <your-aws-cli-profile> --region <your-region>

   # Step 2: Deploy PrebidServerStack with RTB Requester Gateway enabled
   cdk deploy prebid-server-deployment-on-aws \
     --context deployBiddingSimulator=true \
     --parameters prebid-server-deployment-on-aws:EnableRtbRequesterGateway=true \
     --profile <your-aws-cli-profile> --region <your-region>

   # Step 3: Create the Fabric Link (post-deployment, matches what deploy.sh does automatically)
   python3 deployment/simulator_fabric_link.py create \
     --stack-name prebid-server-deployment-on-aws \
     --responder-gateway-id <responder-gw-id-from-step-1-outputs> \
     --profile <your-aws-cli-profile> --region <your-region>

   # Or deploy without bidder simulator (no file copy needed, single step)
   cdk deploy prebid-server-deployment-on-aws \
     --profile <your-aws-cli-profile> --region <your-region>
   ```

   > **Note:** When deploying with the simulator, the two-step process is required because PrebidServerStack needs outputs from BidderSimulatorStack as CloudFormation parameter overrides. The `deploy.sh` script handles this automatically.

   **Advanced Configuration**
   
   For advanced customization or troubleshooting, refer to the [loadtest component readme](./source/loadtest/README.md) which contains detailed information about bidder simulator configuration and manual CDK deployment instructions.

## Deployment Scenarios

The solution supports the following deployment paths:

| Scenario | deploy.sh flags | Description |
|----------|----------------|-------------|
| PBS only (no simulator) | `--profile <p> --region <r>` | Core Prebid Server infrastructure. Connects to external bidders via NAT gateways. |
| PBS + simulator (RTB Fabric) | `--deploy-bidding-simulator` | Default simulator connectivity. After stack deployment, `deployment/simulator_fabric_link.py` creates the Fabric Link and updates the ECS task definition directly via the ECS API (no CloudFormation stack update needed). Traffic is routed through AWS RTB Fabric private network. |
| PBS + simulator (VPC peering) | `--deploy-bidding-simulator --simulator-connectivity vpc-peering` | Fallback for regions where RTB Fabric is unavailable. Direct VPC peering between stacks. |
| PBS + RTB Requester Gateway only | `--enable-rtb-requester-gateway` | Provisions a Requester Gateway for partner onboarding without deploying the simulator. Create Fabric Links manually. |
| PBS + analytics | `--enable-log-analytics` | Enables the log analytics pipeline (Glue, Athena, QuickSight). |
| PBS + custom container (tar.gz) | `--container-image deployment/container/prebid-server.tar.gz` | Loads the pre-built container image (from release zip), pushes to ECR, deploys with that image. |
| PBS + custom container (ECR URI) | `--container-image <ecr-uri>` | Deploys with an existing ECR image URI (skips local Docker build). |

Flags can be combined. For example, deploy with simulator + analytics:
```bash
./deploy.sh --deploy-bidding-simulator --enable-log-analytics --profile <p> --region <r>
```

## CloudFormation Parameters

### PrebidServerStack Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `EnableLogAnalytics` | String (true/false) | `false` | Enable the log analytics pipeline (Glue ETL, Athena, QuickSight). |
| `EnableRtbRequesterGateway` | String (true/false) | `false` | Provision an RTB Fabric Requester Gateway in the Prebid Server VPC. Required for RTB Fabric connectivity. |
| `ContainerImage` | String | `` (empty) | ECR image URI for Prebid Server. When empty, the container is built from source during CDK deployment. |
| `SimulatorVpcId` | String | `` (empty) | Bidder Simulator VPC ID. Used for VPC peering connectivity. |
| `SimulatorAlbSgId` | String | `` (empty) | Bidder Simulator ALB Security Group ID. Used to authorize ingress from Prebid Server VPC via peering. |
| `SimulatorRouteTableId1` | String | `` (empty) | First route table ID in the Bidder Simulator VPC (for peering routes). |
| `SimulatorRouteTableId2` | String | `` (empty) | Second route table ID in the Bidder Simulator VPC (for peering routes). |
| `SimulatorEndpoint` | String | `` (empty) | Bidder Simulator ALB endpoint URL. Used as the bid endpoint when VPC peering is active. |

### BidderSimulatorStack Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `EnableRtbFabric` | String (true/false) | `true` | Deploy an RTB Fabric Responder Gateway in the simulator VPC. Set to `false` for VPC peering mode. |

## Deployment Validation

After deploying the solution:

1. Open the CloudFormation console and verify the status of the template with the name starting with your solution name.
2. If deployment is successful, you should see an active ECS cluster with the Prebid Server tasks running.
3. Verify that the Application Load Balancer is in service.
4. If bidder simulator is deployed, follow the instructions [here](./source/loadtest/README.md) to load test the deployment.
5. Test prebid.js integration following the instructions demo website readme [here](source/loadtest/demo/README.md).

## Running the Guidance

### Container Image Deployment

The solution supports three paths for deploying the Prebid Server container image:

#### Quick start: Pre-built container image (recommended)

A pre-built container image (`prebid-server.tar.gz`) is available as a downloadable asset on the [GitHub Release page](https://github.com/aws-solutions-library-samples/prebid-server-deployment-on-aws/releases). This is the fastest path to deployment — no local Docker build, no Maven/Java toolchain required.

**Deploy:**

1. Download `prebid-server-deployment-on-aws.zip` from the [latest release](https://github.com/aws-solutions-library-samples/prebid-server-deployment-on-aws/releases)
2. Extract and deploy:

```bash
unzip prebid-server-deployment-on-aws.zip -d prebid-server
cd prebid-server
./deploy.sh --container-image deployment/container/prebid-server.tar.gz --profile <p> --region <r>
```

The `deploy.sh` script handles everything automatically:
1. Loads the tar.gz into your local container runtime (Docker/Finch)
2. Creates an ECR repository (`prebid-server-on-aws`) if it doesn't exist
3. Tags and pushes the image to your ECR
4. Deploys the stack with `ContainerImage` pointing to the pushed URI

> **Note:** The release zip includes the pre-built container image. If you cloned the source repository directly, the tar.gz is not included — build from source instead or download the release zip.

#### Build from source

Without `--container-image`, the CDK deployment builds the container image locally from `deployment/ecr/prebid-server/` and pushes it to a CDK-managed ECR repository. This requires Docker, Java 21, and Maven installed locally:

```bash
./deploy.sh --profile <p> --region <r>
```

#### Use an existing ECR URI

If you already have a Prebid Server image in ECR:

```bash
./deploy.sh --container-image 123456789012.dkr.ecr.us-east-1.amazonaws.com/prebid-server:v1.0.0 --profile <p> --region <r>
```

### Prebid Server Java Container Customization

You may choose to customize the container configuration, or create your own container to use with this solution. The infrastructure for this solution has only been tested on Prebid Server Java.

#### Deploy with Customized Prebid Server Configurations
* After deploying the CloudFormation template stack, find the S3 bucket in the CloudFormation stack outputs named `ContainerImagePrebidSolutionConfigBucket`.
1. Review the `/prebid-server/default/README.md` and `/prebid-server/current/README.md` files in the bucket.
2. Upload your changes to the `/prebid-server/current/` prefix in that bucket.
3. To update the ECS service manually, navigate to the Amazon ECS cluster associated with the deployed CloudFormation stack using the AWS Management Console. Then, update the ECS service by selecting the 'Force New Deployment' option with the new task definition version.

### Runtime and Metric Logging for ETL

The Prebid Server container shipped with this solution is configured for two types of logging:

1. Runtime logs from the Prebid Server are sent to CloudWatch logs under the `PrebidContainerLogGroup` log group.
2. Metrics output logs are written to `/mnt/efs/metrics/CONTAINER_ID/prebid-metrics.log` with a default interval of 30 seconds.
3. Rotated logs are stored at `/mnt/efs/metrics/CONTAINER_ID/archived/prebid-metrics.TIMESTAMP.log.gz` and are migrated from EFS to S3 by AWS DataSync.

### Analytics Reporter Configuration

The solution includes a custom analytics adapter for Prebid Server. By default, the analytics integration is disabled in the [prebid-config.yaml](deployment/ecr/prebid-server/default-config/prebid-config.yaml)

```yaml
analytics:
  global:
    adapters: "psdoaAnalytics"  # Specifies the custom analytics adapter
  psdoa:
    enabled: ${LOG_ANALYTICS_ENABLED}  # Enables or Disables psdoa analytics integration
```

To enable psdoaAnalytics, deploy with `--enable-log-analytics` or set the `EnableLogAnalytics` CloudFormation parameter to `true`.

### RTB Fabric Integration

[AWS RTB Fabric](https://aws.amazon.com/rtb-fabric/) is a private network purpose-built for real-time bidding that provides low-latency, cost-optimized connectivity between ad tech participants without traversing the public internet.

#### How It Works

When RTB Fabric connectivity is enabled (`--simulator-connectivity rtb-fabric`, the default), the solution creates the following architecture:

```
Prebid Server VPC                          Bidder Simulator VPC
┌──────────────────────┐                    ┌─────────────────────┐
│  ECS Fargate Tasks   │                    │  ALB + Lambda       │
│  (Prebid Server)     │                    │  (Bidder Simulator) │
│         │            │                    │         ▲           │
│         ▼            │                    │         │           │
│  Requester Gateway ──┼── Fabric Link ─────┼── Responder Gateway │
│  (HTTPS, port 443)   │  (RTB Fabric)      │  (HTTP, port 80)    │
└──────────────────────┘                    └─────────────────────┘
```

- **Requester Gateway**: Deployed in the Prebid Server VPC via CloudFormation (enabled via `EnableRtbRequesterGateway=true`). Sends bid requests over HTTPS (port 443) through RTB Fabric.
- **Responder Gateway**: Deployed in the Bidder Simulator VPC via CloudFormation (enabled via `EnableRtbFabric=true` on BidderSimulatorStack). Receives bid requests and forwards them to the simulator ALB.
- **Fabric Link**: Connects the two gateways. Managed by the `simulator_fabric_link.py` script (not CloudFormation). The script creates the link, waits for it to become active, accepts it from the responder side (same-account simulator), and updates the ECS task definition with the link URL.
- **WaitForGateway**: A CloudFormation custom resource that polls until the Requester Gateway reaches ACTIVE state before the stack completes.

#### Fabric Link Management (`simulator_fabric_link.py`)

The Fabric Link lifecycle is managed by `deployment/simulator_fabric_link.py`, a Python script using boto3 that operates independently of CloudFormation. This approach provides faster link operations (~30 seconds vs 5-10 minutes for a stack update) and cleaner separation of concerns.

**Dependencies:** Requires `boto3 >= 1.43.0` (for RTB Fabric SDK support). Install via:
```bash
pip install -r deployment/requirements-fabric-link.txt
```
The `deploy.sh` and `destroy.sh` scripts handle this automatically.

When you deploy with `--deploy-bidding-simulator`, the `deploy.sh` script automatically invokes `simulator_fabric_link.py create` after both stacks are deployed. The script:
1. Creates the Fabric Link between the Requester and Responder Gateways
2. Polls with exponential backoff until the link becomes active
3. Accepts the link from the responder side (same-account simulator links are auto-accepted by the script)
4. Registers a new ECS task definition revision with the link URL
5. Triggers a rolling ECS deployment (~30 seconds)

The link ID is persisted in SSM Parameter Store at `/{stack-name}/fabric-link/link-id` so it can be managed across separate script invocations.

**Subcommands:**

```bash
# Create a Fabric Link
python3 deployment/simulator_fabric_link.py create \
  --stack-name prebid-server-deployment-on-aws \
  --responder-gateway-id rgw-xxx \
  --profile myprofile \
  --region us-east-1

# Check status
python3 deployment/simulator_fabric_link.py status \
  --stack-name prebid-server-deployment-on-aws \
  --profile myprofile \
  --region us-east-1

# Delete a Fabric Link
python3 deployment/simulator_fabric_link.py delete \
  --stack-name prebid-server-deployment-on-aws \
  --profile myprofile \
  --region us-east-1
```

| Subcommand | Required Options | Description |
|------------|-----------------|-------------|
| `create` | `--stack-name`, `--responder-gateway-id` | Creates a Fabric Link, waits for ACTIVE, accepts it, updates ECS task with link URL. Idempotent — if a link already exists (SSM has a link ID), prints status and exits. |
| `delete` | `--stack-name` | Deletes the Fabric Link and removes the SSM parameter. Idempotent — if no link exists, exits cleanly. |
| `status` | `--stack-name` | Prints the current link status, URL, and gateway IDs. |

All subcommands accept optional `--profile` and `--region` for AWS CLI configuration.

#### Connectivity Modes

| Mode | deploy.sh flag | BidderSimulatorStack param | Description |
|------|---------------|---------------------------|-------------|
| RTB Fabric | `--simulator-connectivity rtb-fabric` (default) | `EnableRtbFabric=true` | Traffic routed through AWS RTB Fabric private network. Fabric Link managed by `simulator_fabric_link.py`. |
| VPC Peering | `--simulator-connectivity vpc-peering` | `EnableRtbFabric=false` | Direct VPC peering connection. Fallback for regions without RTB Fabric. |
| Gateway only | `--enable-rtb-requester-gateway` (no simulator) | N/A | Provisions Requester Gateway for manual partner Fabric Link creation. |

When neither mode is applicable (no bidder simulator deployed, no gateway requested), Prebid Server connects to external bidders over the public internet through the NAT gateways.

#### VPC Peering Fallback

For regions where RTB Fabric is not available, use VPC peering:

```bash
./deploy.sh --deploy-bidding-simulator --simulator-connectivity vpc-peering --profile <p> --region <r>
```

This creates a VPC peering connection between the Prebid Server VPC and the Bidder Simulator VPC with:
- Peering connection with auto-accept
- Route table entries in both VPCs
- Security group ingress rules on the simulator ALB

#### Gateway-Only Scenario (Partner Onboarding)

To provision an RTB Fabric Requester Gateway without deploying the bidder simulator:

```bash
./deploy.sh --enable-rtb-requester-gateway --profile <p> --region <r>
```

This is useful when you want to establish RTB Fabric connectivity with external partners. After deployment, create Fabric Links manually using the process described below.

#### Partner Onboarding (Manual Steps)

Connecting to real bidder partners via RTB Fabric is a **manual process** — it is not automated by `simulator_fabric_link.py`. The `simulator_fabric_link.py` script is designed exclusively for the same-account simulator scenario where both gateways are in your account and link acceptance can be automated.

For production partner links, follow these steps:

1. **Create a Fabric Link** using the AWS CLI:
   ```bash
   aws rtbfabric create-link \
     --gateway-id <your-requester-gateway-id> \
     --peer-gateway-id <partner-responder-gateway-id>
   ```
   The Requester Gateway ID is available in the PrebidServerStack CloudFormation outputs (`RequesterGatewayId`).

2. **Share the Link ID with the partner** — provide the link ID returned by `create-link` so the partner can accept it from their side.

3. **Partner accepts the link** — the partner accepts the link from their AWS account using the RTB Fabric console or CLI. The link status transitions to ACTIVE once accepted.

4. **Get the Link URL** once the link is ACTIVE:
   ```bash
   aws rtbfabric get-requester-gateway --gateway-id <your-requester-gateway-id>
   # The Link URL format: https://{domain}/link/{link-id}
   ```

5. **Update `prebid-config.yaml` in S3** — add the partner's endpoint URL to the Prebid Server configuration in the S3 config bucket (`ContainerImagePrebidSolutionConfigBucket` from stack outputs). Configure the appropriate bidder adapter to use the RTB Fabric link URL as its endpoint.

6. **Force ECS redeployment** to pick up the new configuration:
   ```bash
   aws ecs update-service \
     --cluster <cluster-name> \
     --service <service-name> \
     --force-new-deployment
   ```
   The cluster and service names are available in the PrebidServerStack CloudFormation outputs.

> **Note:** Unlike the simulator scenario where `simulator_fabric_link.py` handles link creation, acceptance, and ECS task definition updates automatically, partner onboarding requires coordination between two separate AWS accounts. The partner must accept the link from their side before traffic can flow.

## Next Steps

After deploying the solution, consider the following next steps:
1. **Customize Prebid Server Configuration**: Modify the configuration files in the S3 bucket to match your specific requirements.
2. **Analyze Auction Data**: Analyze the auction data generated by psdoaAnalytics adapter using AWS analytics services like Amazon Athena or Amazon Sagemaker.
3. **Set Up Monitoring**: Configure additional CloudWatch alarms or dashboards to monitor the performance of your Prebid Server.
4. **Integrate with Your Applications**: Update your client applications to use the deployed Prebid Server.
5. **Optimize for Cost**: Review the cost tables and adjust the infrastructure based on your actual traffic patterns.

## Cleanup

To delete the deployed solution, use the provided `destroy.sh` script:

```bash
# Destroy with confirmation prompts
./destroy.sh --profile <your-aws-cli-profile> --region <your-region>

# Preview what would be destroyed (no actual deletion)
./destroy.sh --dry-run --profile <your-aws-cli-profile> --region <your-region>
```

The script automatically detects which stacks are deployed (Prebid Server, Bidder Simulator) and destroys them in the correct order. The script invokes `simulator_fabric_link.py delete` before stack destruction to cleanly remove any Fabric Link. If no link exists or deletion fails, the script continues with stack destruction.

For all options, run `./destroy.sh --help`.

Alternatively, you can delete stacks manually:

1. Navigate to the AWS CloudFormation console.
2. Delete the `prebid-server-deployment-on-aws` stack first.
3. Delete the `BiddingServerSimulator` stack (if deployed).
4. Note that some resources like S3 buckets with content may require manual deletion.

## FAQ, Known Issues, Additional Considerations, and Limitations

### Known Issues
 - When deploying RTB fabric components for the first time you may hit an error related to Service Linked IAM role. This could be a timing issue as the first api call is setting up IAM role in the background. Validate in IAM console that the AWS RTB Fabric Service linked role exist and Re-run the deployment again
 - The demo website uses pre-built jar files hosted on 3rd party CDN. As versions of these dependencies roll, these may need to be re-pointed

### Additional considerations

- All S3 buckets created by this solution have public access blocked and use encryption at rest.
- CloudFront deployment mode uses custom header authentication. ALB-only mode requires user-provided SSL certificates for HTTPS.
- Customers are responsible for reviewing and validating all IAM roles, policies, and security group configurations created by this solution to ensure they meet their organization's security requirements and compliance standards.
- For any feedback, questions, or suggestions, please use the issues tab under the [GitHub repository](https://github.com/aws-solutions-library-samples/prebid-server-deployment-on-aws).

## Revisions
See [CHANGELOG.md](./CHANGELOG.md) for revisions.

## Notices

Customers are responsible for making their own independent assessment of the information in this Guidance. This Guidance: (a) is for informational purposes only, (b) represents AWS current product offerings and practices, which are subject to change without notice, and (c) does not create any commitments or assurances from AWS and its affiliates, suppliers or licensors. AWS products or services are provided "as is" without warranties, representations, or conditions of any kind, whether express or implied. AWS responsibilities and liabilities to its customers are controlled by AWS agreements, and this Guidance is not part of, nor does it modify, any agreement between AWS and its customers.

## Collection of operational metrics

This solution collects anonymized operational metrics to help AWS improve the quality of features of the solution.
For more information, including how to disable this capability, please see the [implementation guide](https://docs.aws.amazon.com/solutions/latest/prebid-server-deployment-on-aws/anonymized-data-collection.html).

## Authors

For a list of contributors, please see [Contributors](https://docs.aws.amazon.com/solutions/latest/prebid-server-deployment-on-aws/contributors.html).

***

Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
