# Polyfinances workshop deployment readiness

**Verification date:** 2026-11-14
**Status:** Application stack, dataset, and one live Lambda acceptance run are
verified; Bedrock remains prohibited pending separate approval
**Region:** `us-east-1`
**Profile:** `portfolioguard-workshop`
**Account:** `010928180049`
**Identity:** `arn:aws:sts::010928180049:assumed-role/WSParticipantRole/Participant`

Temporary credentials, access keys, secret keys, and session tokens must never be
placed in the repository, logs, screenshots, or chat.

## Live Lambda acceptance verification — 2026-11-14

Exactly one synchronous invocation tested `compare_strategy_shift` for a 20-point
TFSA allocation shift from growth to dividend over 2023-11-13 through 2026-11-12.

- Request ID: `dc653658-6c96-40fd-9310-f616a0b1e086`
- Result: `status=ok`, `conclusion=risk_reduced`
- S3 proof: response cites the exact current version IDs for `prices_daily.csv`,
  `fx_usdcad_daily.csv`, and `manifest.json`
- Schema: all required fields and five `MetricEvidence` records validated
- Determinism: zero absolute difference from local calculations across all metric
  values and all 93 performance points
- Window: 738 common observations
- Duration: 2,628.69 ms; billed duration: 2,753 ms
- Cold-start initialization: 123.50 ms
- Memory: 512 MB configured; 123 MB maximum used
- CloudWatch: normal START/END/REPORT plus calculation started/completed; no error,
  exception, timeout, or retry
- Estimated list-price cost: approximately USD $0.0000186 for Lambda compute and
  request before free tier; under USD $0.00003 including three S3 reads and logs

Returned deterministic metrics:

| Metric | Current | Proposed | Delta |
| --- | ---: | ---: | ---: |
| Annualized volatility | 18.4761% | 13.7066% | -4.7696 pp |
| Maximum drawdown | -19.7236% | -15.5291% | +4.1945 pp |
| Annualized historical return | 30.8014% | 27.4180% | -3.3835 pp |
| Total historical return | 119.3034% | 103.1224% | -16.1810 pp |
| Asset concentration HHI | 0.1404 | 0.1144 | -0.0260 |

No Lambda configuration, IAM permission, S3 object, or CloudFormation resource was
modified. No automatic trigger exists, no retry was issued, and Bedrock was not
invoked.

## Dataset upload verification — 2026-11-14

The deployed stack output resolved to the exact approved bucket before upload. All
six local files passed manifest byte-count and SHA-256 validation. Exactly those six
files plus `manifest.json` were uploaded under `starter/v1/` with S3 SHA-256
checksums enabled.

| Key under `starter/v1/` | Bytes | SHA-256 | Version ID |
| --- | ---: | --- | --- |
| `assets_universe.csv` | 2,089 | `f78de8ecb36d914a3448db63498cc9a04a34d805bccb79c481dda1650755467d` | `5Md5bGxXIb9AK0NfBWS_tkyqvhgy82Sf` |
| `prices_daily.csv` | 3,224,985 | `ff2a3f2d0a7d72ea835e8d616d041e0510f018340cef3d3e55b918830e8a569d` | `5IzrfNd9QcvjN.wr4v1fAnOv5hyMeXfD` |
| `corporate_actions.csv` | 29,728 | `37d99f1472f9f1c7360432835353488bdf72bb055295ec66155211a30d8312b1` | `Glqvb62EMDDxyFzjnJsGizBP8_H2BrFR` |
| `fx_usdcad_daily.csv` | 33,344 | `f04e218ac5b0145fd552b3d0dcfbf73e5e17bb9a6fb4562460dbec95cb8972b3` | `P0pWWZIhHouuajKaoAKm5EQYKvoQxnn9` |
| `macro_rates.csv` | 1,074,518 | `2c04b0ca5590396fee1f0de13c0b2a95731125a61c79166d553d106f0375c73e` | `9dJvRX0m671wObxaKUJc.iBAaXLAF8HT` |
| `sources_metadata.csv` | 2,846 | `7ff17052c8235888c4984430830610ae0d81c0df71585afaacb87ba5fe531bdf` | `17dtwpasD7aScenUiBM67uhsQpeJp3oe` |
| `manifest.json` | 1,574 | `847cb84060c517fda9adef90d1ddb2b02b20db0ede3f47922b69510e3aac0208` | `8GGBwEar9wccTuZbvfJonGSSISMUDD.L` |

Every S3-reported checksum decoded to the exact expected local SHA-256. Each key has
one current version and there are no delete markers or unrelated prefix objects.
Every object reports `AES256` encryption. Bucket versioning remains enabled and all
four public-access-block settings remain true. No bucket policy, notification, IAM
permission, CloudFormation resource, Lambda, or Bedrock configuration was changed.

## Deployment verification — 2026-11-14

The exact approved change set was rechecked immediately before execution. It was
still `AVAILABLE` with the same four Add actions and zero Modify/Remove actions.
CloudFormation completed without error at 2026-11-14 21:29:25 UTC.

| Logical resource | Physical resource / ARN | Verified state |
| --- | --- | --- |
| `DataBucket` | `arn:aws:s3:::portfolioguard-workshop-data-010928180049-us-east-1` | Empty; AES-256; versioning enabled; all public-access blocks enabled; 30-day noncurrent-version expiration; no notifications |
| `FinancialToolsExecutionRole` | `arn:aws:iam::010928180049:role/portfolioguard-workshop-FinancialToolsExecutionRole-AhclaNzKFARH` | Lambda-only trust; exactly one approved inline policy; no managed policies |
| `FinancialToolsFunction` | `arn:aws:lambda:us-east-1:010928180049:function:portfolioguard-workshop-financial-tools` | Active; successful update; ARM64 Python 3.12; 512 MB; 30 seconds; concurrency 2 |
| `FinancialToolsLogGroup` | `arn:aws:logs:us-east-1:010928180049:log-group:/aws/lambda/portfolioguard-workshop-financial-tools` | 14-day retention; zero bytes; no log streams |

The Lambda has zero event-source mappings, no resource-based policy, no function
URL, no asynchronous destination configuration, and no S3 notification. Therefore
it has no automatic invocation trigger. Neither Lambda nor Bedrock was invoked.

## Change-set review record — 2026-11-14

- At review time, before the separately approved execution:
- Application stack: `portfolioguard-workshop`
- Stack status: `REVIEW_IN_PROGRESS`
- Change set: `samcli-deploy1794691346`
- Change-set status: `CREATE_COMPLETE`
- Execution status: `AVAILABLE`
- Capability: `CAPABILITY_IAM`
- Parameters: `Environment=workshop`, `DataPrefix=starter/v1`,
  `DatasetId=alphaforge-starter-v1`, and
  `BedrockModelId=us.amazon.nova-lite-v1:0`
- Proposed actions: four **Add**, zero Modify, zero Remove

| Action | Logical resource | Type | Reviewed configuration |
| --- | --- | --- | --- |
| Add | `DataBucket` | `AWS::S3::Bucket` | Exact name `portfolioguard-workshop-data-010928180049-us-east-1`; AES-256 encryption, all public-access blocks, versioning, 30-day noncurrent-version expiration, retained on stack deletion |
| Add | `FinancialToolsExecutionRole` | `AWS::IAM::Role` | CloudFormation-generated stack-scoped name; Lambda-only trust; one inline least-privilege policy described below |
| Add | `FinancialToolsFunction` | `AWS::Lambda::Function` | Exact name `portfolioguard-workshop-financial-tools`; ARM64 Python 3.12, 512 MB, 30-second timeout, concurrency 2, no event source or public endpoint |
| Add | `FinancialToolsLogGroup` | `AWS::Logs::LogGroup` | Exact name `/aws/lambda/portfolioguard-workshop-financial-tools`; 14-day retention; deleted with stack |

The execution role trust policy allows only `lambda.amazonaws.com` to call
`sts:AssumeRole`. Its inline policy
`ReadVersionedPortfolioGuardDatasetAndWriteLogs` allows only:

- `s3:GetObject` and `s3:GetObjectVersion` on
  `arn:aws:s3:::portfolioguard-workshop-data-010928180049-us-east-1/starter/v1/*`;
- `logs:CreateLogStream` and `logs:PutLogEvents` on
  `arn:aws:logs:us-east-1:010928180049:log-group:/aws/lambda/portfolioguard-workshop-financial-tools:*`.

It grants no wildcard action, bucket listing, object writes, Bedrock access, Lambda
invocation, role chaining, or transaction capability. The processed Lambda artifact
references only the SAM packaging bucket key
`d464c006e41f58daeaa1e51678d23a8c`.

### Packaging artifacts already created

SAM created its standard reusable stack `aws-sam-cli-managed-default`, now
`CREATE_COMPLETE`, containing:

- S3 bucket `aws-sam-cli-managed-default-samclisourcebucket-cdt4mdeaihzl`;
- its bucket policy, which conditionally allows Serverless Application Repository
  object reads for this account and denies all insecure-transport S3 requests;
- code object `d464c006e41f58daeaa1e51678d23a8c` (5,991 bytes);
- processed template object `f9b76923fd9921c2ae3e647081477992.template`
  (5,210 bytes).

The bucket blocks all public access and uses AWS KMS server-side encryption. It
contains no financial dataset. Local build artifacts are under `.aws-sam/build/`
and are ignored by Git.

The managed packaging stack may be retained for subsequent SAM deployments. Full
cleanup requires deleting both objects and then deleting
`aws-sam-cli-managed-default`; that is a separate destructive action requiring
approval. The now-deployed application stack also requires explicit approval before
any cleanup action.

### Execution review outcome

The reviewed change set was separately approved and executed successfully within
the architecture and USD $1.00 ceiling. Names are PortfolioGuard-specific, IAM is
narrow, no endpoint or event trigger can invoke the Lambda, and the data bucket is
empty. The operational caveat remains that the bucket is retained during stack
deletion and must later be emptied/deleted separately.

## 1. Confirmed read-only findings

### Identity and controls

- STS resolved the configured profile to account `010928180049` and
  `WSParticipantRole/Participant`.
- The role has no permissions boundary. Attached policies include
  `AdministratorAccess`, the Workshop Studio default policy, and workshop service
  restrictions.
- The Workshop Studio policy explicitly denies actions outside `us-east-1`, with
  selected global/cross-Region exceptions. Bedrock `Invoke*` is one of those
  exceptions. An unrelated policy denies access to a Kiro secret.
- The role itself is not Lambda-assumable. That is correct: it is the deployment
  and local caller identity, not the function execution role.

### Permission simulation

IAM simulation returned **allowed**, with organization evaluation also allowing the
critical actions, for the following deployment surfaces:

| Surface | Confirmed simulated permissions |
| --- | --- |
| S3 | Create/configure bucket, put/get objects, versioning, public-access block |
| Lambda | Create/update/configure/delete/get/invoke function and concurrency |
| CloudFormation | Validate, create/describe/execute change sets, stack operations |
| IAM | Create/get/tag role, put/get/delete inline policy, pass/delete role |
| CloudWatch Logs | Create/delete group, retention, streams, and log events |
| Bedrock | Get inference profile and invoke the exact profile/destination models |

This confirms the evaluated identity-policy and Organizations decision paths. It
does not prove that every eventual resource condition will pass during deployment,
and it deliberately does not replace a live Bedrock acceptance call.

### Lambda execution role

Nine Lambda-trusted roles exist, but they are SageMaker-, Kiro-, or Workshop
internal roles. `WSLambdaCurtailerRole` has no attached or inline permissions, and
`WSRestrictedActionsRole` is reserved for internal Workshop functions and is
explicitly denied for participant `PassRole`. No suitable existing PortfolioGuard
execution role was found.

Simulation confirms that `WSParticipantRole` can create, configure, pass, and
delete a dedicated role. The SAM template therefore creates exactly one unnamed
`AWS::IAM::Role` with:

- trust only for `lambda.amazonaws.com`;
- `s3:GetObject` and `s3:GetObjectVersion` only under `starter/v1/*` in the stack
  bucket;
- `logs:CreateLogStream` and `logs:PutLogEvents` only for the function log group.

The role has no fixed `RoleName`, managed policy, wildcard action, or Bedrock
permission. Deployment must acknowledge `CAPABILITY_IAM`.

### Bedrock profile

`bedrock:GetInferenceProfile` returned the active system-defined profile
`us.amazon.nova-lite-v1:0` with these exact destinations:

- `us-east-1`: `amazon.nova-lite-v1:0`
- `us-east-2`: `amazon.nova-lite-v1:0`
- `us-west-2`: `amazon.nova-lite-v1:0`

Simulation allowed `bedrock:InvokeModel` for the inference-profile ARN and all
three model ARNs, with no missing context and organization evaluation allowed. The
Workshop policy's out-of-Region deny exempts Bedrock invocation, so no simulated
cross-Region blocker was found. Actual compatibility remains **unproven until a
separately approved, chargeable invocation**; none was performed during readiness
verification.

### Lambda capacity

The `us-east-1` account limit is 400 concurrent executions, with 110 unreserved at
verification time. The function reserves two, so no quota blocker was found.

## 2. Template and local tool validation

- AWS CLI v2.40.3 is installed and the named profile works.
- AWS SAM CLI v1.172.1 was installed locally and reports successfully.
- Python 3.12.16 was installed locally to match the Lambda runtime.
- `sam validate --lint` accepts `infra/template.yaml` as a valid SAM template.
- A clean local `sam build` succeeds for ARM64 Python 3.12.
- The read-only CloudFormation `ValidateTemplate` API accepts the template and
  reports the expected four parameters and SAM transform capability.
- The configuration fixes deployment to `us-east-1`, uses the US Nova Lite profile,
  requires change-set confirmation, and declares `CAPABILITY_IAM`.

## 3. Resource inventory

The SAM artifact bucket, two packaging objects, and four application resources now
exist. The dataset bucket remains empty and no service has been invoked.

| Resource | Created by | Purpose | Charge surface | Cleanup |
| --- | --- | --- | --- | --- |
| SAM artifact bucket/object | SAM CLI | Deployment artifact | Tiny S3 storage/request cost | Delete with approval |
| CloudFormation stack | SAM/CloudFormation | Owns application resources | No direct charge | Delete stack |
| Versioned S3 data bucket | Stack | Reviewed CSVs and manifest | Storage/requests | Retained; empty/delete separately |
| Lambda function | Stack | Deterministic calculations | Requests/GB-seconds | Delete with stack |
| Lambda execution role | Stack | Narrow S3/log permissions | No direct charge | Delete with stack |
| CloudWatch log group | Stack | Structured logs, 14-day retention | Ingestion/storage | Delete with stack |
| Bedrock inference | Existing managed service | Grounded explanation | Input/output tokens | No persistent resource |

The stack creates no API Gateway, database, VPC, NAT gateway, frontend/backend
hosting, provisioned Bedrock throughput, transaction integration, alarm, or
dashboard.

## 4. Cost estimate for the 72-hour workshop

Assumptions: under 5 MB of data, one small artifact, 100 demo analyses, a 512 MB
Lambda at about one second per calculation, about 4,000 Bedrock input and 500 output
tokens per analysis, and under 10 MB of logs.

| Service | Planning estimate |
| --- | ---: |
| S3 | Less than $0.01 |
| Lambda | Less than $0.01 at expected duration |
| Nova Lite | About $0.04 for 100 assumed analyses |
| CloudWatch Logs | Less than $0.01 |
| CloudFormation and IAM | No direct service charge |
| **Expected total** | **Under $0.10; conservative approval ceiling: $1.00** |

This is not a billing guarantee. Actual tokens, retries, existing free-tier usage,
Workshop credits, taxes, and current pricing can change the result.

## 5. Blockers and residual risks

There is no confirmed policy, role, template, tooling, or quota blocker for
executing the reviewed change set. Residual gates are intentional:

1. Temporary Workshop credentials may expire and must be refreshed securely.
2. Any future CloudFormation update requires a new reviewed change set and explicit
   approval.
3. Cross-Region Nova Lite invocation is simulated as allowed but cannot be proven
   without the separately approved live call.
4. Dataset upload, Lambda invocation, and Bedrock invocation are all prohibited
   until their explicit approvals.
5. The S3 data bucket uses `DeletionPolicy: Retain`; teardown therefore needs a
   separate approved empty/delete action.

Organizer assistance is needed only if a future update encounters an unanticipated
service-control restriction or if a later live Nova call is denied.

## 6. Next approval step

The minimum safe next phase is **one bounded Nova Lite acceptance invocation only**:

1. Refresh the `portfolioguard-workshop` profile privately if needed and re-run STS.
2. Send only the already-verified deterministic evidence to
   `us.amazon.nova-lite-v1:0` using the production explanation schema.
3. Validate evidence IDs, numeric-firewall behavior, limitations, latency, usage,
   and cost without allowing Nova to create financial values.
4. Stop before any additional Lambda or Bedrock invocation.

No Bedrock invocation should occur until the user explicitly approves step 2.

## 7. Secure credentials and cleanup

Use Workshop Studio's temporary credentials through the standard AWS credential
chain and the local named profile. Store no credential value in `.env`; expose only
`AWS_PROFILE=portfolioguard-workshop` and `AWS_REGION=us-east-1`. Never enable shell
tracing around credentials.

Before the workshop expires, delete the stack with explicit approval. Because the
data bucket is retained, emptying/deleting it is a separate destructive operation
requiring explicit approval. The same applies to the SAM artifact bucket. Confirm
that no unexpected tagged resource remains in `us-east-1`.
