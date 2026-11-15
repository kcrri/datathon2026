# Data

The committed challenge package under `hackathon_info/alphaforge_starter/` is the source for the first AWS-backed demo. Market files are uploaded to a private, versioned S3 prefix; the Lambda never reads them from the application process.

The six approved CSV files and `starter-v1.json` manifest were uploaded to the
workshop bucket under `starter/v1/` on 2026-11-14. Local and S3-reported byte counts
and SHA-256 checksums match. Any replacement upload requires a new approval.

Generate the versioned integrity manifest before an approved upload:

```bash
python3 scripts/build_data_manifest.py
```

Verify the committed files without changing the manifest:

```bash
python3 scripts/verify_data_manifest.py
```

After the CloudFormation stack and upload have both been approved, set `S3_BUCKET`
from its output and run with the local Workshop Studio profile:

```bash
AWS_PROFILE=portfolioguard-workshop \
AWS_REGION=us-east-1 \
S3_BUCKET=<stack-output> \
scripts/upload_data.sh
```

The manifest records file hashes, row counts, and the safeguards that must remain visible in the analysis.

At runtime, Lambda loads `manifest.json` from the same versioned S3 prefix and
fails closed if the configured dataset ID, prefix, file size, or SHA-256 digest does
not match the price and FX objects used by the calculation.
