# Prebid Server Docker Build Context

## Directory Structure

| Directory | Purpose | Deployed To |
|-----------|---------|-------------|
| `default-config/` | Baseline PBS config (YAML, logging, entrypoint) | S3 → container at startup |
| `current-config/` | Custom config overrides (precedence over default) | S3 → container at startup |
| `stored_requests/` | Stored request templates | S3 stored requests bucket |
| `stored_impressions/` | Stored impression templates | S3 stored requests bucket |
| `stored_responses/` | Static bid responses for testing | S3 stored requests bucket |
| `stored_accounts/` | Publisher account settings | S3 stored requests bucket |
| `amt-bidder/` | AMT adapter source (populated by deploy script) | Docker image at build time |
| `extra-modules/` | Custom PBS modules (analytics) | Docker image at build time |

All `stored_*` directories are uploaded to S3 on deploy via a Lambda custom resource. PBS reads from S3 with a 15-minute in-memory cache refresh. See the README in each directory for details.

For Prebid Server configuration reference, see the [PBS Java documentation](https://github.com/prebid/prebid-server-java/blob/master/docs/application-settings.md).

## AMT Bidder Directory

The `amt-bidder/` directory is intentionally empty in version control.

- **Without bidder simulator**: Leave empty — ensures Docker COPY commands succeed
- **With bidder simulator**: `./deploy.sh --deploy-bidding-simulator` populates this with adapter source from `source/loadtest/amt-bidder/`
