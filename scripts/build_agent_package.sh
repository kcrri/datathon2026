#!/usr/bin/env bash
# Build the AgentCore Runtime code package: main.py + the agents (backend/app) + dependencies.
#
#   scripts/build_agent_package.sh            builds .build/portfolioguard-agents.zip
#   S3_BUCKET=<bucket> scripts/build_agent_package.sh --upload   also uploads it to S3
#
# AgentCore Runtime runs on Linux ARM64 and rejects packages with binaries for any other
# platform, so the only compiled dependency (pydantic-core) is installed for ARM64 only.
# Everything else is pure Python.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD="$REPO_ROOT/.build/agent"
ZIP="$REPO_ROOT/.build/portfolioguard-agents.zip"
KEY="${AGENT_CODE_KEY:-agents/portfolioguard-agents.zip}"

rm -rf "$BUILD" "$ZIP"
mkdir -p "$BUILD"
for platform in manylinux2014_aarch64; do
  PLATFORM_DIR="$REPO_ROOT/.build/deps-$platform"
  rm -rf "$PLATFORM_DIR"
  python3 -m pip install --quiet --no-compile --only-binary=:all: --python-version 3.12 \
    --platform "$platform" --target "$PLATFORM_DIR" -r "$REPO_ROOT/agentcore/requirements.txt"
  rsync -a "$PLATFORM_DIR/" "$BUILD/"
  rm -rf "$PLATFORM_DIR"
done
cp "$REPO_ROOT/agentcore/main.py" "$BUILD/main.py"
# The agents need everything in app/ except the web API layer, which stays in the gateway.
rsync -a --exclude '__pycache__' --exclude '*.pyc' --exclude 'api/' --exclude 'main.py' "$REPO_ROOT/backend/app/" "$BUILD/app/"
find "$BUILD" -name '__pycache__' -type d -prune -exec rm -rf {} +
(cd "$BUILD" && zip -q -r -X "$ZIP" .)
echo "built $ZIP ($(du -h "$ZIP" | cut -f1))"

if [[ "${1:-}" == "--upload" ]]; then
  : "${S3_BUCKET:?set S3_BUCKET to the approved data bucket}"
  AWS_PROFILE="${AWS_PROFILE:-portfolioguard-workshop}" AWS_REGION="${AWS_REGION:-us-east-1}" \
    aws s3api put-object --bucket "$S3_BUCKET" --key "$KEY" --body "$ZIP" --query 'VersionId' --output text
fi
