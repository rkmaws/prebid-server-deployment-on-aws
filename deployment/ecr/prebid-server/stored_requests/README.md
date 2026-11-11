# stored_requests/

Place Prebid Server stored request JSON files here. Files are uploaded to S3 on deploy and loaded by PBS via in-memory cache (15-min refresh).

Filename without `.json` extension = the stored request ID.

See `video-test-stored-req.json` for an example used with the bidder simulator.

For stored request format and usage, see the [Prebid Server documentation](https://github.com/prebid/prebid-server-java/blob/master/docs/application-settings.md).
