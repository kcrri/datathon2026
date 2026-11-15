#!/usr/bin/env bash
# Upload the reviewed starter dataset and manifest to the approved private S3 bucket.
set -euo pipefail

: "${S3_BUCKET:?set S3_BUCKET from the approved CloudFormation stack output}"
DATA_PREFIX="${DATA_PREFIX:-starter/v1}"
AWS_REGION="${AWS_REGION:-us-east-1}"
AWS_PROFILE="${AWS_PROFILE:-portfolioguard-workshop}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA_DIR="${DATA_DIR:-$REPO_ROOT/hackathon_info/alphaforge_starter}"
MANIFEST="$REPO_ROOT/data/manifests/starter-v1.json"

if [[ "$AWS_REGION" != "us-east-1" ]]; then
  echo "refusing upload outside approved workshop Region us-east-1" >&2
  exit 2
fi

test -f "$MANIFEST"
python3 "$REPO_ROOT/scripts/verify_data_manifest.py"
AWS_ARGS=(--profile "$AWS_PROFILE" --region "$AWS_REGION")
aws "${AWS_ARGS[@]}" s3 sync "$DATA_DIR" "s3://$S3_BUCKET/$DATA_PREFIX/" \
  --exclude "*" --include "*.csv" --only-show-errors
aws "${AWS_ARGS[@]}" s3 cp "$MANIFEST" \
  "s3://$S3_BUCKET/$DATA_PREFIX/manifest.json" --only-show-errors
