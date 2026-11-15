#!/usr/bin/env bash
# Upload the simulated market data (prices, headlines, current scores) and its manifest to the
# approved private S3 bucket. Run only after the upload has been approved.
set -euo pipefail

: "${S3_BUCKET:?set S3_BUCKET from the approved CloudFormation stack output}"
MARKET_PREFIX="${MARKET_PREFIX:-simulated/v1}"
AWS_REGION="${AWS_REGION:-us-east-1}"
AWS_PROFILE="${AWS_PROFILE:-portfolioguard-workshop}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SOURCE="$REPO_ROOT/data/simulated"
MANIFEST="$REPO_ROOT/data/manifests/simulated-v1.json"

if [[ "$AWS_REGION" != "us-east-1" ]]; then
  echo "refusing upload outside approved workshop Region us-east-1" >&2
  exit 2
fi

test -f "$MANIFEST"
python3 "$REPO_ROOT/scripts/build_market_manifest.py" --check
AWS_ARGS=(--profile "$AWS_PROFILE" --region "$AWS_REGION")
for folder in current marketchange; do
  for file in prices.csv news.csv news_scored.csv; do
    aws "${AWS_ARGS[@]}" s3 cp "$SOURCE/$folder/$file" "s3://$S3_BUCKET/$MARKET_PREFIX/$folder/$file" --only-show-errors
  done
done
aws "${AWS_ARGS[@]}" s3 cp "$MANIFEST" "s3://$S3_BUCKET/$MARKET_PREFIX/manifest.json" --only-show-errors
echo "uploaded to s3://$S3_BUCKET/$MARKET_PREFIX/"
