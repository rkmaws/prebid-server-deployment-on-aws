# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

from aws_cdk import (
    Aws,
    CfnOutput,
    CfnTag,
    CustomResource,
    Duration,
    aws_ec2 as ec2,
    aws_lambda as awslambda,
    aws_rtbfabric as rtbfabric,
)
from constructs import Construct
from aws_lambda_layers.aws_solutions.layer import SolutionsLayer
from aws_solutions.cdk.aws_lambda.layers.aws_lambda_powertools import PowertoolsLayer
from aws_solutions.cdk.aws_lambda.python.function import SolutionsPythonFunction
import prebid_server.stack_constants as stack_constants

from .vpc_construct import VpcConstruct


class RtbFabricConstruct(Construct):
    """
    Creates RTB Fabric Requester Gateway with a WaitForGateway readiness check.

    Resources are gated by CfnConditions from StackParams:
    - Requester Gateway: created when HasRtbRequesterGateway is true
      (EnableRtbRequesterGateway=true)

    A WaitForGateway custom resource ensures the gateway is fully provisioned
    before any downstream operations (e.g., Fabric Link creation via script).

    Fabric Link lifecycle is managed externally by simulator-fabric-link.sh.
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
        self._create_requester_gateway(vpc_construct)
        self._create_wait_for_gateway()

    def _create_requester_gateway(self, vpc_construct: VpcConstruct) -> None:
        """
        Create RTB Fabric Requester Gateway (conditional on HasRtbRequesterGateway).

        Gateway Configuration:
        - Attached to PBS VPC
        - Configured for IPv4 traffic only (HTTPS on port 443)
        - Security group allows HTTPS (443) from PBS application
        """
        # Create security group for Requester Gateway
        self.requester_gateway_security_group = ec2.SecurityGroup(
            self,
            "RequesterGatewaySecurityGroup",
            vpc=vpc_construct.prebid_vpc,
            description="Security group for RTB Fabric Requester Gateway",
            allow_all_outbound=True,
        )

        # Attach condition to the L1 security group resource
        sg_l1 = self.requester_gateway_security_group.node.default_child
        sg_l1.cfn_options.condition = self.stack_params.has_rtb_requester_gateway

        # Allow HTTPS (443) from PBS application
        self.requester_gateway_security_group.add_ingress_rule(
            peer=ec2.Peer.ipv4(vpc_construct.prebid_vpc.vpc_cidr_block),
            connection=ec2.Port.tcp(443),
            description="Allow HTTPS from PBS application",
        )

        # Get private subnets for gateway attachment
        private_subnets = vpc_construct.prebid_vpc.select_subnets(
            subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
        )

        # Create RTB Fabric Requester Gateway
        self.requester_gateway = rtbfabric.CfnRequesterGateway(
            self,
            "RequesterGateway",
            vpc_id=vpc_construct.prebid_vpc.vpc_id,
            subnet_ids=[private_subnets.subnets[0].subnet_id],
            security_group_ids=[self.requester_gateway_security_group.security_group_id],
            description="RTB Fabric Requester Gateway for PBS",
            tags=[CfnTag(key="Name", value=f"{Aws.STACK_NAME}-PBS-RequesterGateway")],
        )
        self.requester_gateway.cfn_options.condition = self.stack_params.has_rtb_requester_gateway

        requester_gw_id_output = CfnOutput(
            self,
            "RequesterGatewayId",
            key="RequesterGatewayId",
            value=self.requester_gateway.attr_gateway_id,
            description="RTB Fabric Requester Gateway ID",
        )
        requester_gw_id_output.condition = self.stack_params.has_rtb_requester_gateway

        requester_gw_arn_output = CfnOutput(
            self,
            "RequesterGatewayArn",
            key="RequesterGatewayArn",
            value=self.requester_gateway.attr_arn,
            description="RTB Fabric Requester Gateway ARN",
        )
        requester_gw_arn_output.condition = self.stack_params.has_rtb_requester_gateway

    def _create_wait_for_gateway(self) -> None:
        """
        Create WaitForGateway custom resource (conditional on HasRtbRequesterGateway).

        Ensures the Requester Gateway is fully provisioned before any downstream
        operations (e.g., Fabric Link creation via simulator-fabric-link.sh script).

        CloudFormation reports CREATE_COMPLETE before RTB Fabric finishes internal
        provisioning, which causes a 409 "not ready" error on Link creation.
        """
        wait_for_gw_function = SolutionsPythonFunction(
            self,
            "WaitForGatewayFunction",
            stack_constants.CUSTOM_RESOURCES_PATH
            / "wait_for_gateway_lambda"
            / "wait_for_gateway.py",
            "event_handler",
            runtime=awslambda.Runtime.PYTHON_3_11,
            description="Wait for RTB Fabric Gateway to be fully provisioned",
            timeout=Duration.seconds(60),
            memory_size=128,
            architecture=awslambda.Architecture.ARM_64,
            layers=[
                PowertoolsLayer.get_or_create(self),
                SolutionsLayer.get_or_create(self),
            ],
            environment={
                "SOLUTION_ID": self.node.try_get_context("SOLUTION_ID"),
                "SOLUTION_VERSION": self.node.try_get_context("SOLUTION_VERSION"),
            }
        )

        # Suppress cfn_guard rules — this function does not need VPC access or reserved concurrency.
        wait_for_gw_function.node.find_child(id='Resource').add_metadata("guard", {
            'SuppressedRules': ['LAMBDA_INSIDE_VPC', 'LAMBDA_CONCURRENCY_CHECK']
        })

        # Gate the Lambda with the condition
        wait_for_gw_function.node.default_child.cfn_options.condition = self.stack_params.has_rtb_requester_gateway
        # Gate the IAM role and policy
        wait_for_gw_role = wait_for_gw_function.role.node.default_child
        wait_for_gw_role.cfn_options.condition = self.stack_params.has_rtb_requester_gateway

        wait_for_gw_cr = CustomResource(
            self,
            "WaitForRequesterGatewayCr",
            service_token=wait_for_gw_function.function_arn,
            properties={
                "GatewayId": self.requester_gateway.attr_gateway_id,
            }
        )
        wait_for_gw_cr.node.add_dependency(self.requester_gateway)

        # Gate the custom resource with the condition
        wait_for_gw_cr.node.default_child.cfn_options.condition = self.stack_params.has_rtb_requester_gateway
