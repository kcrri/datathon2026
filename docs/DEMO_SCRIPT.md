# PortfolioGuard AI five-minute demo script

## Before recording

- Confirm the live AWS integration test passes against the approved stack.
- Confirm the backend health endpoint and live integration test report the expected
  Region, Lambda, versioned S3 sources, and Bedrock model.
- Use fictional persona and allocation data only.
- Open CloudWatch Logs to the current Lambda log group in a separate tab.
- Keep a prior real-run response available only as a clearly labeled backup artifact.

## 0:00–0:35 — Problem and promise

**Say:**

“Portfolio changes are often delivered as a recommendation without a transparent
calculation path. PortfolioGuard AI turns a hypothetical question into a traceable,
source-backed comparison. It never executes a trade, and every portfolio shown is
fictional.”

Show the landing page and simulation-only boundary.

## 0:35–1:05 — Investor context and question

Select **Amira**.

**Say:**

“Our first scenario is deliberately focused: would moving twenty percentage points
of Amira’s fictional TFSA from growth to dividend reduce measured risk? The current
allocation is sixty percent growth and twenty percent dividend. The proposal makes
both forty percent.”

Point to the allocation bars. Do not describe the result yet.

## 1:05–1:45 — Real agent hierarchy

Click **Analyze with live AWS**.

**Say while it runs:**

“This is not one prompt pretending to be many agents. The global orchestrator
selects the TFSA account agent. That account agent delegates only to the two
strategies affected by the change: growth and dividend. Those agents request a
typed deterministic operation; they do not calculate numbers.”

When the result appears, scroll to **Observable delegation** and point out the
parent/child trace, Lambda request ID, governance step, and Bedrock model.

## 1:45–2:40 — Deterministic AWS evidence

Scroll to **What changed**.

**Say:**

“AWS Lambda reads adjusted prices and USD/CAD observations from private, versioned
Amazon S3 objects. It converts USD listings into CAD, intersects the trading
calendars, and applies the same constant-weight method to both portfolios.”

“In this historical window, annualized volatility declines from about eighteen and
a half percent to thirteen and seven tenths. Maximum drawdown becomes less severe,
moving from about negative nineteen and seven tenths to negative fifteen and a
half. Asset concentration also falls.”

Point to the metric cards and performance chart.

## 2:40–3:20 — Trade-off, not recommendation

**Say:**

“The conclusion is not simply ‘yes.’ Historical annualized return also declines,
from about thirty point eight percent to twenty-seven point four. PortfolioGuard
surfaces that trade-off and explicitly states that historical performance does not
predict future results.”

Open **Calculation assumptions** and **Limitations**. Mention fees, taxes,
contribution room, survivorship bias, and fictional baskets.

## 3:20–4:05 — Grounded Bedrock explanation and governance

**Say:**

“Only Lambda can generate financial values. Bedrock receives a closed evidence
packet and explains the result in words. Its response fails validation if it cites
an unknown evidence ID or tries to introduce a number.”

Point to governance findings.

Switch briefly between personas:

- Mateo exposes the lack of company-level ESG controversy evidence.
- Robert exposes the conflict between the same proposal and his short fictional
  horizon and capital-preservation objective.

**Say:**

“The calculations stay consistent, but governance changes with the investor
context instead of manufacturing a different market history.”

## 4:05–4:35 — Prove the AWS path

Open CloudWatch Logs.

**Say:**

“Here is the same analysis ID and AWS Lambda request ID in CloudWatch. The S3 source
list in the response includes version IDs or ETags, so this result is reproducible.
IAM limits the backend to this function and the approved Bedrock resources.”

Show one `calculation_started` and matching `calculation_completed` structured log.
Do not expose account identifiers or credentials.

## 4:35–5:00 — Close

Return to the answer.

**Say:**

“PortfolioGuard AI demonstrates a safer pattern for agentic financial decision
support: purposeful delegation, deterministic cloud tools, visible governance, and
language generation constrained by evidence. For this fictional scenario, measured
historical risk declined, but so did historical return. The user sees both—and can
inspect exactly why.”

## Failure recovery

If AWS fails during the live demo, keep the honest error state visible and explain
that local placeholders are intentionally disabled. Then show a timestamped prior
response that is clearly labeled as a previous real AWS run, followed by its
matching CloudWatch entries. Never present a fixture or mocked response as live.
