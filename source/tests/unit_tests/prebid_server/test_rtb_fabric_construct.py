# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

# ###############################################################################
# PURPOSE:
#   * Unit test for RtbFabricConstruct (Requester Gateway + WaitForGateway).
#   * Tests CfnCondition-based gating, resource dependencies, and outputs.
#   * Fabric Link lifecycle is managed externally by simulator-fabric-link.sh.
# USAGE:
#   cd source && python -m pytest tests/unit_tests/prebid_server/test_rtb_fabric_construct.py -v
###############################################################################

import pytest
import aws_cdk as cdk
from aws_cdk import Stack, aws_ec2 as ec2
from aws_cdk.assertions import Template, Match
from prebid_server.rtb_fabric_construct import RtbFabricConstruct
from prebid_server.stack_cfn_parameters import StackParams


class MinimalRtbFabricStack(Stack):
    """Minimal stack that instantiates VPC + RtbFabricConstruct for testing.

    Uses a plain ec2.Vpc wrapped in a simple object to satisfy the
    vpc_construct.prebid_vpc interface, avoiding the real VpcConstruct
    which requires S3 bucket dependencies.
    """

    def __init__(self, scope, id, **kwargs):
        super().__init__(scope, id, **kwargs)

        # Minimal VPC satisfying RtbFabricConstruct requirements
        vpc = ec2.Vpc(self, "TestVpc", max_azs=2)
        vpc_construct = type("obj", (object,), {"prebid_vpc": vpc})()

        # StackParams needs solutions_template_options on the stack
        self.solutions_template_options = type(
            "obj", (object,), {"add_parameter": lambda self, *a, **kw: None}
        )()
        stack_params = StackParams(self)

        # Instantiate the construct under test
        self.rtb_fabric = RtbFabricConstruct(
            self, "RtbFabric", vpc_construct, stack_params
        )


@pytest.fixture(scope="module")
def template():
    """Synthesize the minimal stack and return a Template for assertions."""
    app = cdk.App(
        context={
            "SOLUTION_ID": "SO0248",
            "SOLUTION_VERSION": "v1.0.0",
        }
    )
    stack = MinimalRtbFabricStack(app, "TestRtbFabricStack")
    return Template.from_stack(stack)


@pytest.fixture(scope="module")
def template_json(template):
    """Raw JSON of the synthesized template for direct inspection."""
    return template.to_json()


# ---------------------------------------------------------------------------
# 1. RequesterGateway has HasRtbRequesterGateway condition
# ---------------------------------------------------------------------------
class TestRequesterGatewayCondition:
    def test_requester_gateway_has_condition(self, template):
        """RequesterGateway resource is gated by HasRtbRequesterGateway."""
        template.has_resource("AWS::RTBFabric::RequesterGateway", {
            "Condition": "HasRtbRequesterGateway",
        })

    def test_requester_gateway_count(self, template):
        """Exactly one RequesterGateway resource exists."""
        template.resource_count_is("AWS::RTBFabric::RequesterGateway", 1)


# ---------------------------------------------------------------------------
# 2. CfnLink (FabricLink) is removed from the template
# ---------------------------------------------------------------------------
class TestFabricLinkRemoved:
    def test_no_fabric_link_resource(self, template):
        """CfnLink resource is no longer in the template (managed by script)."""
        template.resource_count_is("AWS::RTBFabric::Link", 0)


# ---------------------------------------------------------------------------
# 3. WaitForGateway custom resource has HasRtbRequesterGateway condition
# ---------------------------------------------------------------------------
class TestWaitForGatewayCustomResource:
    def test_wait_for_gateway_cr_has_condition(self, template_json):
        """WaitForGateway custom resource is gated by HasRtbRequesterGateway."""
        resources = template_json["Resources"]
        wait_cr_found = False
        for logical_id, resource in resources.items():
            if (
                resource.get("Type") == "AWS::CloudFormation::CustomResource"
                and "WaitForRequesterGateway" in logical_id
            ):
                wait_cr_found = True
                assert resource.get("Condition") == "HasRtbRequesterGateway", (
                    f"WaitForGateway CR ({logical_id}) should have HasRtbRequesterGateway condition"
                )
        assert wait_cr_found, "WaitForRequesterGateway custom resource not found"


# ---------------------------------------------------------------------------
# 4. AcceptFabricLink custom resource is removed from the template
# ---------------------------------------------------------------------------
class TestAcceptFabricLinkRemoved:
    def test_no_accept_fabric_link_cr(self, template_json):
        """AcceptFabricLink custom resource is no longer in the template."""
        resources = template_json["Resources"]
        for logical_id, resource in resources.items():
            if (
                resource.get("Type") == "AWS::CloudFormation::CustomResource"
                and "AcceptFabricLink" in logical_id
            ):
                pytest.fail(f"AcceptFabricLink CR ({logical_id}) should not exist")


# ---------------------------------------------------------------------------
# 5. WaitForGateway depends on RequesterGateway
# ---------------------------------------------------------------------------
class TestWaitForGatewayDependsOnGateway:
    def test_wait_for_gateway_depends_on_requester_gateway(self, template_json):
        """WaitForGateway CR has an explicit DependsOn the RequesterGateway."""
        resources = template_json["Resources"]

        # Find the RequesterGateway logical ID
        gateway_id = None
        for logical_id, resource in resources.items():
            if resource.get("Type") == "AWS::RTBFabric::RequesterGateway":
                gateway_id = logical_id
                break
        assert gateway_id is not None, "RequesterGateway resource not found"

        # Find the WaitForGateway CR logical ID
        wait_cr_id = None
        for logical_id, resource in resources.items():
            if (
                resource.get("Type") == "AWS::CloudFormation::CustomResource"
                and "WaitForRequesterGateway" in logical_id
            ):
                wait_cr_id = logical_id
                break
        assert wait_cr_id is not None, "WaitForGateway CR not found"

        # Verify DependsOn
        depends_on = resources[wait_cr_id].get("DependsOn", [])
        assert gateway_id in depends_on, (
            f"WaitForGateway CR should depend on {gateway_id}, got DependsOn={depends_on}"
        )


# ---------------------------------------------------------------------------
# 6. RequesterGateway has VPC attachment and security group
# ---------------------------------------------------------------------------
class TestRequesterGatewayVpcAttachment:
    def test_requester_gateway_has_vpc_and_subnets(self, template):
        """RequesterGateway is attached to VPC with subnets and security groups."""
        template.has_resource_properties("AWS::RTBFabric::RequesterGateway", {
            "VpcId": Match.any_value(),
            "SubnetIds": Match.any_value(),
            "SecurityGroupIds": Match.any_value(),
        })

    def test_security_group_allows_https(self, template):
        """Security group for RequesterGateway allows HTTPS (port 443) ingress."""
        template.has_resource_properties("AWS::EC2::SecurityGroup", {
            "SecurityGroupIngress": Match.array_with([
                Match.object_like({
                    "IpProtocol": "tcp",
                    "FromPort": 443,
                    "ToPort": 443,
                })
            ]),
        })

    def test_security_group_has_condition(self, template):
        """RequesterGateway security group is gated by HasRtbRequesterGateway."""
        template.has_resource("AWS::EC2::SecurityGroup", {
            "Condition": "HasRtbRequesterGateway",
            "Properties": {
                "GroupDescription": "Security group for RTB Fabric Requester Gateway",
            },
        })


# ---------------------------------------------------------------------------
# 7. RequesterGateway outputs have HasRtbRequesterGateway condition
# ---------------------------------------------------------------------------
class TestRequesterGatewayOutputs:
    def test_requester_gateway_id_output_has_condition(self, template_json):
        """RequesterGatewayId output is gated by HasRtbRequesterGateway."""
        outputs = template_json.get("Outputs", {})
        assert "RequesterGatewayId" in outputs
        assert outputs["RequesterGatewayId"].get("Condition") == "HasRtbRequesterGateway"

    def test_requester_gateway_arn_output_has_condition(self, template_json):
        """RequesterGatewayArn output is gated by HasRtbRequesterGateway."""
        outputs = template_json.get("Outputs", {})
        assert "RequesterGatewayArn" in outputs
        assert outputs["RequesterGatewayArn"].get("Condition") == "HasRtbRequesterGateway"


# ---------------------------------------------------------------------------
# 8. FabricLink outputs are removed
# ---------------------------------------------------------------------------
class TestFabricLinkOutputsRemoved:
    def test_no_fabric_link_id_output(self, template_json):
        """FabricLinkId output is no longer in the template."""
        outputs = template_json.get("Outputs", {})
        assert "FabricLinkId" not in outputs

    def test_no_fabric_link_arn_output(self, template_json):
        """FabricLinkArn output is no longer in the template."""
        outputs = template_json.get("Outputs", {})
        assert "FabricLinkArn" not in outputs


# ---------------------------------------------------------------------------
# 9. HasRtbRequesterGateway condition uses simple equals logic
# ---------------------------------------------------------------------------
class TestHasRtbRequesterGatewayConditionLogic:
    def test_condition_uses_equals_logic(self, template_json):
        """HasRtbRequesterGateway = EnableRtbRequesterGateway=='true'."""
        conditions = template_json.get("Conditions", {})
        assert "HasRtbRequesterGateway" in conditions

        condition_expr = conditions["HasRtbRequesterGateway"]
        # Should be Fn::Equals with EnableRtbRequesterGateway == "true"
        assert "Fn::Equals" in condition_expr, (
            f"Expected Fn::Equals in HasRtbRequesterGateway, got: {condition_expr}"
        )
        equals_args = condition_expr["Fn::Equals"]
        assert {"Ref": "EnableRtbRequesterGateway"} in equals_args
        assert "true" in equals_args


# ---------------------------------------------------------------------------
# 10. HasSimulatorFabricLink condition is removed
# ---------------------------------------------------------------------------
class TestHasSimulatorFabricLinkRemoved:
    def test_condition_does_not_exist(self, template_json):
        """HasSimulatorFabricLink condition is no longer in the template."""
        conditions = template_json.get("Conditions", {})
        assert "HasSimulatorFabricLink" not in conditions


# ---------------------------------------------------------------------------
# 11. SimulatorResponderGatewayId parameter is removed
# ---------------------------------------------------------------------------
class TestSimulatorResponderGatewayIdRemoved:
    def test_parameter_does_not_exist(self, template_json):
        """SimulatorResponderGatewayId parameter is no longer in the template."""
        parameters = template_json.get("Parameters", {})
        assert "SimulatorResponderGatewayId" not in parameters
