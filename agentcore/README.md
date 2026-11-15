# PortfolioGuard AgentCore agents

Five agents, each its own Amazon Bedrock AgentCore runtime built with the Strands Agents SDK.

| Agent | Folder | Tool | What the tool uses |
| --- | --- | --- | --- |
| Orchestrator | `orchestrator/` | `intake_agent`, `market_agent`, `classifier_agent`, `explainer_agent` | Calls the four runtimes below in order |
| Intake | `intake/` | `assess_investor` | Persona presets, the S3 investor record, Bedrock for a self-description |
| Market | `market/` | `compare_snapshots` | Financial-tools Lambda over the versioned market data in S3 |
| Classifier | `classifier/` | `classify_move` | Financial-tools Lambda (deterministic scores, headline sentiment pre-scored by Bedrock) |
| Explainer | `explainer/` | `write_explanation` | Persona Fit, then a Bedrock model with digit and evidence-ID checks |

A model decides when to call each tool, but the tools produce every figure and the result returned
is the tool's, never the model's text. The Orchestrator enforces the order and runs any step the
model skipped.

## Try it without AWS

```bash
pip install strands-agents bedrock-agentcore pytest
ENGINE=local pytest agentcore/tests -q
```

## Deploy

Deployed 2026-11-15 as the stack `portfolioguard-workshop-agentcore-agents` (`infra/agentcore-agents.yaml`):
five runtimes `portfolioguard_{intake,market,classifier,explainer,orchestrator}_workshop` and two roles.

1. `S3_BUCKET=<bucket> scripts/build_agentcore_agents.sh --upload` builds the five ARM64 packages and
   uploads them to `s3://<bucket>/agents/agentcore/`; it prints each S3 version ID.
2. Create a change set for `infra/agentcore-agents.yaml` with those version IDs as parameters
   (`IntakeVersionId`, ...), review it, then execute it. A new package version updates that agent.
3. Backend `.env`: `ORCHESTRATOR_AGENT_ARN` (stack output). Buy/sell checks then go to the Orchestrator;
   everything else still goes to `AGENT_RUNTIME_ARN`. Change `AGENT_SESSION_SUFFIX` after an update.

The Orchestrator gets the four specialist ARNs from its environment (set by the stack).

Permissions each execution role needs (review before applying):

- all five: `bedrock:InvokeModel` on the chosen model;
- Market, Classifier, Explainer: `lambda:InvokeFunction` on the financial-tools function;
- Intake: `s3:GetObject` and `s3:PutObject` on `personas/*` in the data bucket;
- Orchestrator: `bedrock-agentcore:InvokeAgentRuntime` on the four specialist runtimes.
