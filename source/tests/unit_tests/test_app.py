# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

# ###############################################################################
# PURPOSE:
#   * Unit test for infrastructure/app.py.
#   * Verifies stack instantiation and context-driven behavior.
#   * Uses Template.from_stack() for BidderSimulatorStack (lightweight).
#   * Uses inspection-based tests for PrebidServerStack (avoids full synthesis
#     which requires all CDK context flags and takes 70+ seconds).
# USAGE:
#   cd source && python -m pytest tests/unit_tests/test_app.py -v
###############################################################################

import inspect
import sys
from pathlib import Path

import pytest
from aws_cdk import App
from aws_cdk.assertions import Template

# Add infrastructure path for imports
sys.path.insert(0, "./infrastructure")
sys.path.insert(0, "./loadtest/bidder_simulator")


class TestBidderSimulatorSynthesis:
    """Test BidderSimulatorStack synthesis (lightweight, no heavy dependencies)."""

    def test_bidder_simulator_stack_synthesizes(self):
        """BidderSimulatorStack is synthesized when deployBiddingSimulator=true."""
        from bidder_simulator_stack import BidderSimulatorStack

        app = App(context={"BIDDER_TYPE": "loadtest"})
        stack = BidderSimulatorStack(app, "BiddingServerSimulator")
        template = Template.from_stack(stack)
        assert template is not None

        # BidderSimulatorStack should have its own EnableRtbFabric parameter
        template.has_parameter("EnableRtbFabric", {
            "Type": "String",
            "Default": "true",
        })

    def test_bidder_simulator_no_cross_stack_refs(self):
        """BidderSimulatorStack does not accept include_rtb_fabric constructor param."""
        from bidder_simulator_stack import BidderSimulatorStack

        app = App(context={"BIDDER_TYPE": "loadtest"})
        # Should work without any RTB-related constructor parameters
        stack = BidderSimulatorStack(app, "TestStack")
        assert stack is not None

        # Should reject include_rtb_fabric kwarg
        with pytest.raises(TypeError):
            BidderSimulatorStack(app, "TestReject", include_rtb_fabric=True)


class TestPrebidServerStackInterface:
    """Test PrebidServerStack interface — no cross-stack reference parameters required."""

    def test_no_required_cross_stack_params(self):
        """PrebidServerStack constructor does not require cross-stack reference parameters.

        All configuration (simulator_endpoint, RTB fabric, VPC peering) is via
        CloudFormation parameters at deploy time, not constructor arguments.
        """
        from prebid_server.prebid_server_stack import PrebidServerStack

        sig = inspect.signature(PrebidServerStack.__init__)
        params = sig.parameters

        # These params should have defaults (not required)
        optional_params = [
            "simulator_endpoint",
            "include_rtb_fabric",
            "enable_log_analytics",
            "responder_gateway_id",
            "bidder_simulator_vpc_id",
            "bidder_simulator_alb_sg_id",
            "bidder_simulator_route_table_ids",
        ]
        for param_name in optional_params:
            if param_name in params:
                assert params[param_name].default is not inspect.Parameter.empty, (
                    f"Parameter '{param_name}' should have a default value (not be required)"
                )

    def test_no_enable_log_analytics_context_read(self):
        """PrebidServerStack uses CF parameter for EnableLogAnalytics, not CDK context."""
        from prebid_server.stack_cfn_parameters import StackParams
        import aws_cdk as cdk
        from aws_cdk import Stack

        # Create a minimal stack to verify the parameter exists
        app = cdk.App(context={"SOLUTION_ID": "SO0248", "SOLUTION_VERSION": "v1.0.0"})

        class MinimalStack(Stack):
            def __init__(self, scope, id):
                super().__init__(scope, id)
                self.solutions_template_options = type(
                    "obj", (object,), {"add_parameter": lambda self, *a, **kw: None}
                )()
                self.stack_params = StackParams(self)

        stack = MinimalStack(app, "TestStack")
        template = Template.from_stack(stack)

        # EnableLogAnalytics is a CF parameter, not a context value
        template.has_parameter("EnableLogAnalytics", {
            "Type": "String",
            "Default": "false",
            "AllowedValues": ["true", "false"],
        })

    def test_no_include_rtb_fabric_context_read(self):
        """PrebidServerStack uses CF parameters for RTB Fabric, not CDK context."""
        from prebid_server.stack_cfn_parameters import StackParams
        import aws_cdk as cdk
        from aws_cdk import Stack

        app = cdk.App(context={"SOLUTION_ID": "SO0248", "SOLUTION_VERSION": "v1.0.0"})

        class MinimalStack(Stack):
            def __init__(self, scope, id):
                super().__init__(scope, id)
                self.solutions_template_options = type(
                    "obj", (object,), {"add_parameter": lambda self, *a, **kw: None}
                )()
                self.stack_params = StackParams(self)

        stack = MinimalStack(app, "TestStack")
        template = Template.from_stack(stack)

        # RTB Fabric is controlled via CF parameters, not context
        template.has_parameter("EnableRtbRequesterGateway", {
            "Type": "String",
            "Default": "false",
        })

    def test_vpc_peering_params_are_cf_parameters(self):
        """VPC peering configuration is via CF parameters, not constructor args."""
        from prebid_server.stack_cfn_parameters import StackParams
        import aws_cdk as cdk
        from aws_cdk import Stack

        app = cdk.App(context={"SOLUTION_ID": "SO0248", "SOLUTION_VERSION": "v1.0.0"})

        class MinimalStack(Stack):
            def __init__(self, scope, id):
                super().__init__(scope, id)
                self.solutions_template_options = type(
                    "obj", (object,), {"add_parameter": lambda self, *a, **kw: None}
                )()
                self.stack_params = StackParams(self)

        stack = MinimalStack(app, "TestStack")
        template = Template.from_stack(stack)

        # Verify VPC peering params exist as CF parameters
        template.has_parameter("SimulatorVpcId", {"Type": "String", "Default": ""})
        template.has_parameter("SimulatorAlbSgId", {"Type": "String", "Default": ""})
        template.has_parameter("SimulatorRouteTableId1", {"Type": "String", "Default": ""})
        template.has_parameter("SimulatorRouteTableId2", {"Type": "String", "Default": ""})
        template.has_parameter("SimulatorEndpoint", {"Type": "String", "Default": ""})


class TestAppBuildFunction:
    """Test the app.py build_app function behavior."""

    def _get_app_module(self):
        """Import the infrastructure app module explicitly."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "infrastructure_app",
            "./infrastructure/app.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_app_module_imports(self):
        """app.py can be imported without errors."""
        module = self._get_app_module()
        assert hasattr(module, "build_app")

    def test_app_does_not_read_enable_log_analytics_context(self):
        """app.py does not read enableLogAnalytics from CDK context."""
        module = self._get_app_module()
        source = inspect.getsource(module.build_app.__wrapped__)
        assert "enableLogAnalytics" not in source

    def test_app_does_not_read_include_rtb_fabric_context(self):
        """app.py does not read includeRtbFabric from CDK context."""
        module = self._get_app_module()
        source = inspect.getsource(module.build_app.__wrapped__)
        assert "includeRtbFabric" not in source

    def test_app_reads_deploy_bidding_simulator_context(self):
        """app.py reads deployBiddingSimulator from CDK context."""
        module = self._get_app_module()
        source = inspect.getsource(module.build_app.__wrapped__)
        assert "deployBiddingSimulator" in source
