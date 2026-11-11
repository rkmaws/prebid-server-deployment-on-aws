# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

from aws_cdk import (
    Aws,
    CfnOutput,
    Tags,
    aws_ec2 as ec2,
)
from constructs import Construct

from .vpc_construct import VpcConstruct


class VpcPeeringConstruct(Construct):
    """
    Creates a VPC peering connection between Prebid Server and Bidder Simulator VPCs.

    All resources are gated by the UseVpcPeering CfnCondition from StackParams:
    - UseVpcPeering is true when SimulatorVpcId != "" AND SimulatorResponderGatewayId == ""
    - When RTB Fabric is available (SimulatorResponderGatewayId provided), VPC peering is skipped

    VPC Peering Configuration:
    - Automatically accepted (both VPCs in same account)
    - Routes added in BOTH VPCs
    - Bidder Simulator ALB security group updated to allow HTTP from Prebid Server VPC CIDR
    """

    def __init__(
        self,
        scope: Construct,
        id: str,
        vpc_construct: VpcConstruct,
        stack_params,
    ) -> None:
        super().__init__(scope, id)

        self.stack_params = stack_params
        condition = stack_params.use_vpc_peering

        # Create VPC peering connection
        self.vpc_peering_connection = ec2.CfnVPCPeeringConnection(
            self,
            "PrebidServerVpcPeering",
            peer_vpc_id=stack_params.simulator_vpc_id_param.value_as_string,
            vpc_id=vpc_construct.prebid_vpc.vpc_id,
        )
        self.vpc_peering_connection.cfn_options.condition = condition
        Tags.of(self.vpc_peering_connection).add("Name", f"{Aws.STACK_NAME}-PrebidServer-VpcPeering")

        # Add routes in Prebid Server VPC private subnets
        # Route Bidder Simulator VPC CIDR (10.1.0.0/16) to the peering connection
        private_subnets = vpc_construct.prebid_vpc.select_subnets(
            subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
        )

        for i, subnet in enumerate(private_subnets.subnets):
            route = ec2.CfnRoute(
                self,
                f"PrebidToBidderRoute{i}",
                route_table_id=subnet.route_table.route_table_id,
                destination_cidr_block="10.1.0.0/16",  # Bidder Simulator VPC CIDR
                vpc_peering_connection_id=self.vpc_peering_connection.ref,
            )
            route.cfn_options.condition = condition

        # Add routes in Bidder Simulator VPC using the two route table ID parameters
        route_1 = ec2.CfnRoute(
            self,
            "BidderToPrebidRoute0",
            route_table_id=stack_params.simulator_route_table_id_1_param.value_as_string,
            destination_cidr_block="10.8.0.0/16",  # Prebid Server VPC CIDR
            vpc_peering_connection_id=self.vpc_peering_connection.ref,
        )
        route_1.cfn_options.condition = condition

        route_2 = ec2.CfnRoute(
            self,
            "BidderToPrebidRoute1",
            route_table_id=stack_params.simulator_route_table_id_2_param.value_as_string,
            destination_cidr_block="10.8.0.0/16",  # Prebid Server VPC CIDR
            vpc_peering_connection_id=self.vpc_peering_connection.ref,
        )
        route_2.cfn_options.condition = condition

        # Update Bidder Simulator ALB security group to allow HTTP from Prebid Server VPC CIDR
        sg_ingress = ec2.CfnSecurityGroupIngress(
            self,
            "BidderAlbIngressFromPrebid",
            group_id=stack_params.simulator_alb_sg_id_param.value_as_string,
            ip_protocol="tcp",
            from_port=80,
            to_port=80,
            cidr_ip="10.8.0.0/16",  # Prebid Server VPC CIDR
            description="Allow HTTP from Prebid Server VPC via peering",
        )
        sg_ingress.cfn_options.condition = condition

        # Output VPC peering connection ID for reference
        peering_output = CfnOutput(
            self,
            "VpcPeeringConnectionId",
            key="VpcPeeringConnectionId",
            value=self.vpc_peering_connection.ref,
            description="VPC Peering Connection ID between Prebid Server and Bidder Simulator VPCs",
        )
        peering_output.condition = condition
