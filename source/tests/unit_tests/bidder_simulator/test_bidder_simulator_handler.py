# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import json
import os
import sys
import pytest
from unittest.mock import patch

# Add the handler to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../loadtest/bidder_simulator/lambdas/loadtest_bidder"))

from handler import parse_bid_request, build_dynamic_response, replace_urls_with_cloudfront


class TestParseBidRequest:
    def test_valid_json_body(self):
        event = {"body": json.dumps({"id": "req-1", "imp": []})}
        result = parse_bid_request(event)
        assert result["id"] == "req-1"

    def test_empty_body(self):
        assert parse_bid_request({"body": ""}) is None

    def test_missing_body(self):
        assert parse_bid_request({}) is None

    def test_invalid_json(self):
        assert parse_bid_request({"body": "not json"}) is None


class TestBuildDynamicResponse:
    def test_banner_imp(self):
        request = {
            "id": "test-1",
            "imp": [{"id": "banner_imp_1", "banner": {"w": 300, "h": 250}}]
        }
        resp = build_dynamic_response(request)
        assert resp["id"] == "test-1"
        assert len(resp["seatbid"]) == 1
        bids = resp["seatbid"][0]["bid"]
        assert len(bids) == 1
        assert bids[0]["impid"] == "banner_imp_1"
        assert "dur" not in bids[0]  # banner bids should not have dur

    def test_video_imp_includes_dur(self):
        request = {
            "id": "test-2",
            "imp": [{
                "id": "video_imp_1",
                "video": {"mimes": ["video/mp4"], "minduration": 5, "maxduration": 30}
            }]
        }
        resp = build_dynamic_response(request)
        bids = resp["seatbid"][0]["bid"]
        assert len(bids) == 1
        assert bids[0]["impid"] == "video_imp_1"
        assert "dur" in bids[0]
        assert 5 <= bids[0]["dur"] <= 30

    def test_mixed_banner_and_video(self):
        request = {
            "id": "test-3",
            "imp": [
                {"id": "b1", "banner": {"w": 300, "h": 250}},
                {"id": "v1", "video": {"mimes": ["video/mp4"], "minduration": 5, "maxduration": 30}},
                {"id": "b2", "banner": {"w": 728, "h": 90}},
            ]
        }
        resp = build_dynamic_response(request)
        bids = resp["seatbid"][0]["bid"]
        assert len(bids) == 3
        imp_ids = [b["impid"] for b in bids]
        assert imp_ids == ["b1", "v1", "b2"]
        # Only video bid should have dur
        assert "dur" not in bids[0]
        assert "dur" in bids[1]
        assert "dur" not in bids[2]

    def test_echoes_request_id(self):
        request = {"id": "my-unique-id", "imp": [{"id": "imp1", "banner": {"w": 300, "h": 250}}]}
        resp = build_dynamic_response(request)
        assert resp["id"] == "my-unique-id"

    def test_empty_imps(self):
        request = {"id": "test-empty", "imp": []}
        resp = build_dynamic_response(request)
        assert resp["seatbid"] == []

    def test_video_dur_clamped_to_maxduration(self):
        """When creative dur exceeds maxduration, it should clamp to maxduration."""
        request = {
            "id": "test-clamp",
            "imp": [{
                "id": "v1",
                "video": {"mimes": ["video/mp4"], "minduration": 1, "maxduration": 3}
            }]
        }
        resp = build_dynamic_response(request)
        bid = resp["seatbid"][0]["bid"][0]
        assert bid["dur"] <= 3

    def test_multiple_video_imps_cycle_creatives(self):
        """Multiple video imps should cycle through different creatives."""
        request = {
            "id": "test-cycle",
            "imp": [
                {"id": "v1", "video": {"mimes": ["video/mp4"], "minduration": 5, "maxduration": 60}},
                {"id": "v2", "video": {"mimes": ["video/mp4"], "minduration": 5, "maxduration": 60}},
                {"id": "v3", "video": {"mimes": ["video/mp4"], "minduration": 5, "maxduration": 60}},
            ]
        }
        resp = build_dynamic_response(request)
        bids = resp["seatbid"][0]["bid"]
        crids = [b["crid"] for b in bids]
        # Should cycle through the 3 video creatives
        assert len(set(crids)) == 3


class TestReplaceUrlsWithCloudfront:
    def test_replaces_asset_urls(self):
        bid_response = {
            "seatbid": [{"bid": [{
                "adm": "<img src=\"/assets/banners/test.jpg\">"
            }]}]
        }
        result = replace_urls_with_cloudfront(bid_response, "d123.cloudfront.net")
        assert "https://d123.cloudfront.net/assets/banners/test.jpg" in result["seatbid"][0]["bid"][0]["adm"]

    def test_replaces_cdata_urls(self):
        bid_response = {
            "seatbid": [{"bid": [{
                "adm": "<![CDATA[/assets/videos/test.mp4]]>"
            }]}]
        }
        result = replace_urls_with_cloudfront(bid_response, "d123.cloudfront.net")
        assert "https://d123.cloudfront.net/assets/videos/test.mp4" in result["seatbid"][0]["bid"][0]["adm"]

    def test_no_replacement_without_assets(self):
        bid_response = {"seatbid": [{"bid": [{"adm": "no urls here"}]}]}
        result = replace_urls_with_cloudfront(bid_response, "d123.cloudfront.net")
        assert result["seatbid"][0]["bid"][0]["adm"] == "no urls here"
