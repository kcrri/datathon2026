# PortfolioGuard AI

***Team 62 · AlphaForge AI Datathon 2026***

PortfolioGuard AI is an evidence-backed decision-support prototype for fictional
TFSA and RRSP portfolios. It delegates a scenario through a real agent hierarchy,
calculates every financial metric deterministically in AWS Lambda from versioned
S3 data, applies governance rules, and asks Amazon Bedrock to explain only the
verified evidence.

> Simulation only. Fictional portfolios. Not financial advice. No real trades.

## Demo scenario

> Would moving 20% of my TFSA from my growth strategy into my dividend strategy reduce my risk?

The reviewed starter data produces a deterministic historical result: annualized
volatility falls from 18.48% to 13.71%, maximum drawdown improves from -19.72% to
-15.53%, and historical annualized return falls from 30.80% to 27.42%. The lower
measured risk therefore comes with a historical return trade-off. These figures
are observations from the stated 2023-11-13 through 2026-11-12 window, not forecasts.

## Architecture

```text
Next.js dashboard → FastAPI → Global Orchestrator
                                ├─ TFSA / RRSP Account Agent
                                │    └─ Growth / Dividend / Momentum /
                                │       Capital Preservation Strategy Agents
                                │          └─ AWS Lambda → versioned Amazon S3 data
                                ├─ deterministic Governance Agent
                                └─ Explainability Agent → Amazon Bedrock Converse API

AWS Lambda + FastAPI expose correlated execution details to CloudWatch and the UI.
```

The execution trace makes delegation observable. Strategy and language-model
agents cannot create financial values; only the deterministic Lambda does so.

## Current status

- Local vertical slice, agent hierarchy, deterministic engine, dashboard, IaC,
  manifest generation, CI, and local tests are implemented.
- AWS SAM defines a private encrypted/versioned bucket, bounded calculation
  Lambda, CloudWatch log group, and one unnamed least-privilege Lambda execution
  role for the restricted workshop.
- The reviewed AWS stack is deployed in `us-east-1`: private versioned S3 storage,
  deterministic Lambda, least-privilege execution role, and CloudWatch log group.
  The six-file dataset and manifest are uploaded with verified SHA-256 checksums;
  one bounded Lambda acceptance run matched the local engine exactly, while
  Bedrock has not yet been invoked.
- Advanced VaR/CVaR, broader momentum analytics, and monitoring dashboards remain
  intentionally deferred until the primary scenario is proven end to end.

Project documentation:

- [Living implementation plan](docs/IMPLEMENTATION_PLAN.md)
- [Technical documentation](docs/TECHNICAL_DOCUMENTATION.md)
- [One-page summary](docs/ONE_PAGER.md)
- [Five-minute demo script](docs/DEMO_SCRIPT.md)
- [AWS deployment approval gate](docs/AWS_DEPLOYMENT_GATE.md)

## Local development

Prerequisites: Python 3.12+, Node.js 22+, and npm.

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
pytest -m "not integration" -q
uvicorn app.main:app --reload
```

In another terminal:

```bash
cd frontend
npm ci
cp .env.example .env.local
npm run dev
```

The API runs at `http://localhost:8000`; the landing page runs at
`http://localhost:3000`, and the demo workspace is at
`http://localhost:3000/dashboard`. Selecting a persona on the landing page and
choosing **Analyze with live AWS** opens the workspace and starts the approved
TFSA comparison. The workspace deliberately shows no substitute metrics when
live AWS is unavailable.

FastAPI loads `backend/.env` for local development without overriding variables
already supplied by the shell or deployment environment.

## Environment configuration

Backend configuration is documented in `backend/.env.example`:

| Variable | Workshop value | Purpose |
| --- | --- | --- |
| `AWS_REGION` | `us-east-1` | Lambda, S3, and Bedrock source Region |
| `AWS_PROFILE` | `portfolioguard-workshop` | Local AWS named profile using temporary Workshop Studio credentials |
| `BEDROCK_MODEL_ID` | `us.amazon.nova-lite-v1:0` | Amazon Nova Lite US inference profile |
| `LAMBDA_FUNCTION_NAME` | `portfolioguard-workshop-financial-tools` | Deterministic calculation function |
| `S3_BUCKET` | CloudFormation `DataBucketName` output | Versioned dataset bucket used by deployment helpers |
| `DATA_PREFIX` | `starter/v1` | Approved dataset prefix reported by the readiness endpoint |
| `ENGINE` | unset (`lambda`) | `lambda` runs every calculation in the Lambda against S3; `local` is for tests and offline work only |
| `FRONTEND_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | Comma-separated browser origins allowed to call FastAPI |

The frontend uses one API base URL, `NEXT_PUBLIC_API_URL`, defaulting to
`http://localhost:8000` in `frontend/.env.example`. The app workspace uses that
same connection for readiness, conversational actions, accounts, Lambda-backed
analysis, and Bedrock-backed explanations. Keep `.env` and `.env.local` files outside Git. Never place
temporary access keys or session tokens in environment example files; configure the
named profile using Workshop Studio's secure temporary-credential workflow.

## Verification

```bash
cd backend && .venv/bin/pytest -m "not integration" -q
python3 -m unittest discover -s lambda/tests -v
cd frontend && npm run lint && npm run build
cd .. && SAM_CLI_TELEMETRY=0 sam validate --lint --template-file infra/template.yaml
```

After an approved AWS deployment, run the opt-in acceptance test with a secure AWS
profile and the deployed outputs:

```bash
cd backend
RUN_AWS_INTEGRATION=1 \
AWS_PROFILE=portfolioguard-workshop \
AWS_REGION=us-east-1 \
LAMBDA_FUNCTION_NAME=portfolioguard-workshop-financial-tools \
BEDROCK_MODEL_ID=us.amazon.nova-lite-v1:0 \
.venv/bin/pytest -m integration -q
```

## Data controls

- Returns use adjusted close.
- USD listings convert to CAD using the latest USD/CAD observation on or before
  each asset date.
- The portfolio calendar is the intersection of every holding's available dates.
- The initial comparison uses constant weights with daily rebalancing.
- Lambda verifies the S3 dataset ID, prefix, file sizes, and SHA-256 checksums
  against the committed manifest before calculating.
- S3 object version IDs or ETags are returned as metric provenance.
- Duplicate dates, non-positive prices/FX, missing assets, insufficient common
  history, invalid weights, and impossible shifts fail closed.
- Macro reference dates are not used in backtests until publication-date handling
  is available.

The immutable local manifest is
[data/manifests/starter-v1.json](data/manifests/starter-v1.json).

## Repository map

- `frontend/` — Next.js dashboard
- `backend/` — FastAPI, hierarchy, governance, and Bedrock client
- `lambda/financial_tools/` — deterministic S3-backed calculations
- `infra/template.yaml` — deployed AWS SAM/CloudFormation template
- `scripts/` — manifest and S3 upload helpers
- `docs/` — plan, technical documentation, one-pager, demo script, and decisions
- `hackathon_info/` — challenge documents and reviewed starter dataset

The original project Wiki remains available for historical context, while the
in-repository plan is authoritative for the approved implementation architecture.
