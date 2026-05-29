# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import prebid_server.stack_constants as stack_constants
from aws_cdk import (
    CfnParameter,
    CfnCondition,
    Fn
)

# Constants
ECS_AUTOSCALING_GROUP_NAME = "ECS Service Autoscaling Settings"
CDN_GROUP_NAME = "Content Delivery Network (CDN) Settings"
CONTAINER_GROUP_NAME = "Container Settings"
LOG_ANALYTICS_GROUP_NAME = "Log Analytics Settings"
RTB_FABRIC_GROUP_NAME = "RTB Fabric Settings"
VPC_PEERING_GROUP_NAME = "VPC Peering Settings (Fallback)"

class StackParams:
    def __init__(self, stack) -> None:
        self.deploy_cloudfront_and_waf_param = CfnParameter(
            stack,
            id="InstallCloudFrontAndWAF",
            description="Yes - Use the CloudFront and Web Application Firewall to deliver your content. \n No - Skip CloudFront and WAF deployment and use your own content delivery network instead",
            type="String",
            allowed_values=["Yes", "No"],
            default="Yes"
        )

        self.ssl_certificate_param = CfnParameter(
            stack,
            id="SSLCertificateARN",
            description="The ARN of an SSL certificate in AWS Certificate Manager associated with a domain name. This field is only required if InstallCloudFrontAndWAF is set to \"No\".",
            type="String",
            default="",
            allowed_pattern="^$|^arn:aws:acm:[a-z0-9-]+:[0-9]{12}:certificate/[a-zA-Z0-9-]+$",
            constraint_description="Must be a valid ACM certificate ARN or empty if using CloudFront"
        )

        stack.solutions_template_options.add_parameter(
            self.deploy_cloudfront_and_waf_param, label="InstallCloudFrontAndWAF",
            group=CDN_GROUP_NAME)
        stack.solutions_template_options.add_parameter(
            self.ssl_certificate_param, label="SSLCertificateARN",
            group=CDN_GROUP_NAME)

        self.ecs_task_min_capacity = CfnParameter(
            stack,
            id="ECSTaskMinCapacity",
            description="The minimum number of tasks to run for the Prebid Server ECS service",
            type="Number",
            default=stack_constants.TASK_MIN_CAPACITY,
            min_value=1,
            constraint_description="Minimum capacity must be at least 1 task"
        )

        self.ecs_task_max_capacity = CfnParameter(
            stack,
            id="ECSTaskMaxCapacity",
            description="The maximum number of tasks to run for the Prebid Server ECS service",
            type="Number",
            default=stack_constants.TASK_MAX_CAPACITY,
            min_value=1,
            constraint_description="Maximum capacity must be at least 1 task"
        )

        self.request_count_threshold = CfnParameter(
            stack,
            id="RequestsPerTargetThreshold",
            description="The number of requests per target to trigger scaling up the Prebid Server ECS service",
            type="Number",
            default=stack_constants.REQUESTS_PER_TARGET_THRESHOLD,
            min_value=100,
            max_value=10000,
            constraint_description="Requests per target threshold must be between 100 and 10000"
        )

        self.spot_instance_weight = CfnParameter(
            stack,
            id="SpotInstanceWeight",
            description="Spot instance weight configuration (On-demand weight fixed at 1). Default Spot weight is 1, adjustable as needed",
            type="Number",
            default=stack_constants.SPOT_INSTANCE_WEIGHT,
            min_value=0,
            constraint_description="Spot instance weight must be a non-negative number"
        )

        stack.solutions_template_options.add_parameter(
            self.ecs_task_min_capacity, label="ECSTaskMinCapacity",
            group=ECS_AUTOSCALING_GROUP_NAME)
        stack.solutions_template_options.add_parameter(
            self.ecs_task_max_capacity, label="ECSTaskMaxCapacity",
            group=ECS_AUTOSCALING_GROUP_NAME)
        stack.solutions_template_options.add_parameter(
            self.request_count_threshold, label="RequestsPerTargetThreshold",
            group=ECS_AUTOSCALING_GROUP_NAME)
        stack.solutions_template_options.add_parameter(
            self.spot_instance_weight, label="SpotInstanceWeight",
            group=ECS_AUTOSCALING_GROUP_NAME)

        # --- Container Settings ---
        self.container_image_param = CfnParameter(
            stack,
            id="ContainerImageUri",
            description="ECR image URI for the Prebid Server container. Leave empty to build from source (CDK deployment path). Required when deploying via synthesized CloudFormation template.",
            type="String",
            default=""
        )

        stack.solutions_template_options.add_parameter(
            self.container_image_param, label="ContainerImageUri",
            group=CONTAINER_GROUP_NAME)

        # --- Log Analytics Settings ---
        self.enable_log_analytics_param = CfnParameter(
            stack,
            id="EnableLogAnalytics",
            description="Enable log analytics for Prebid Server auction data (EFS → DataSync → S3 → Glue ETL → Athena)",
            type="String",
            allowed_values=["true", "false"],
            default="false"
        )

        stack.solutions_template_options.add_parameter(
            self.enable_log_analytics_param, label="EnableLogAnalytics",
            group=LOG_ANALYTICS_GROUP_NAME)

        # --- RTB Fabric Settings ---
        self.enable_rtb_requester_gateway_param = CfnParameter(
            stack,
            id="EnableRtbRequesterGateway",
            description="Create an RTB Fabric Requester Gateway for partner connectivity. Set to 'true' to provision the gateway. Fabric Link lifecycle is managed by the simulator-fabric-link.sh script.",
            type="String",
            allowed_values=["true", "false"],
            default="false"
        )

        stack.solutions_template_options.add_parameter(
            self.enable_rtb_requester_gateway_param, label="EnableRtbRequesterGateway",
            group=RTB_FABRIC_GROUP_NAME)

        # --- VPC Peering Settings (Fallback) ---
        self.simulator_vpc_id_param = CfnParameter(
            stack,
            id="SimulatorVpcId",
            description="The VPC ID of the BidderSimulatorStack. Required for VPC peering connectivity (fallback when RTB Fabric is not available).",
            type="String",
            default=""
        )

        self.simulator_alb_sg_id_param = CfnParameter(
            stack,
            id="SimulatorAlbSgId",
            description="The ALB Security Group ID from the BidderSimulatorStack. Used to allow traffic from PrebidServerStack VPC over VPC peering.",
            type="String",
            default=""
        )

        self.simulator_route_table_id_1_param = CfnParameter(
            stack,
            id="SimulatorRouteTableId1",
            description="First private subnet route table ID from the BidderSimulatorStack VPC. Used for return traffic routing over VPC peering.",
            type="String",
            default=""
        )

        self.simulator_route_table_id_2_param = CfnParameter(
            stack,
            id="SimulatorRouteTableId2",
            description="Second private subnet route table ID from the BidderSimulatorStack VPC. Used for return traffic routing over VPC peering.",
            type="String",
            default=""
        )

        self.simulator_endpoint_param = CfnParameter(
            stack,
            id="SimulatorEndpoint",
            description="The bidder simulator's internal ALB DNS name. Used as the ECS bidder endpoint when VPC peering is the connectivity model.",
            type="String",
            default=""
        )

        stack.solutions_template_options.add_parameter(
            self.simulator_vpc_id_param, label="SimulatorVpcId",
            group=VPC_PEERING_GROUP_NAME)
        stack.solutions_template_options.add_parameter(
            self.simulator_alb_sg_id_param, label="SimulatorAlbSgId",
            group=VPC_PEERING_GROUP_NAME)
        stack.solutions_template_options.add_parameter(
            self.simulator_route_table_id_1_param, label="SimulatorRouteTableId1",
            group=VPC_PEERING_GROUP_NAME)
        stack.solutions_template_options.add_parameter(
            self.simulator_route_table_id_2_param, label="SimulatorRouteTableId2",
            group=VPC_PEERING_GROUP_NAME)
        stack.solutions_template_options.add_parameter(
            self.simulator_endpoint_param, label="SimulatorEndpoint",
            group=VPC_PEERING_GROUP_NAME)

        # --- CfnConditions ---
        # HasRtbRequesterGateway: EnableRtbRequesterGateway == "true"
        self.has_rtb_requester_gateway = CfnCondition(
            stack,
            "HasRtbRequesterGateway",
            expression=Fn.condition_equals(self.enable_rtb_requester_gateway_param.value_as_string, "true")
        )

        # UseVpcPeering: SimulatorVpcId != ""
        self.use_vpc_peering = CfnCondition(
            stack,
            "UseVpcPeering",
            expression=Fn.condition_not(Fn.condition_equals(self.simulator_vpc_id_param.value_as_string, ""))
        )

        # HasSimulatorEndpoint: SimulatorEndpoint != ""
        self.has_simulator_endpoint = CfnCondition(
            stack,
            "HasSimulatorEndpoint",
            expression=Fn.condition_not(Fn.condition_equals(self.simulator_endpoint_param.value_as_string, ""))
        )
            
    def validate_parameters(self):
        """
        Validate parameters at runtime before deployment.
        """
        # Check if CloudFront is not used, then SSL certificate must be provided
        if self.deploy_cloudfront_and_waf_param.default == "No" and not self.ssl_certificate_param.default:
            raise ValueError("SSL Certificate ARN is required when CloudFront and WAF are not installed")
