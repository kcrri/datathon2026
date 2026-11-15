# ADR 0001: AWS-backed numeric firewall

**Status:** Accepted
**Date:** 2026-11-14

## Context

PortfolioGuard must be both genuinely agentic and financially reproducible. A
language model is useful for routing and explanation but is not an acceptable
source of portfolio metrics. The datathon also requires demonstrable AWS value.

## Decision

The global orchestrator delegates to one account agent and only the strategy
agents relevant to the requested change. Those agents request typed operations but
never calculate values. The orchestrator invokes a real AWS Lambda that reads
versioned S3 objects and produces every metric using deterministic code. Governance
is rule-based. Amazon Bedrock receives a closed evidence packet and may cite only
its supplied evidence IDs.

Production configuration fails closed when Lambda, S3, Bedrock, IAM permissions,
or required environment variables are unavailable. Unit tests may inject local
deterministic functions to test orchestration, but those tests are not evidence of
AWS integration. A separately marked acceptance test must call the deployed AWS
services.

## Consequences

- Financial results remain reproducible and source-backed.
- The UI can expose real delegation and AWS request provenance.
- Bedrock cannot silently become a calculation fallback.
- Demo availability depends on approved AWS resources and credentials; the UI
  presents a clear unavailable state instead of fabricated output.
- Geographic Bedrock profiles require IAM access to the profile and all underlying
  destination model ARNs.
