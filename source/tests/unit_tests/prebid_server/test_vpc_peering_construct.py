# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

# ###############################################################################
# PURPOSE:
#   * Unit test for VpcPeeringConstruct.
#   * Tests UseVpcPeering CfnCondition gating on all resources and outputs.
# USAGE:
#   cd source && python -m pytest tests/unit_tests/prebid_server/test_vpc_peering_construct.py -v
###############################################################################

import pytest
import aws_cdk as cdk
from aws_cdk import Stack, aws_ec2 as ec2
from aws_cdk.assertions import Template, Match
from prebid_server.vpc_peering_construct import VpcPeeringConstruct
from prebid_server.stack_cfn_parameters import StackParams


class MinimalVpcPeeringStack(Stack):
    """Minimal stack that instantiates VPC + VpcPeeringConstruct for testing."""

    def __init__(self, scope, id, **kwargs):
        super().__init__(scope, id, **kwargs)

        # Minimal VPC satisfying VpcPeeringConstruct requirements
        vpc = ec2.Vpc(self, "TestVpc", max_azs=2,
                      ip_addresses=ec2.IpAddresses.cidr("10.8.0.0/16"),
                      subnet_configuration=[
                          ec2.SubnetConfiguration(
                              subnet_type=ec2.SubnetType.PUBLIC,
                              name="Public",
                              cidr_mask=20,
                          ),
                          ec2.SubnetConfiguration(
                              subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                              name="Private",
                              cidr_mask=20,
                          ),
                      ])
        vpc_construct = type("obj", (object,), {"prebid_vpc": vpc})()

        # StackParams needs solutions_template_options on the stack
        self.solutions_template_options = type(
            "obj", (object,), {"add_parameter": lambda self, *a, **kw: None}
        )()
        stack_params = StackParams(self)

        # Instantiate the construct under test
        VpcPeeringConstruct(self, "VpcPeering", vpc_construct, stack_params)


@pytest.fixture(scope="module")
def template():
    """Synthesize the minimal stack and return a Template for assertions."""
    app = cdk.App(
        context={
            "SOLUTION_ID": "SO0248",
            "SOLUTION_VERSION": "v1.0.0",
        }
    )
    stack = MinimalVpcPeeringStack(app, "TestVpcPeeringStack")
    return Template.from_stack(stack)


@pytest.fixture(scope="module")
def template_json(template):
    """Raw JSON of the synthesized template for direct inspection."""
    return template.to_json()


# ---------------------------------------------------------------------------
# 1. VPC Peering Connection has UseVpcPeering condition
# ---------------------------------------------------------------------------
class TestVpcPeeringConnectionCondition:
    def test_peering_connection_has_condition(self, template):
        """VPC peering connection is gated by UseVpcPeering."""
        template.has_resource("AWS::EC2::VPCPeeringConnection", {
            "Condition": "UseVpcPeering",
        })

    def test_peering_connection_count(self, template):
        """Exactly one VPC peering connection exists."""
        template.resource_count_is("AWS::EC2::VPCPeeringConnection", 1)


# ---------------------------------------------------------------------------
# 2. Routes in both VPCs have UseVpcPeering condition
# ---------------------------------------------------------------------------
class TestRoutesHaveCondition:
    def test_all_routes_have_condition(self, template_json):
        """All CfnRoute resources created by VpcPeeringConstruct have UseVpcPeering condition."""
        resources = template_json["Resources"]
        peering_routes = []
        for logical_id, resource in resources.items():
            if (
                resource.get("Type") == "AWS::EC2::Route"
                and "VpcPeering" in logical_id
            ):
                peering_routes.append((logical_id, resource))

        # Should have routes for Prebid VPC private subnets (2) + Bidder VPC route tables (2)
        assert len(peering_routes) >= 4, (
            f"Expected at least 4 peering routes, found {len(peering_routes)}: "
            f"{[r[0] for r in peering_routes]}"
        )

        for logical_id, resource in peering_routes:
            assert resource.get("Condition") == "UseVpcPeering", (
                f"Route {logical_id} should have UseVpcPeering condition"
            )

    def test_prebid_to_bidder_routes_exist(self, template_json):
        """Routes from Prebid VPC to Bidder VPC CIDR (10.1.0.0/16) exist."""
        resources = template_json["Resources"]
        prebid_to_bidder = [
            r for _, r in resources.items()
            if r.get("Type") == "AWS::EC2::Route"
            and r.get("Properties", {}).get("DestinationCidrBlock") == "10.1.0.0/16"
        ]
        assert len(prebid_to_bidder) >= 2, (
            f"Expected at least 2 routes to 10.1.0.0/16, found {len(prebid_to_bidder)}"
        )

    def test_bidder_to_prebid_routes_exist(self, template_json):
        """Routes from Bidder VPC to Prebid VPC CIDR (10.8.0.0/16) exist."""
        resources = template_json["Resources"]
        bidder_to_prebid = [
            r for _, r in resources.items()
            if r.get("Type") == "AWS::EC2::Route"
            and r.get("Properties", {}).get("DestinationCidrBlock") == "10.8.0.0/16"
        ]
        assert len(bidder_to_prebid) == 2, (
            f"Expected 2 routes to 10.8.0.0/16, found {len(bidder_to_prebid)}"
        )


# ---------------------------------------------------------------------------
# 3. Security group ingress has UseVpcPeering condition
# ---------------------------------------------------------------------------
class TestSecurityGroupIngressCondition:
    def test_sg_ingress_has_condition(self, template):
        """Security group ingress for ALB from Prebid VPC is gated by UseVpcPeering."""
        template.has_resource("AWS::EC2::SecurityGroupIngress", {
            "Condition": "UseVpcPeering",
            "Properties": {
                "IpProtocol": "tcp",
                "FromPort": 80,
                "ToPort": 80,
                "CidrIp": "10.8.0.0/16",
            },
        })

    def test_sg_ingress_description(self, template):
        """Security group ingress has descriptive text about VPC peering."""
        template.has_resource_properties("AWS::EC2::SecurityGroupIngress", {
            "Description": Match.string_like_regexp(".*Prebid Server VPC.*peering.*"),
        })


# ---------------------------------------------------------------------------
# 4. Output has UseVpcPeering condition
# ---------------------------------------------------------------------------
class TestOutputCondition:
    def test_vpc_peering_connection_id_output_has_condition(self, template_json):
        """VpcPeeringConnectionId output is gated by UseVpcPeering."""
        outputs = template_json.get("Outputs", {})
        assert "VpcPeeringConnectionId" in outputs
        assert outputs["VpcPeeringConnectionId"].get("Condition") == "UseVpcPeering"


# ---------------------------------------------------------------------------
# 5. UseVpcPeering condition is properly defined
# ---------------------------------------------------------------------------
class TestUseVpcPeeringConditionDefinition:
    def test_condition_exists(self, template_json):
        """UseVpcPeering condition is defined in the template."""
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
