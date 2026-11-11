# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

# ###############################################################################
# PURPOSE:
#   * Unit test for the full BidderSimulatorStack.
#   * Tests EnableRtbFabric parameter, HasRtbFabric condition, conditional resources,
#     and unconditional resources (VPC, ALB, Lambda).
# USAGE:
#   cd source && python -m pytest tests/unit_tests/bidder_simulator/test_bidder_simulator_stack.py -v
###############################################################################

import sys

import pytest
from aws_cdk import App
from aws_cdk.assertions import Template, Match

# Add the bidder simulator directory to the Python path
sys.path.insert(0, "./loadtest/bidder_simulator")
from bidder_simulator_stack import BidderSimulatorStack


@pytest.fixture(scope="module")
def template():
    """Synthesize BidderSimulatorStack and return a Template for assertions."""
    app = App(context={"BIDDER_TYPE": "loadtest"})
    stack = BidderSimulatorStack(app, "TestBidderSimulatorStack")
    return Template.from_stack(stack)


@pytest.fixture(scope="module")
def template_json(template):
    """Raw JSON of the synthesized template for direct inspection."""
    return template.to_json()


# ---------------------------------------------------------------------------
# 1. EnableRtbFabric parameter exists with correct definition
# ---------------------------------------------------------------------------
class TestEnableRtbFabricParameter:
    def test_parameter_exists(self, template):
        """EnableRtbFabric parameter is defined."""
        template.has_parameter("EnableRtbFabric", {
            "Type": "String",
            "Default": "true",
            "AllowedValues": ["true", "false"],
        })

    def test_parameter_has_description(self, template_json):
        """EnableRtbFabric parameter has a meaningful description."""
        params = template_json.get("Parameters", {})
        assert "EnableRtbFabric" in params
        desc = params["EnableRtbFabric"].get("Description", "")
        assert "RTB Fabric" in desc


# ---------------------------------------------------------------------------
# 2. HasRtbFabric condition exists
# ---------------------------------------------------------------------------
class TestHasRtbFabricCondition:
    def test_condition_exists(self, template):
        """HasRtbFabric CfnCondition is defined."""
        template.has_condition("HasRtbFabric", {
            "Fn::Equals": [{"Ref": "EnableRtbFabric"}, "true"]
        })


# ---------------------------------------------------------------------------
# 3. Responder Gateway has HasRtbFabric condition
# ---------------------------------------------------------------------------
class TestResponderGatewayCondition:
    def test_responder_gateway_has_condition(self, template):
        """Responder Gateway is gated by HasRtbFabric."""
        template.has_resource("AWS::RTBFabric::ResponderGateway", {
            "Condition": "HasRtbFabric",
        })

    def test_responder_gateway_count(self, template):
        """Exactly one Responder Gateway exists."""
        template.resource_count_is("AWS::RTBFabric::ResponderGateway", 1)


# ---------------------------------------------------------------------------
# 4. Responder Gateway security group has HasRtbFabric condition
# ---------------------------------------------------------------------------
class TestResponderGatewaySecurityGroupCondition:
    def test_sg_has_condition(self, template):
        """Responder Gateway security group is gated by HasRtbFabric."""
        template.has_resource("AWS::EC2::SecurityGroup", {
            "Condition": "HasRtbFabric",
            "Properties": {
                "GroupDescription": "Security group for RTB Fabric Responder Gateway",
            },
        })


# ---------------------------------------------------------------------------
# 5. Responder Gateway outputs have HasRtbFabric condition
# ---------------------------------------------------------------------------
class TestResponderGatewayOutputs:
    def test_responder_gateway_id_output_has_condition(self, template):
        """ResponderGatewayId output is gated by HasRtbFabric."""
        template.has_output("ResponderGatewayId", {
            "Condition": "HasRtbFabric",
        })

    def test_responder_gateway_arn_output_has_condition(self, template):
        """ResponderGatewayArn output is gated by HasRtbFabric."""
        template.has_output("ResponderGatewayArn", {
            "Condition": "HasRtbFabric",
        })


# ---------------------------------------------------------------------------
# 6. VPC is always present (no condition)
# ---------------------------------------------------------------------------
class TestVpcAlwaysPresent:
    def test_vpc_has_no_condition(self, template):
        """VPC is always created regardless of EnableRtbFabric value."""
        template.has_resource("AWS::EC2::VPC", {
            "Condition": Match.absent(),
        })

    def test_vpc_cidr(self, template):
        """VPC uses the expected CIDR block."""
        template.has_resource_properties("AWS::EC2::VPC", {
            "CidrBlock": "10.1.0.0/16",
        })


# ---------------------------------------------------------------------------
# 7. ALB is always present (no condition)
# ---------------------------------------------------------------------------
class TestAlbAlwaysPresent:
    def test_alb_has_no_condition(self, template):
        """ALB is always created regardless of EnableRtbFabric value."""
        template.has_resource("AWS::ElasticLoadBalancingV2::LoadBalancer", {
            "Condition": Match.absent(),
        })

    def test_alb_is_internal(self, template):
        """ALB is internal (not internet-facing)."""
        template.has_resource_properties("AWS::ElasticLoadBalancingV2::LoadBalancer", {
            "Scheme": "internal",
        })


# ---------------------------------------------------------------------------
# 8. Lambda is always present (no condition)
# ---------------------------------------------------------------------------
class TestLambdaAlwaysPresent:
    def test_lambda_has_no_condition(self, template_json):
        """Lambda function is always created regardless of EnableRtbFabric value."""
        resources = template_json["Resources"]
        lambda_functions = [
            (lid, r) for lid, r in resources.items()
            if r.get("Type") == "AWS::Lambda::Function"
            and "bidderSimulator" in lid
        ]
        assert len(lambda_functions) >= 1, "Bidder simulator Lambda function not found"
        for lid, resource in lambda_functions:
            assert resource.get("Condition") is None, (
                f"Lambda {lid} should not have a condition"
            )


# ---------------------------------------------------------------------------
# 9. Constructor does NOT accept include_rtb_fabric parameter
# ---------------------------------------------------------------------------
class TestNoIncludeRtbFabricConstructorParam:
    def test_constructor_works_without_rtb_params(self):
        """BidderSimulatorStack constructor works without include_rtb_fabric parameter."""
        app = App(context={"BIDDER_TYPE": "loadtest"})
        # This should not raise — no include_rtb_fabric param needed
        stack = BidderSimulatorStack(app, "TestNoRtbParam")
        assert stack is not None

    def test_constructor_rejects_include_rtb_fabric(self):
        """BidderSimulatorStack constructor does not accept include_rtb_fabric kwarg."""
        app = App(context={"BIDDER_TYPE": "loadtest"})
        with pytest.raises(TypeError):
            BidderSimulatorStack(app, "TestReject", include_rtb_fabric=True)


# ---------------------------------------------------------------------------
# 10. ALB security group ingress from Responder Gateway has condition
# ---------------------------------------------------------------------------
class TestAlbIngressFromGatewayCondition:
    def test_alb_ingress_from_gateway_has_condition(self, template):
        """ALB SG ingress from Responder Gateway is gated by HasRtbFabric."""
        template.has_resource("AWS::EC2::SecurityGroupIngress", {
            "Condition": "HasRtbFabric",
            "Properties": {
                "IpProtocol": "tcp",
                "FromPort": 80,
                "ToPort": 80,
                "Description": Match.string_like_regexp(".*RTB Fabric.*"),
            },
        })
