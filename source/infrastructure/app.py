# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import logging
import sys
from pathlib import Path

from aws_cdk import App, CfnOutput
from aws_solutions.cdk import CDKSolution

from prebid_server.prebid_server_stack import PrebidServerStack

# Add the loadtest directory to the Python path to import BidderSimulatorStack
sys.path.insert(0, str(Path(__file__).parent.parent / "loadtest" / "bidder_simulator"))
from bidder_simulator_stack import BidderSimulatorStack

solution = CDKSolution(cdk_json_path=Path(__file__).parent.absolute() / "cdk.json")

logger = logging.getLogger("cdk-helper")


def synthesizer():
    return CDKSolution(
        cdk_json_path=Path(__file__).parent.absolute() / "cdk.json"
    ).synthesizer


@solution.context.requires("SOLUTION_NAME")
@solution.context.requires("SOLUTION_ID")
@solution.context.requires("SOLUTION_VERSION")
@solution.context.requires("BUCKET_NAME")
def build_app(context):
    app = App(context=context)

    # Read context flag for bidder simulator synthesis
    # This is a build-time decision: whether to synthesize the BidderSimulatorStack template
    deploy_bidding_simulator = app.node.try_get_context("deployBiddingSimulator")
    deploy_bidding_simulator = deploy_bidding_simulator in [True, 'true', 'True']

    # Conditionally synthesize BidderSimulatorStack
    # No cross-stack references — deploy.sh handles the two-step deployment
    # and passes BidderSimulatorStack outputs as PrebidServerStack CF parameters
    if deploy_bidding_simulator:
        BidderSimulatorStack(app, "BiddingServerSimulator")

    # Deploy main Prebid Server stack
    # All configuration is via CloudFormation parameters at deploy time:
    # - EnableLogAnalytics, EnableRtbRequesterGateway, SimulatorResponderGatewayId
    # - SimulatorVpcId, SimulatorAlbSgId, SimulatorRouteTableId1/2, SimulatorEndpoint
    # No cross-stack references from BidderSimulatorStack
    PrebidServerStack(
        app,
        PrebidServerStack.name,
        description=PrebidServerStack.description,
        template_filename=PrebidServerStack.template_filename,
        synthesizer=synthesizer(),
    )

    return app.synth(validate_on_synthesis=True, skip_validation=False)


if __name__ == "__main__":
    build_app()
