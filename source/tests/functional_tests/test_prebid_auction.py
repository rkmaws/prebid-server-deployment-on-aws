# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import os
import uuid
import time
import requests
import pytest
from conftest import SKIP_REASON, TEST_REGIONS, logging

logger = logging.getLogger(__name__)

CLOUDFRONT_ENDPOINT = os.environ["CLOUDFRONT_ENDPOINT"]
url = f"https://{CLOUDFRONT_ENDPOINT}/openrtb2/auction"



@pytest.mark.run(order=1)
def test_auction_request():
    random_id = uuid.uuid4().hex

    auction_request = {
        "id": random_id,
        "imp": [
            {
                "id": "banner_imp_1",
                "banner": {"w": 300, "h": 250},
                "ext": {
                    "amt": {
                        "placementId": "placement_1",
                        "bidFloor": 1,
                        "bidCeiling": 100000
                    }
                }
            },
            {
                "id": "banner_imp_2",
                "banner": {"w": 300, "h": 250},
                "ext": {
                    "amt": {
                        "placementId": "placement_2",
                        "bidFloor": 1,
                        "bidCeiling": 50
                    }
                }
            }
        ],
        "device": {
            "pxratio": 4.2,
            "dnt": 2,
            "language": "en",
            "ifa": "ifaId"
        },
        "site": {
            "page": "prebid.org",
            "publisher": {
                "id": "publisherId"
            }
        },
        "at": 1,
        "tmax": 5000,
        "cur": [
            "USD"
        ],
        "source": {
            "fd": 1,
            "tid": "tid"
        },
        "ext": {
            "prebid": {
                "targeting": {
                    "pricegranularity": {
                        "precision": 2,
                        "ranges": [
                            {
                                "max": 20,
                                "increment": 0.1
                            }
                        ]
                    }
                },
                "cache": {
                    "bids": {}
                },
                "auctiontimestamp": 1000
            }
        },
        "regs": {"ext": {"gdpr": 0}}
    }

    time.sleep(5)
    auction_resonse = requests.post(url, json=auction_request)
    logger.info(auction_resonse)
    assert auction_resonse.status_code == 200
    logger.info(auction_resonse.json())

    if (
        os.environ.get("AMT_ADAPTER_ENABLED") and 
        os.environ.get("AMT_BIDDING_SERVER_SIMULATOR_ENDPOINT") and
        os.environ["TEST_AWS_REGION"] in TEST_REGIONS
    ):
        assert auction_resonse.json()["id"] == random_id
        assert auction_resonse.json()["cur"] == "USD"
        assert auction_resonse.json()["seatbid"][0]["bid"][0]["impid"] == "banner_imp_1"
        assert auction_resonse.json()["seatbid"][0]["bid"][1]["impid"] == "banner_imp_2"
        assert auction_resonse.json()["seatbid"][0]["bid"][0]["price"] == 3.25
        assert auction_resonse.json()["seatbid"][0]["bid"][1]["price"] == 2.75
        assert auction_resonse.json()["seatbid"][0]["bid"][0]["crid"] == "banner_creative_1"
        assert auction_resonse.json()["seatbid"][0]["bid"][1]["crid"] == "banner_creative_2"
        assert auction_resonse.json()["seatbid"][0]["seat"] == "amt"

    else:
        logger.info(SKIP_REASON)
        logger.info("Skipping detailed test_auction_request as AMT_ADAPTER_ENABLED or AMT_BIDDING_SERVER_SIMULATOR_ENDPOINT is not set")


@pytest.mark.run(order=2)
def test_outstream_video_auction_request():
    random_id = uuid.uuid4().hex

    auction_request = {
        "id": random_id,
        "imp": [
            {
                "id": "outstream_video_imp_1",
                "video": {
                    "mimes": ["video/mp4"],
                    "protocols": [1, 2, 3, 4, 5, 6, 7, 8],
                    "w": 360,
                    "h": 360,
                    "placement": 3
                },
                "ext": {
                    "amt": {
                        "placementId": "placement_1",
                        "bidFloor": 1,
                        "bidCeiling": 100000
                    }
                }
            }
        ],
        "device": {
            "pxratio": 4.2,
            "dnt": 2,
            "language": "en",
            "ifa": "ifaId"
        },
        "site": {
            "page": "prebid.org",
            "publisher": {
                "id": "publisherId"
            }
        },
        "at": 1,
        "tmax": 5000,
        "cur": ["USD"],
        "source": {
            "fd": 1,
            "tid": "tid"
        },
        "ext": {
            "prebid": {
                "targeting": {
                    "pricegranularity": {
                        "precision": 2,
                        "ranges": [
                            {
                                "max": 20,
                                "increment": 0.1
                            }
                        ]
                    }
                },
                "cache": {
                    "bids": {},
                    "vastxml": {}
                },
                "auctiontimestamp": 1000
            }
        },
        "regs": {"ext": {"gdpr": 0}}
    }

    time.sleep(5)
    auction_resonse = requests.post(url, json=auction_request)
    logger.info(auction_resonse)
    assert auction_resonse.status_code == 200
    logger.info(auction_resonse.json())

    if (
        os.environ.get("AMT_ADAPTER_ENABLED") and
        os.environ.get("AMT_BIDDING_SERVER_SIMULATOR_ENDPOINT") and
        os.environ["TEST_AWS_REGION"] in TEST_REGIONS
    ):
        assert auction_resonse.json()["id"] == random_id
        assert auction_resonse.json()["cur"] == "USD"
        assert auction_resonse.json()["seatbid"][0]["bid"][0]["impid"] == "outstream_video_imp_1"
        assert auction_resonse.json()["seatbid"][0]["bid"][0]["price"] == 12.50
        assert auction_resonse.json()["seatbid"][0]["bid"][0]["crid"] == "video_creative_outstream"
        assert auction_resonse.json()["seatbid"][0]["seat"] == "amt"
        # Verify VAST XML is present in the ad markup
        assert "VAST" in auction_resonse.json()["seatbid"][0]["bid"][0].get("adm", "")

    else:
        logger.info(SKIP_REASON)
        logger.info("Skipping detailed test_outstream_video_auction_request as AMT_ADAPTER_ENABLED or AMT_BIDDING_SERVER_SIMULATOR_ENDPOINT is not set")


@pytest.mark.run(order=3)
def test_instream_video_auction_request():
    random_id = uuid.uuid4().hex

    auction_request = {
        "id": random_id,
        "imp": [
            {
                "id": "instream_video_imp_1",
                "video": {
                    "mimes": ["video/mp4"],
                    "protocols": [1, 2, 3, 4, 5, 6, 7, 8],
                    "w": 640,
                    "h": 480,
                    "playbackmethod": [2],
                    "placement": 1,
                    "skip": 1
                },
                "ext": {
                    "amt": {
                        "placementId": "placement_1",
                        "bidFloor": 1,
                        "bidCeiling": 100000
                    }
                }
            }
        ],
        "device": {
            "pxratio": 4.2,
            "dnt": 2,
            "language": "en",
            "ifa": "ifaId"
        },
        "site": {
            "page": "prebid.org",
            "publisher": {
                "id": "publisherId"
            }
        },
        "at": 1,
        "tmax": 5000,
        "cur": ["USD"],
        "source": {
            "fd": 1,
            "tid": "tid"
        },
        "ext": {
            "prebid": {
                "targeting": {
                    "pricegranularity": {
                        "precision": 2,
                        "ranges": [
                            {
                                "max": 25,
                                "increment": 0.1
                            }
                        ]
                    }
                },
                "cache": {
                    "bids": {},
                    "vastxml": {}
                },
                "auctiontimestamp": 1000
            }
        },
        "regs": {"ext": {"gdpr": 0}}
    }

    time.sleep(5)
    auction_resonse = requests.post(url, json=auction_request)
    logger.info(auction_resonse)
    assert auction_resonse.status_code == 200
    logger.info(auction_resonse.json())

    if (
        os.environ.get("AMT_ADAPTER_ENABLED") and
        os.environ.get("AMT_BIDDING_SERVER_SIMULATOR_ENDPOINT") and
        os.environ["TEST_AWS_REGION"] in TEST_REGIONS
    ):
        assert auction_resonse.json()["id"] == random_id
        assert auction_resonse.json()["cur"] == "USD"
        assert auction_resonse.json()["seatbid"][0]["bid"][0]["impid"] == "instream_video_imp_1"
        assert auction_resonse.json()["seatbid"][0]["bid"][0]["price"] > 0
        assert auction_resonse.json()["seatbid"][0]["seat"] == "amt"
        # Verify VAST XML is present in the ad markup
        assert "VAST" in auction_resonse.json()["seatbid"][0]["bid"][0].get("adm", "")

    else:
        logger.info(SKIP_REASON)
        logger.info("Skipping detailed test_instream_video_auction_request as AMT_ADAPTER_ENABLED or AMT_BIDDING_SERVER_SIMULATOR_ENDPOINT is not set")


@pytest.mark.run(order=4)
def test_instream_preroll_midroll_auction_request():
    """Test instream video with both preroll (startdelay=0) and midroll (startdelay=900) impressions."""
    random_id = uuid.uuid4().hex

    auction_request = {
        "id": random_id,
        "imp": [
            {
                "id": "instream_video_imp_1",
                "video": {
                    "mimes": ["video/mp4", "video/webm"],
                    "protocols": [2, 3, 5, 6],
                    "w": 1920,
                    "h": 1080,
                    "startdelay": 0,
                    "placement": 1,
                    "linearity": 1,
                    "minduration": 5,
                    "maxduration": 30,
                    "skip": 1
                },
                "bidfloor": 5.0,
                "bidfloorcur": "USD",
                "ext": {
                    "prebid": {
                        "bidder": {
                            "amt": {
                                "placementId": "instream-preroll",
                                "bidFloor": 5.0,
                                "bidCeiling": 75.0
                            }
                        }
                    }
                }
            },
            {
                "id": "instream_video_imp_2",
                "video": {
                    "mimes": ["video/mp4", "video/webm"],
                    "protocols": [2, 3, 5, 6],
                    "w": 1920,
                    "h": 1080,
                    "startdelay": 900,
                    "placement": 1,
                    "linearity": 1,
                    "minduration": 15,
                    "maxduration": 60,
                    "skip": 0
                },
                "bidfloor": 8.0,
                "bidfloorcur": "USD",
                "ext": {
                    "prebid": {
                        "bidder": {
                            "amt": {
                                "placementId": "instream-midroll",
                                "bidFloor": 8.0,
                                "bidCeiling": 100.0
                            }
                        }
                    }
                }
            }
        ],
        "site": {
            "page": "video.publisher.example.com",
            "publisher": {"id": "pub-video-001"}
        },
        "at": 1,
        "tmax": 5000,
        "cur": ["USD"],
        "ext": {
            "prebid": {
                "targeting": {
                    "pricegranularity": {
                        "precision": 2,
                        "ranges": [{"max": 50, "increment": 0.5}]
                    }
                },
                "cache": {"bids": {}, "vastxml": {}},
                "auctiontimestamp": 1000
            }
        },
        "regs": {"ext": {"gdpr": 0}}
    }

    time.sleep(5)
    auction_response = requests.post(url, json=auction_request)
    logger.info(auction_response)
    assert auction_response.status_code == 200
    logger.info(auction_response.json())

    if (
        os.environ.get("AMT_ADAPTER_ENABLED") and
        os.environ.get("AMT_BIDDING_SERVER_SIMULATOR_ENDPOINT") and
        os.environ["TEST_AWS_REGION"] in TEST_REGIONS
    ):
        data = auction_response.json()
        assert data["id"] == random_id
        assert data["cur"] == "USD"

        bids = data["seatbid"][0]["bid"]
        imp_ids = {b["impid"] for b in bids}
        assert "instream_video_imp_1" in imp_ids, "Missing preroll bid"
        assert "instream_video_imp_2" in imp_ids, "Missing midroll bid"

        for bid in bids:
            assert "VAST" in bid.get("adm", ""), f"Missing VAST XML in bid {bid['impid']}"
            assert bid.get("ext", {}).get("prebid", {}).get("type") == "video"

        assert data["seatbid"][0]["seat"] == "amt"
    else:
        logger.info(SKIP_REASON)
        logger.info("Skipping detailed test as AMT_ADAPTER_ENABLED or AMT_BIDDING_SERVER_SIMULATOR_ENDPOINT is not set")


@pytest.mark.run(order=5)
def test_mixed_banner_video_auction_request():
    """Test a mixed request with banner + outstream video + instream video in a single auction."""
    random_id = uuid.uuid4().hex

    auction_request = {
        "id": random_id,
        "imp": [
            {
                "id": "banner_imp_1",
                "banner": {"w": 300, "h": 250},
                "ext": {
                    "prebid": {
                        "bidder": {
                            "amt": {"placementId": "banner-1", "bidFloor": 0.5, "bidCeiling": 25.0}
                        }
                    }
                }
            },
            {
                "id": "outstream_video_imp_1",
                "video": {
                    "mimes": ["video/mp4"],
                    "protocols": [2, 5],
                    "w": 640,
                    "h": 480,
                    "placement": 3,
                    "minduration": 5,
                    "maxduration": 30
                },
                "ext": {
                    "prebid": {
                        "bidder": {
                            "amt": {"placementId": "outstream-1", "bidFloor": 2.0, "bidCeiling": 50.0}
                        }
                    }
                }
            },
            {
                "id": "instream_video_imp_1",
                "video": {
                    "mimes": ["video/mp4"],
                    "protocols": [2, 3, 5, 6],
                    "w": 1920,
                    "h": 1080,
                    "startdelay": 0,
                    "placement": 1,
                    "minduration": 5,
                    "maxduration": 30
                },
                "ext": {
                    "prebid": {
                        "bidder": {
                            "amt": {"placementId": "instream-1", "bidFloor": 5.0, "bidCeiling": 75.0}
                        }
                    }
                }
            }
        ],
        "site": {
            "page": "publisher.example.com",
            "publisher": {"id": "pub-001"}
        },
        "at": 1,
        "tmax": 5000,
        "cur": ["USD"],
        "ext": {
            "prebid": {
                "targeting": {
                    "pricegranularity": {
                        "precision": 2,
                        "ranges": [{"max": 50, "increment": 0.5}]
                    }
                },
                "cache": {"bids": {}, "vastxml": {}},
                "auctiontimestamp": 1000
            }
        },
        "regs": {"ext": {"gdpr": 0}}
    }

    time.sleep(5)
    auction_response = requests.post(url, json=auction_request)
    logger.info(auction_response)
    assert auction_response.status_code == 200
    logger.info(auction_response.json())

    if (
        os.environ.get("AMT_ADAPTER_ENABLED") and
        os.environ.get("AMT_BIDDING_SERVER_SIMULATOR_ENDPOINT") and
        os.environ["TEST_AWS_REGION"] in TEST_REGIONS
    ):
        data = auction_response.json()
        assert data["id"] == random_id
        assert data["cur"] == "USD"

        bids = data["seatbid"][0]["bid"]
        imp_ids = {b["impid"] for b in bids}
        assert imp_ids == {"banner_imp_1", "outstream_video_imp_1", "instream_video_imp_1"}

        for bid in bids:
            bid_type = bid.get("ext", {}).get("prebid", {}).get("type")
            if "banner" in bid["impid"]:
                assert bid_type == "banner"
            else:
                assert bid_type == "video"
                assert "VAST" in bid.get("adm", "")

        assert data["seatbid"][0]["seat"] == "amt"
    else:
        logger.info(SKIP_REASON)
        logger.info("Skipping detailed test as AMT_ADAPTER_ENABLED or AMT_BIDDING_SERVER_SIMULATOR_ENDPOINT is not set")
