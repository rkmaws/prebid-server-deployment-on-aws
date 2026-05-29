### Prerequisite
* [Apache JMeter](https://jmeter.apache.org/)
  * macOS: `brew install jmeter`

### Running Tests Locally

Pass your CloudFront endpoint URL using the `-Jurl` property:

```bash
jmeter -n -t prebid_server_test_plan.jmx -Jurl=https://YOUR_CLOUDFRONT_ENDPOINT -l log.jtl
```

The `url` parameter in the JMX files uses JMeter's `__P()` function, so the value provided via `-Jurl` overrides the default at runtime.

### Running Tests with AWS Distributed Load Testing (DLT)

The [Distributed Load Testing on AWS](https://docs.aws.amazon.com/solutions/latest/distributed-load-testing-on-aws/overview.html) solution does not support passing JMeter properties (`-J` flags) through its UI or API. Before uploading a JMX file to DLT, you must set the `url` value directly in the file:

1. Open the JMX file in a text editor or JMeter GUI
2. Find the `url` User Defined Variable and replace the default value with your CloudFront endpoint
3. Upload the modified JMX file to DLT

### Test Plans

#### prebid_server_test_plan.jmx
This test plan uses several commercial bidding adapters in Prebid Server configured to respond in test mode. The bidding adapters do not make connections over the Internet when invoked this way and respond with fixed data. This test plan is suitable for verifying basic operations of the deployed stack are working.

#### prebid_server_test_plan_using_amt_adapter.jmx
This test plan uses the AMT bidding adapter. Use this when the stack is deployed with the AMT adapter enabled and a bidding server simulator endpoint configured.
