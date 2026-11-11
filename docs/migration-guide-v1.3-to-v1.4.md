# Migration Guide: v1.3.0 → v1.4.0

## Overview

v1.4.0 migrates from CDK context flags to CloudFormation parameters for connectivity and log analytics configuration. This enables customers deploying via the CloudFormation console (without CDK) to configure settings at deploy time.

**Key changes:**
- `--include-rtb-fabric` flag removed → replaced by `--simulator-connectivity` and `--enable-rtb-requester-gateway`
- `--enable-log-analytics` now passes a CF parameter (not CDK context)
- Two-step deployment: BidderSimulatorStack first, then PrebidServerStack with outputs as parameters
- Accept Lambda and AcceptFabricLinkCr custom resources removed (Fabric Link acceptance is now managed by `simulator_fabric_link.py`)
- WaitForGateway Lambda and custom resource are now conditional on `EnableRtbRequesterGateway=true` (retained for gateway readiness checks)
- All conditional resources use CfnConditions (deploy-time) instead of Python-side if/else (build-time)

---

## Upgrade Risks for Existing Stacks

### ⚠️ Critical: Existing RTB Fabric resources may be deleted

If your existing stack was deployed with `--include-rtb-fabric`, the Requester Gateway and Fabric Link exist in the template without CfnConditions. In v1.4.0, these resources have CfnConditions attached. If you update the stack **without** passing the equivalent parameters, CloudFormation interprets the condition as false and **deletes the resources**.

| Existing deployment | Safe v1.4.0 command | What happens if you forget params |
|---|---|---|
| `--deploy-bidding-simulator --include-rtb-fabric` | `./deploy.sh --deploy-bidding-simulator --profile <p> --region <r>` | Requester Gateway + Fabric Link **DELETED** |
| `--deploy-bidding-simulator` (no RTB Fabric) | `./deploy.sh --deploy-bidding-simulator --simulator-connectivity vpc-peering --profile <p> --region <r>` | VPC peering resources **DELETED** |
| No simulator, no RTB Fabric | `./deploy.sh --profile <p> --region <r>` | Safe — no conditional resources existed |

### Resources that will be deleted (intentionally)

These resources are removed from the template in v1.4.0 and will be deleted on stack update regardless of parameters:

| Resource | Why removed |
|----------|-------------|
| Accept Lambda (`AcceptFabricLinkFunction`) | Fabric Link acceptance is now managed by `simulator_fabric_link.py` script |
| Accept custom resource (`AcceptFabricLinkCr`) | Removed with Accept Lambda |

These deletions are safe — they are operational Lambdas that are no longer needed.

### Resources that are now conditional (retained when `EnableRtbRequesterGateway=true`)

| Resource | Condition | Purpose |
|----------|-----------|---------|
| WaitForGateway Lambda (`WaitForGatewayFunction`) | `HasRtbRequesterGateway` | Ensures gateway is fully provisioned before Fabric Link creation |
| WaitForGateway custom resource (`WaitForRequesterGatewayCr`) | `HasRtbRequesterGateway` | Polls until gateway reaches ACTIVE state |

If you deploy with `EnableRtbRequesterGateway=true`, these resources will be present in your stack.

### ECS task definition changes

The ECS environment variables now use CloudFormation intrinsics (`Fn::If`) instead of hardcoded strings:

| Variable | v1.3.0 behavior | v1.4.0 behavior |
|----------|-----------------|-----------------|
| `AMT_ADAPTER_ENABLED` | Hardcoded `"true"` or `"false"` at synth time | `Fn::If(HasSimulatorEndpoint, "true", "false")` — resolved at deploy time |
| `AMT_BIDDING_SERVER_SIMULATOR_ENDPOINT` | Hardcoded URL at synth time | `Fn::If` chain: Fabric Link URL > SimulatorEndpoint param > empty |
| `LOG_ANALYTICS_ENABLED` | Hardcoded at synth time | References `EnableLogAnalytics` CF parameter directly |

This triggers a new ECS task deployment (rolling update) on stack update.

---

## Migration Steps

### Scenario 1: Existing stack with RTB Fabric simulator

**v1.3.0 command:**
```sh
./deploy.sh --deploy-bidding-simulator --include-rtb-fabric --profile rtb --region us-east-1
```

**v1.4.0 equivalent:**
```sh
./deploy.sh --deploy-bidding-simulator --profile rtb --region us-east-1
```

The `--simulator-connectivity` defaults to `rtb-fabric`, so no extra flag needed. The script:
1. Deploys BidderSimulatorStack with `EnableRtbFabric=true`
2. Reads `ResponderGatewayId` from BSS outputs
3. Deploys PrebidServerStack with `EnableRtbRequesterGateway=true` + `SimulatorResponderGatewayId=<id>`

**Post-update action:** Manually accept the Fabric Link from the responder side (BidderSimulatorStack account). The Accept Lambda no longer does this automatically.

### Scenario 2: Existing stack with VPC peering simulator

**v1.3.0 command:**
```sh
./deploy.sh --deploy-bidding-simulator --profile rtb --region us-east-1
```

**v1.4.0 equivalent:**
```sh
./deploy.sh --deploy-bidding-simulator --simulator-connectivity vpc-peering --profile rtb --region us-east-1
```

### Scenario 3: Existing stack without simulator

**v1.3.0 command:**
```sh
./deploy.sh --profile rtb --region us-east-1
```

**v1.4.0 equivalent (identical):**
```sh
./deploy.sh --profile rtb --region us-east-1
```

No risk — no conditional resources existed in the previous deployment.

### Scenario 4: Fresh deployment (recommended for first test)

Deploy to a new account or region to validate the new flow without risk to existing resources:

```sh
./deploy.sh --deploy-bidding-simulator --enable-log-analytics --profile <new-profile> --region us-east-1
```

---

## New deploy.sh Flags

| Flag | Description | Default |
|------|-------------|---------|
| `--deploy-bidding-simulator` | Deploy the BidderSimulatorStack | false |
| `--simulator-connectivity MODE` | `rtb-fabric` or `vpc-peering` | `rtb-fabric` |
| `--enable-log-analytics` | Enable log analytics (CF parameter) | false |
| `--enable-rtb-requester-gateway` | Provision Requester Gateway for partner onboarding (no simulator needed) | false |
| `--profile PROFILE` | AWS CLI profile | — |
| `--region REGION` | AWS region | — |
| `--synth` | Synthesize only (no deploy) | — |
| `--skip-copy` | Skip AMT bidder file copy | false |

### Removed flags

| Flag | Replacement |
|------|-------------|
| `--include-rtb-fabric` | `--simulator-connectivity rtb-fabric` (default) or `--enable-rtb-requester-gateway` |

---

## New CloudFormation Parameters (PrebidServerStack)

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `EnableLogAnalytics` | String (true/false) | false | Enable log analytics |
| `EnableRtbRequesterGateway` | String (true/false) | false | Create RTB Fabric Requester Gateway |
| `ContainerImageUri` | String | "" | ECR image URI (for synthesized template path) |
| `SimulatorResponderGatewayId` | String | "" | Responder Gateway ID from BidderSimulatorStack |
| `SimulatorVpcId` | String | "" | Simulator VPC ID (VPC peering fallback) |
| `SimulatorAlbSgId` | String | "" | Simulator ALB Security Group ID |
| `SimulatorRouteTableId1` | String | "" | First private subnet route table ID |
| `SimulatorRouteTableId2` | String | "" | Second private subnet route table ID |
| `SimulatorEndpoint` | String | "" | Simulator ALB endpoint (VPC peering fallback) |

### New CloudFormation Parameters (BidderSimulatorStack)

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `EnableRtbFabric` | String (true/false) | true | Create Responder Gateway |

---

## CfnConditions (PrebidServerStack)

| Condition | Expression | Controls |
|-----------|-----------|----------|
| `HasRtbRequesterGateway` | `EnableRtbRequesterGateway == "true" OR SimulatorResponderGatewayId != ""` | Requester Gateway, SecurityGroup, Outputs |
| `HasSimulatorFabricLink` | `SimulatorResponderGatewayId != ""` | Fabric Link |
| `UseVpcPeering` | `SimulatorVpcId != "" AND SimulatorResponderGatewayId == ""` | VPC Peering resources |
| `HasSimulatorEndpoint` | `SimulatorResponderGatewayId != "" OR SimulatorEndpoint != ""` | AMT adapter enabled |

---

## Deployment Scenarios Matrix

| # | Customer Intent | deploy.sh command | Result |
|---|---|---|---|
| 1 | Simulator demo with RTB Fabric | `--deploy-bidding-simulator` | Requester GW + Fabric Link + BSS |
| 2 | Simulator demo without RTB Fabric | `--deploy-bidding-simulator --simulator-connectivity vpc-peering` | VPC peering + BSS |
| 3 | RTB Fabric gateway for future partners | `--enable-rtb-requester-gateway` | Requester GW only |
| 4 | Just Prebid Server | (no extra flags) | Nothing extra |
| 5 | Prebid Server + analytics | `--enable-log-analytics` | Log analytics enabled |

---

## Rollback Plan

If the stack update fails or produces unexpected results:

1. **CloudFormation auto-rollback:** If the update fails, CloudFormation rolls back to the previous template automatically.
2. **Manual rollback:** Redeploy with the v1.3.0 branch: `git checkout release/v1.3.0 && ./deploy.sh --deploy-bidding-simulator --include-rtb-fabric --profile <p> --region <r>`
3. **Fabric Link re-creation:** If the Fabric Link was deleted, it can be recreated manually via AWS CLI after redeploying with the correct parameters.
