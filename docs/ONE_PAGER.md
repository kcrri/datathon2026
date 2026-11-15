# PortfolioGuard AI — one-page summary

## The problem

Portfolio decisions are often presented as a single recommendation without showing
how the answer was produced, which evidence supports it, or which trade-offs and
limitations matter. Generative AI can make this worse if it invents financial
figures or hides the calculation path.

## The solution

PortfolioGuard AI is a transparent multi-agent decision-support prototype for
fictional TFSA and RRSP portfolios. A user asks a hypothetical allocation question;
the system delegates it through account and strategy agents, calculates historical
risk in AWS, applies governance rules, and uses Amazon Bedrock only to explain
verified evidence.

The first scenario asks:

> Would moving 20% of my TFSA from my growth strategy into my dividend strategy reduce my risk?

## Why it is agentic

```text
Global Orchestrator
  → TFSA or RRSP Account Agent
    → relevant Growth / Dividend / Momentum / Preservation Agents
      → deterministic AWS Lambda financial tool
  → Governance Agent
  → Bedrock Explainability Agent
```

Every delegation is typed, recorded, visible in the dashboard, and covered by
tests. Agents that do not contribute to a request are not invoked.

## Why the result is trustworthy

- Lambda is the only source of financial metrics.
- Lambda verifies manifest checksums, reads versioned S3 data, and returns object
  provenance.
- Adjusted close, CAD currency conversion, common calendars, and rebalance policy
  are explicit.
- Bedrock may cite only supplied evidence IDs and cannot introduce numbers.
- Governance exposes persona conflicts, account-scope limits, and missing ESG data.
- Historical observations are clearly separated from future outcomes.
- The application cannot execute a trade.

## Primary result

In the reviewed historical window, the proposed fictional shift lowers annualized
volatility from 18.48% to 13.71% and improves maximum drawdown from -19.72% to
-15.53%. Historical annualized return also falls from 30.80% to 27.42%. The answer
is therefore “lower measured historical risk, with a return trade-off,” not a
recommendation or forecast.

## AWS contribution

- **Amazon S3:** encrypted, private, versioned source data.
- **AWS Lambda:** deterministic financial calculations.
- **Amazon Bedrock:** grounded explanation through the Converse API.
- **IAM:** least-privilege access to the function and selected model resources.
- **CloudWatch:** correlated structured execution logs.

## User experience

The Next.js dashboard shows the investor persona, current and proposed allocation,
risk metrics, performance comparison, agent delegation trace, governance controls,
assumptions, limitations, and exact source objects. If AWS is unavailable, it shows
an honest unavailable state instead of placeholder results.

## Status and next step

The complete local vertical slice, infrastructure template, data manifest, tests,
CI, and dashboard are ready. The template is configured for the organizer workshop
in `us-east-1` and the US Nova Lite inference profile. Core AWS infrastructure has
been deployed and verified. One bounded Lambda acceptance test read the versioned
S3 dataset and matched the local deterministic engine exactly. The next separately
gated step is one Nova Lite explanation test; Bedrock has not yet been invoked.
