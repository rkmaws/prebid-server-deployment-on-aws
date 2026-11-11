# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

# ###############################################################################
# PURPOSE:
#   * Unit test for StackParams (stack_cfn_parameters.py).
#   * Tests parameter definitions, parameter groups, and CfnCondition logic.
# USAGE:
#   cd source && python -m pytest tests/unit_tests/prebid_server/test_stack_cfn_parameters.py -v
###############################################################################

import pytest
import aws_cdk as cdk
from aws_cdk import Stack
from aws_cdk.assertions import Template, Match


class MinimalParamsStack(Stack):
    """Minimal stack that instantiates StackParams for testing."""

    def __init__(self, scope, id, **kwargs):
        super().__init__(scope, id, **kwargs)

        # StackParams needs solutions_template_options on the stack
        self.solutions_template_options = type(
            "obj", (object,), {"add_parameter": lambda self, *a, **kw: None}
        )()

        from prebid_server.stack_cfn_parameters import StackParams
        self.stack_params = StackParams(self)


@pytest.fixture(scope="module")
def template():
    """Synthesize the minimal stack and return a Template for assertions."""
    app = cdk.App(
        context={
            "SOLUTION_ID": "SO0248",
            "SOLUTION_VERSION": "v1.0.0",
        }
    )
    stack = MinimalParamsStack(app, "TestStackParams")
    return Template.from_stack(stack)


@pytest.fixture(scope="module")
def template_json(template):
    """Raw JSON of the synthesized template for direct inspection."""
    return template.to_json()


# ---------------------------------------------------------------------------
# 1. CDN Parameters
# ---------------------------------------------------------------------------
class TestCdnParameters:
    def test_install_cloudfront_and_waf_param(self, template):
        """InstallCloudFrontAndWAF parameter exists with correct definition."""
        template.has_parameter("InstallCloudFrontAndWAF", {
            "Type": "String",
            "Default": "Yes",
            "AllowedValues": ["Yes", "No"],
        })

    def test_ssl_certificate_arn_param(self, template):
        """SSLCertificateARN parameter exists with correct definition."""
        template.has_parameter("SSLCertificateARN", {
            "Type": "String",
            "Default": "",
        })


# ---------------------------------------------------------------------------
# 2. ECS Autoscaling Parameters
# ---------------------------------------------------------------------------
class TestEcsAutoscalingParameters:
    def test_ecs_task_min_capacity_param(self, template):
        """ECSTaskMinCapacity parameter exists with correct definition."""
        template.has_parameter("ECSTaskMinCapacity", {
            "Type": "Number",
            "Default": 2,
        })

    def test_ecs_task_max_capacity_param(self, template):
        """ECSTaskMaxCapacity parameter exists with correct definition."""
        template.has_parameter("ECSTaskMaxCapacity", {
            "Type": "Number",
            "Default": 300,
        })

    def test_requests_per_target_threshold_param(self, template):
        """RequestsPerTargetThreshold parameter exists with correct definition."""
        template.has_parameter("RequestsPerTargetThreshold", {
            "Type": "Number",
            "Default": 5000,
        })

    def test_spot_instance_weight_param(self, template):
        """SpotInstanceWeight parameter exists with correct definition."""
        template.has_parameter("SpotInstanceWeight", {
            "Type": "Number",
            "Default": 1,
        })


# ---------------------------------------------------------------------------
# 3. Container Settings Parameters
# ---------------------------------------------------------------------------
class TestContainerParameters:
    def test_container_image_uri_param(self, template):
        """ContainerImageUri parameter exists with correct definition."""
        template.has_parameter("ContainerImageUri", {
            "Type": "String",
            "Default": "",
        })


# ---------------------------------------------------------------------------
# 4. Log Analytics Parameters
# ---------------------------------------------------------------------------
class TestLogAnalyticsParameters:
    def test_enable_log_analytics_param(self, template):
        """EnableLogAnalytics parameter exists with correct definition."""
        template.has_parameter("EnableLogAnalytics", {
            "Type": "String",
            "Default": "false",
            "AllowedValues": ["true", "false"],
        })


# ---------------------------------------------------------------------------
# 5. RTB Fabric Parameters
# ---------------------------------------------------------------------------
class TestRtbFabricParameters:
    def test_enable_rtb_requester_gateway_param(self, template):
        """EnableRtbRequesterGateway parameter exists with correct definition."""
        template.has_parameter("EnableRtbRequesterGateway", {
            "Type": "String",
            "Default": "false",
            "AllowedValues": ["true", "false"],
        })

    def test_simulator_responder_gateway_id_removed(self, template_json):
        """SimulatorResponderGatewayId parameter is removed (link managed by script)."""
        parameters = template_json.get("Parameters", {})
        assert "SimulatorResponderGatewayId" not in parameters


# ---------------------------------------------------------------------------
# 6. VPC Peering Parameters
# ---------------------------------------------------------------------------
class TestVpcPeeringParameters:
    def test_simulator_vpc_id_param(self, template):
        """SimulatorVpcId parameter exists with correct definition."""
        template.has_parameter("SimulatorVpcId", {
            "Type": "String",
            "Default": "",
        })

    def test_simulator_alb_sg_id_param(self, template):
        """SimulatorAlbSgId parameter exists with correct definition."""
        template.has_parameter("SimulatorAlbSgId", {
            "Type": "String",
            "Default": "",
        })

    def test_simulator_route_table_id_1_param(self, template):
        """SimulatorRouteTableId1 parameter exists with correct definition."""
        template.has_parameter("SimulatorRouteTableId1", {
            "Type": "String",
            "Default": "",
        })

    def test_simulator_route_table_id_2_param(self, template):
        """SimulatorRouteTableId2 parameter exists with correct definition."""
        template.has_parameter("SimulatorRouteTableId2", {
            "Type": "String",
            "Default": "",
        })

    def test_simulator_endpoint_param(self, template):
        """SimulatorEndpoint parameter exists with correct definition."""
        template.has_parameter("SimulatorEndpoint", {
            "Type": "String",
            "Default": "",
        })


# ---------------------------------------------------------------------------
# 7. CfnCondition: HasRtbRequesterGateway
# ---------------------------------------------------------------------------
class TestHasRtbRequesterGatewayCondition:
    def test_condition_exists(self, template_json):
        """HasRtbRequesterGateway condition is defined."""
        conditions = template_json.get("Conditions", {})
        assert "HasRtbRequesterGateway" in conditions

    def test_condition_uses_equals_logic(self, template_json):
        """HasRtbRequesterGateway = EnableRtbRequesterGateway=='true'."""
        conditions = template_json["Conditions"]
        condition_expr = conditions["HasRtbRequesterGateway"]
        # Should be Fn::Equals with EnableRtbRequesterGateway == "true"
        assert "Fn::Equals" in condition_expr, (
            f"Expected Fn::Equals in HasRtbRequesterGateway, got: {condition_expr}"
        )
        equals_args = condition_expr["Fn::Equals"]
        assert {"Ref": "EnableRtbRequesterGateway"} in equals_args
        assert "true" in equals_args


# ---------------------------------------------------------------------------
# 8. CfnCondition: HasSimulatorFabricLink is removed
# ---------------------------------------------------------------------------
class TestHasSimulatorFabricLinkRemoved:
    def test_condition_does_not_exist(self, template_json):
        """HasSimulatorFabricLink condition is removed (link managed by script)."""
        conditions = template_json.get("Conditions", {})
        assert "HasSimulatorFabricLink" not in conditions


# ---------------------------------------------------------------------------
# 9. CfnCondition: UseVpcPeering
# ---------------------------------------------------------------------------
class TestUseVpcPeeringCondition:
    def test_condition_exists(self, template_json):
        """UseVpcPeering condition is defined."""
        conditions = template_json.get("Conditions", {})
        assert "UseVpcPeering" in conditions

    def test_condition_checks_vpc_id_not_empty(self, template_json):
        """UseVpcPeering = SimulatorVpcId != ''."""
        conditions = template_json["Conditions"]
        condition_expr = conditions["UseVpcPeering"]
        # Should be Fn::Not wrapping Fn::Equals
        assert "Fn::Not" in condition_expr, (
            f"Expected Fn::Not in UseVpcPeering, got: {condition_expr}"
        )
        not_clause = condition_expr["Fn::Not"]
        equals_clause = not_clause[0]
        assert "Fn::Equals" in equals_clause
        equals_args = equals_clause["Fn::Equals"]
        assert {"Ref": "SimulatorVpcId"} in equals_args
        assert "" in equals_args


# ---------------------------------------------------------------------------
# 10. CfnCondition: HasSimulatorEndpoint
# ---------------------------------------------------------------------------
class TestHasSimulatorEndpointCondition:
    def test_condition_exists(self, template_json):
        """HasSimulatorEndpoint condition is defined."""
        conditions = template_json.get("Conditions", {})
        assert "HasSimulatorEndpoint" in conditions

    def test_condition_checks_endpoint_not_empty(self, template_json):
        """HasSimulatorEndpoint = SimulatorEndpoint != ''."""
        conditions = template_json["Conditions"]
        condition_expr = conditions["HasSimulatorEndpoint"]
        # Should be Fn::Not wrapping Fn::Equals
        assert "Fn::Not" in condition_expr, (
            f"Expected Fn::Not in HasSimulatorEndpoint, got: {condition_expr}"
        )
        not_clause = condition_expr["Fn::Not"]
        equals_clause = not_clause[0]
        assert "Fn::Equals" in equals_clause
        equals_args = equals_clause["Fn::Equals"]
        assert {"Ref": "SimulatorEndpoint"} in equals_args
        assert "" in equals_args


# ---------------------------------------------------------------------------
# 11. No EnableRtbFabric parameter in PrebidServerStack
# ---------------------------------------------------------------------------
class TestNoEnableRtbFabricParameter:
    def test_no_enable_rtb_fabric_param(self, template_json):
        """There should be no EnableRtbFabric parameter — that belongs to BidderSimulatorStack."""
        parameters = template_json.get("Parameters", {})
        assert "EnableRtbFabric" not in parameters
