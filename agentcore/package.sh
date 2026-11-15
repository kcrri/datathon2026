#!/usr/bin/env bash
# Stage one deployable folder per agent under agentcore/build/<agent>/: its main.py and
# requirements.txt, common.py, and the shared backend code (app/, lambda/financial_tools/).
# Local file copies only. It does not deploy anything.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
repo="$here/.."
rm -rf "$here/build"
for agent in intake market classifier explainer orchestrator; do
  out="$here/build/$agent"
  mkdir -p "$out"
  cp "$here/$agent/main.py" "$here/$agent/requirements.txt" "$here/common.py" "$out/"
  cp -R "$repo/backend/app" "$out/app"
  mkdir -p "$out/lambda"
  cp -R "$repo/lambda/financial_tools" "$out/lambda/financial_tools"
  find "$out" -name __pycache__ -type d -prune -exec rm -rf {} +
  echo "staged $out"
done
