#!/usr/bin/env python3
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Test script for sending full OpenRTB 2.x requests to Prebid Server.

Both request types hit /openrtb2/auction with inline imp objects:
  - banner+outstream: Banner display + outstream video impressions
  - instream:         Preroll + midroll instream video impressions

Usage:
    python test-auction-amt.py --endpoint <url> --type banner+outstream
    python test-auction-amt.py --endpoint <url> --type instream
    python test-auction-amt.py --endpoint <url> --type all
    python test-auction-amt.py --endpoint <url> --type all --verbose
    python test-auction-amt.py --endpoint <url> --type banner+outstream --request-file custom.json
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Any, Optional
import requests


SCRIPT_DIR = Path(__file__).parent

DEFAULT_REQUEST_FILES = {
    "banner+outstream": SCRIPT_DIR / "openrtb2-banner-outstream-request.json",
    "instream": SCRIPT_DIR / "openrtb2-instream-video-request.json",
    "video-endpoint": SCRIPT_DIR / "openrtb2-video-endpoint-request.json",
}


class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    END = '\033[0m'


# ---------------------------------------------------------------------------
# Request loading
# ---------------------------------------------------------------------------

def load_request(request_type: str, custom_file: Optional[str] = None, quiet: bool = False) -> Dict[str, Any]:
    """Load an OpenRTB request payload from a JSON file."""
    if custom_file:
        file_path = Path(custom_file)
    else:
        file_path = DEFAULT_REQUEST_FILES.get(request_type)
        if not file_path:
            print(f"{Colors.RED}Unknown request type: {request_type}{Colors.END}")
            sys.exit(1)

    if not file_path.exists():
        print(f"{Colors.RED}Request file not found: {file_path}{Colors.END}")
        sys.exit(1)

    with open(file_path, "r") as f:
        data = json.load(f)

    if not quiet:
        print(f"{Colors.GREEN}✓{Colors.END} Loaded request from: {file_path.name}")
    return data


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def normalize_endpoint(endpoint: str) -> str:
    if not endpoint.startswith(("http://", "https://")):
        endpoint = f"https://{endpoint}"
    return endpoint.rstrip("/")


def send_request(url: str, payload: Dict[str, Any], verbose: bool = False) -> requests.Response:
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if verbose:
        print(f"\n{Colors.BLUE}=== REQUEST ==={Colors.END}")
        print(f"POST {url}")
        print(json.dumps(payload, indent=2))
    try:
        return requests.post(url, json=payload, headers=headers, timeout=15)
    except requests.exceptions.RequestException as e:
        print(f"{Colors.RED}Request failed: {e}{Colors.END}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Response validation
# ---------------------------------------------------------------------------

def validate_auction_response(resp: requests.Response, verbose: bool = False) -> bool:
    """Validate /openrtb2/auction response."""
    ok = True
    print(f"\n{Colors.BLUE}=== RESPONSE ({resp.status_code}) ==={Colors.END}")

    if resp.status_code != 200:
        print(f"{Colors.RED}✗ HTTP {resp.status_code}{Colors.END}")
        print(resp.text[:2000])
        return False

    try:
        data = resp.json()
    except json.JSONDecodeError:
        print(f"{Colors.RED}✗ Invalid JSON{Colors.END}")
        return False

    if verbose:
        print(json.dumps(data, indent=2))

    for field in ("id", "seatbid", "cur"):
        if field in data:
            print(f"{Colors.GREEN}✓{Colors.END} {field} present")
        else:
            print(f"{Colors.RED}✗{Colors.END} {field} missing")
            ok = False

    seatbids = data.get("seatbid", [])
    if seatbids:
        print(f"{Colors.GREEN}✓{Colors.END} {len(seatbids)} seat(s) returned")
        for sb in seatbids:
            seat = sb.get("seat", "?")
            bids = sb.get("bid", [])
            print(f"  seat={seat}  bids={len(bids)}")
            for b in bids:
                impid = b.get("impid", "?")
                price = b.get("price", 0)
                crid = b.get("crid", "?")
                btype = b.get("ext", {}).get("prebid", {}).get("type", "?")
                print(f"    impid={impid}  price={price}  crid={crid}  type={btype}")
    else:
        print(f"{Colors.YELLOW}! No seatbids (adapter may not be returning bids){Colors.END}")

    ext = data.get("ext", {})
    timing = ext.get("responsetimemillis", {})
    if timing:
        print(f"\n  Response times: {json.dumps(timing)}")

    return ok


def validate_video_response(resp: requests.Response, verbose: bool = False) -> bool:
    """Validate /openrtb2/video response (ad pods with targeting keys)."""
    print(f"\n{Colors.BLUE}=== RESPONSE ({resp.status_code}) ==={Colors.END}")

    if resp.status_code != 200:
        print(f"{Colors.RED}✗ HTTP {resp.status_code}{Colors.END}")
        print(resp.text[:2000])
        return False

    content_type = resp.headers.get("Content-Type", "")

    if "json" in content_type:
        try:
            data = resp.json()
        except json.JSONDecodeError:
            print(f"{Colors.RED}✗ Invalid JSON{Colors.END}")
            return False
        if verbose:
            print(json.dumps(data, indent=2))

        adpods = data.get("adPods", [])
        if adpods:
            print(f"{Colors.GREEN}✓{Colors.END} {len(adpods)} ad pod(s) returned")
            for pod in adpods:
                podid = pod.get("podid", "?")
                targeting = pod.get("targeting", [])
                errors = pod.get("errors", [])
                print(f"  podid={podid}  targeting_keys={len(targeting)}  errors={len(errors)}")
                for t in targeting[:3]:
                    print(f"    hb_pb={t.get('hb_pb', '?')}  hb_cache_id={t.get('hb_cache_id', t.get('hb_uuid', '?'))}")
                for err in errors:
                    print(f"    {Colors.YELLOW}error: {err}{Colors.END}")
        else:
            print(f"{Colors.YELLOW}! No adPods in response{Colors.END}")
            if verbose:
                print(json.dumps(data, indent=2))
        return len(adpods) > 0
    else:
        body = resp.text[:3000]
        if "<VMAP" in body or "<VAST" in body:
            print(f"{Colors.GREEN}✓{Colors.END} Received VMAP/VAST XML response")
            if verbose:
                print(body)
            return True
        else:
            print(f"{Colors.YELLOW}! Unexpected content-type: {content_type}{Colors.END}")
            if verbose:
                print(body)
            return False


# ---------------------------------------------------------------------------
# Test runners
# ---------------------------------------------------------------------------

def run_test(endpoint: str, request_type: str, label: str, verbose: bool,
             custom_file: Optional[str] = None) -> bool:
    print(f"\n{Colors.CYAN}{Colors.BOLD}{'='*60}")
    print(f"  {label}  →  /openrtb2/auction")
    print(f"{'='*60}{Colors.END}")
    url = f"{endpoint}/openrtb2/auction"
    payload = load_request(request_type, custom_file)
    imp_ids = [imp.get("id", "?") for imp in payload.get("imp", [])]
    print(f"Impressions: {', '.join(imp_ids)}")
    resp = send_request(url, payload, verbose)
    return validate_auction_response(resp, verbose)


def run_video_endpoint_test(endpoint: str, verbose: bool,
                            custom_file: Optional[str] = None) -> bool:
    print(f"\n{Colors.CYAN}{Colors.BOLD}{'='*60}")
    print(f"  VIDEO ENDPOINT (pod-based)  →  /openrtb2/video")
    print(f"{'='*60}{Colors.END}")
    url = f"{endpoint}/openrtb2/video"
    payload = load_request("video-endpoint", custom_file)
    pods = payload.get("podconfig", {}).get("pods", [])
    pod_info = [f"pod {p.get('podid','?')} ({p.get('configid','?')}, {p.get('adpoddurationsec','?')}s)" for p in pods]
    print(f"Pods: {', '.join(pod_info)}")
    print(f"{Colors.YELLOW}Note: Requires stored request/impression configs in S3{Colors.END}")
    resp = send_request(url, payload, verbose)
    return validate_video_response(resp, verbose)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Send full OpenRTB 2.x requests to Prebid Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python test-auction-amt.py --endpoint d123.cloudfront.net --type banner+outstream
  python test-auction-amt.py --endpoint d123.cloudfront.net --type instream
  python test-auction-amt.py --endpoint d123.cloudfront.net --type all -v
  python test-auction-amt.py --endpoint d123.cloudfront.net --type banner+outstream --request-file custom.json
        """,
    )
    parser.add_argument("--endpoint", required=True, help="CloudFront or ALB URL")
    parser.add_argument(
        "--type", required=True,
        choices=["banner+outstream", "instream", "video-endpoint", "all"],
        help="Request type to send",
    )
    parser.add_argument("--request-file", help="Custom request JSON file (overrides default for the selected type)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show full payloads/responses")
    parser.add_argument("--dump", action="store_true", help="Print request JSON to stdout and exit (no HTTP call)")
    args = parser.parse_args()

    endpoint = normalize_endpoint(args.endpoint)

    types_to_run = ["banner+outstream", "instream", "video-endpoint"] if args.type == "all" else [args.type]

    if args.dump:
        for t in types_to_run:
            data = load_request(t, args.request_file, quiet=True)
            print(json.dumps(data, indent=2))
        return

    print(f"{Colors.BOLD}OpenRTB 2.x Prebid Server Test{Colors.END}")
    print(f"Endpoint: {endpoint}")

    labels = {
        "banner+outstream": "BANNER + OUTSTREAM",
        "instream": "INSTREAM VIDEO (preroll + midroll)",
    }

    results = {}
    for t in types_to_run:
        if t == "video-endpoint":
            results[t] = run_video_endpoint_test(endpoint, args.verbose, args.request_file)
        else:
            results[t] = run_test(endpoint, t, labels[t], args.verbose, args.request_file)

    print(f"\n{Colors.BOLD}=== SUMMARY ==={Colors.END}")
    all_pass = True
    for name, passed in results.items():
        icon = f"{Colors.GREEN}✓{Colors.END}" if passed else f"{Colors.RED}✗{Colors.END}"
        print(f"  {icon} {name}")
        if not passed:
            all_pass = False

    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
