# stored_impressions/

Place Prebid Server stored impression JSON files here. Files are uploaded to S3 on deploy and loaded by PBS via in-memory cache (15-min refresh).

Filename without `.json` extension = the stored impression ID.

See `preroll-config.json` and `midroll-config.json` for examples used with the bidder simulator.

For stored impression format and usage, see the [Prebid Server documentation](https://github.com/prebid/prebid-server-java/blob/master/docs/application-settings.md).
