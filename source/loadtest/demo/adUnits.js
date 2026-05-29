import InRenderer from 'in-renderer-js';

// Define ad units
export const adUnits = [
    {
        code: 'banner_imp_1',
        mediaTypes: {
            banner: {
                sizes: [[300, 250]]
            }
        },
        bids: [
            {
                bidder: 'amt',
                params: {
                    placementId: "13144370",
                    bidFloor: 1,
                    bidCeiling: 100000,
                }
            }
        ]
    },
    {
        code: 'banner_imp_2',
        mediaTypes: {
            banner: {
                sizes: [[300, 250]]
            }
        },
        bids: [
            {
                bidder: 'amt',
                params: {
                    placementId: "13144371",
                    bidFloor: 1,
                    bidCeiling: 100000,
                }
            }
        ]
    },
    {
        code: 'outstream_video_imp_1',
        mediaTypes: {
            video: {
                context: "outstream",
                playerSize: [360, 360],
                mimes: ["video/mp4"],
            }
        },
        bids: [
            {
                bidder: 'amt',
                params: {
                    placementId: "13144370",
                    bidFloor: 1,
                    bidCeiling: 100000,
                }
            }
        ],
        renderer: {
            render: function(bid) {
                var inRenderer = new InRenderer();
                inRenderer.render("outstream_video_imp_1", bid, {});
            }
        }
    },
    {
        code: 'instream_video_imp_1',
        mediaTypes: {
            video: {
                context: "instream",
                playerSize: [640, 480],
                mimes: ["video/mp4"],
                protocols: [1, 2, 3, 4, 5, 6, 7, 8],
                playbackmethod: [2],
                skip: 1
            }
        },
        bids: [
            {
                bidder: 'amt',
                params: {
                    placementId: "13144370",
                    bidFloor: 1,
                    bidCeiling: 100000,
                }
            }
        ]
    }
];
