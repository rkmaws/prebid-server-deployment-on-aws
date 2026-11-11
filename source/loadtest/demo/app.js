// Prebid.js including needed modules
import pbjs from 'prebid.js';
import 'prebid.js/modules/prebidServerBidAdapter';
import 'prebid.js/modules/consentManagementGpp';
import 'prebid.js/modules/consentManagementTcf';
import 'prebid.js/modules/gppControl_usnat';
import 'prebid.js/modules/gppControl_usstates';
import 'prebid.js/modules/gptPreAuction';
import 'prebid.js/modules/videoModule';

// Video.js including needed modules
import videojs from 'video.js';
import 'video.js/dist/video-js.css';
window.videojs = videojs;
require('videojs-vast-vpaid/dist/videojs_5.vast.vpaid.js');

// Ad units configuration
import { adUnits } from './adUnits.js';

// Read the Prebid Server endpoint from the "prebidserver" query parameter.
// Falls back to a relative path for local development or same-origin setups.
var PREBID_SERVER_ENDPOINT = (function() {
    var params = new URLSearchParams(window.location.search);
    var ep = params.get("prebidserver");
    return ep ? "https://" + ep + "/openrtb2/auction" : "/openrtb2/auction";
})();

// Configure Prebid Server
var prebidServerConfig = {
    debug: true,
    s2sConfig: [
        {
            accountId: '12345',
            bidders: ['amt'],
            adapter: 'prebidServer',
            enabled: true,
            endpoint: PREBID_SERVER_ENDPOINT,
            extPrebid: {
                cache: {
                    vastxml: {returnCreative: false}
                }
            }
        }
    ],
    consentManagement: {
        gdpr: {
            cmpApi: 'static', // Use 'static' to provide manual data
            timeout: 0,         // No need to wait for a CMP
            defaultGdprScope: false, // Forces regs.ext.gdpr=0 if not found
            consentData: {
                getTCData: {
                    gdprApplies: false, // Explicitly set to false
                    tcString: ""   // TC string not needed when gdprApplies is false
                }
            }
        }
    }
};

// Initialize Prebid.js
pbjs.processQueue();
pbjs.que.push(function() {
    console.log("Initializing Prebid.js");
    pbjs.setConfig(prebidServerConfig);
    pbjs.addAdUnits(adUnits);
    pbjs.requestBids({
        timeout: 10000,
        bidsBackHandler: renderAllAdUnits
    });
});   

const renderAllAdUnits = function() {
    console.log("Getting winning bids");
    var winners = pbjs.getHighestCpmBids();
    console.log('render ad units: ', winners); 
    for (var i = 0; i < winners.length; i++) {
        const adUnitPlaceholder = document.getElementById(winners[i].adUnitCode);
        if (winners[i].adUnitCode === 'instream_video_imp_1') {
            // Handle instream video - load VAST ad
            invokeVideoPlayer(winners[i].vastUrl);
        } else if (winners[i].adUnitCode === 'outstream_video_imp_1') {
            // Handle outstream
            pbjs.renderAd(adUnitPlaceholder, winners[i].adId);
        } else {
            // Handle banner
            const iframe = document.createElement('iframe');
            adUnitPlaceholder.appendChild(iframe);
            pbjs.renderAd(iframe.contentWindow.document, winners[i].adId);
        }
    }
}

function invokeVideoPlayer(vastUrl) {
    console.log('VAST URL:', vastUrl);
    // Initialize Video.js player with sample content
    const player = videojs('videojs', {
        controls: true,
        autoplay: true,
        preload: 'auto'
    });
    player.src({
        type: 'video/mp4',
        src: 'https://media.w3.org/2010/05/sintel/trailer.mp4'
    });
    // add preroll
    player.vastClient({
        adTag: vastUrl,
        playAdAlways: true,
        verbosity: 4,
        autoplay: true
    });
    // autoplay
    player.muted(true);
    player.play();
}