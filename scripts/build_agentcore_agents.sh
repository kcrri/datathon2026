#!/usr/bin/env bash
# Build one AgentCore Runtime code package per PortfolioGuard agent (Strands Agents SDK).
#
#   scripts/build_agentcore_agents.sh             builds .build/agentcore/<agent>.zip
#   S3_BUCKET=<bucket> scripts/build_agentcore_agents.sh --upload
#                                                 also uploads each zip to s3://<bucket>/agents/agentcore/
#                                                 and prints the S3 version IDs for infra/agentcore-agents.yaml
#
# AgentCore runs on Linux ARM64 and rejects binaries for any other platform, so dependencies are
# installed for ARM64 only. Each zip holds main.py, common.py, the agents' backend code (app/, without
# the web API layer) and the dependencies.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$REPO_ROOT/.build/agentcore"
DEPS="$OUT/deps"
AGENTS=(intake market classifier explainer orchestrator)

rm -rf "$OUT"
mkdir -p "$DEPS"
python3 -m pip install --quiet --no-compile --only-binary=:all: --python-version 3.12 \
  --platform manylinux2014_aarch64 --target "$DEPS" -r "$REPO_ROOT/agentcore/requirements-agents.txt"

for agent in "${AGENTS[@]}"; do
  stage="$OUT/stage-$agent"
  mkdir -p "$stage"
  rsync -a "$DEPS/" "$stage/"
  cp "$REPO_ROOT/agentcore/$agent/main.py" "$stage/main.py"
  cp "$REPO_ROOT/agentcore/common.py" "$stage/common.py"
  rsync -a --exclude '__pycache__' --exclude '*.pyc' --exclude 'api/' --exclude 'main.py' "$REPO_ROOT/backend/app/" "$stage/app/"
  find "$stage" -name '__pycache__' -type d -prune -exec rm -rf {} +
  (cd "$stage" && zip -q -r -X "$OUT/$agent.zip" .)
  rm -rf "$stage"
  echo "built $OUT/$agent.zip ($(du -h "$OUT/$agent.zip" | cut -f1))"
done

if [[ "${1:-}" == "--upload" ]]; then
  : "${S3_BUCKET:?set S3_BUCKET to the approved data bucket}"
  for agent in "${AGENTS[@]}"; do
    version=$(AWS_PROFILE="${AWS_PROFILE:-portfolioguard-workshop}" AWS_REGION="${AWS_REGION:-us-east-1}" \
      aws s3api put-object --bucket "$S3_BUCKET" --key "agents/agentcore/$agent.zip" --body "$OUT/$agent.zip" \
      --query 'VersionId' --output text)
    echo "$agent $version"
  done
fi
