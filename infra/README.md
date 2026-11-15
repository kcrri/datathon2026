# AWS infrastructure

`template.yaml` defines the deployed first PortfolioGuard AI vertical slice for the
Polyfinances Workshop Studio account in `us-east-1`:

- Private, encrypted, versioned S3 data bucket
- Deterministic Python Lambda with read-only access to the data bucket
- Fourteen-day Lambda log retention in CloudWatch Logs
- One unnamed, least-privilege Lambda execution role scoped to the dataset prefix
  and function log group
- Review-only least-privilege policy documents for US Nova Lite caller access

The template does not host the frontend or FastAPI service. During the first slice,
the local FastAPI backend uses Workshop Studio temporary credentials to call the
deployed Lambda and `us.amazon.nova-lite-v1:0`.

## Market data and headline scoring in AWS

All market data lives in S3 and all calculation and classification runs in the Lambda, so
every user gets the same answers and nothing depends on a developer machine.

| What | Where | Notes |
| --- | --- | --- |
| Simulated prices and headlines | `s3://<bucket>/simulated/v1/{current,marketchange}/` | `prices.csv` and `news.csv` are checked against `manifest.json` (sha256) on every load |
| Scored headlines | `.../news_scored.csv` | written only by the Lambda; the role may `PutObject` on those two keys and nothing else |
| Starter dataset and asset universe | `s3://<bucket>/starter/v1/` | unchanged |
| Trade check, portfolio, sentiment summary | Lambda operations `trade_check`, `portfolio_snapshot`, `sentiment_summary`, `market_status` | the backend sends the investor presets and a `live` flag; it keeps no market state |
| Headline classification | Lambda operation `score_headlines`, Bedrock Nova Lite | run with `scripts/score_news_sentiment.py` |

Changes this needs (each one needs the usual change-set review and approval):

1. Upload the simulated data: `S3_BUCKET=<bucket> scripts/upload_market_data.sh`
2. Update the stack: new S3 read and write statements, `bedrock:InvokeModel` for Nova Lite,
   timeout 30 s to 120 s (headline scoring), reserved concurrency 2 to 5, three environment
   variables (`MARKET_PREFIX`, `MARKET_DATASET_ID`, `BEDROCK_MODEL_ID`).
3. Optionally score the headlines in the Lambda: `scripts/score_news_sentiment.py`

The backend defaults to `ENGINE=lambda` and fails with a clear error if the Lambda is not
configured; it never falls back to local files. `ENGINE=local` is for tests and offline work.
Hyperparameter tuning and the backtest (`scripts/tune_thresholds.py`,
`scripts/backtest_sentiment.py`) stay local by design.

## Agents on Amazon Bedrock AgentCore

The orchestrator and every agent run in an AgentCore Runtime in this account (`infra/agents.yaml`,
a separate stack `portfolioguard-workshop-agents`), not on a laptop. The local FastAPI backend
only signs and forwards requests (`AGENT_RUNTIME_ARN`).

Why AgentCore and not Bedrock Agents: the workshop role has an explicit deny on
`bedrock:CreateAgent`, so managed Bedrock Agents cannot be created here.

### The five agents and where each one runs

| Agent | Role | Runs in | Uses |
| --- | --- | --- | --- |
| Orchestrator | Routes the message with a language model, calls the agents in order, passes evidence IDs between them, records the execution trace. No calculation. | AgentCore runtime | Bedrock (routing), FastAPI gateway |
| Intake | Turns who is asking into a low, mid or high risk persona; an RRSP lowers the risk one step. Reads a self-description with a model when no investor is selected. | AgentCore runtime | Bedrock (only for free-text descriptions), persona and risk presets |
| Market | Compares the market before and after the refresh: price move, volume, how many tickers fell together. | Lambda operation `market_agent` | S3 CSVs |
| Classifier | Labels the move market-driven or company-driven; sentiment label and fundamental, emotion and hype scores. | Lambda operation `classifier_agent` | Deterministic sell guard, headlines pre-scored by Bedrock |
| Explainer | Writes the pop-up warning, then the chat detail, citing only the Classifier's evidence IDs. Output is validated (no digits, no predictions, no advice, cited IDs must exist); one or two corrective retries, then fixed wording. | AgentCore runtime | Bedrock Converse |

Account creation, the FAQ and macro answers stay rule-based; the Orchestrator hands those over.

| Piece | Detail |
| --- | --- |
| Package | `scripts/build_agent_package.sh --upload` zips `agentcore/main.py`, `backend/app` (without the web API layer) and ARM64 dependencies, and uploads it to `s3://<bucket>/agents/` |
| Runtime | `AWS::BedrockAgentCore::Runtime`, Python 3.12, code from S3, HTTP on port 8080 (`/ping`, `/invocations`) |
| Role | `AgentRuntimeRole`: invoke the financial-tools Lambda, read the code and two reference files in S3, invoke Nova Lite, write logs and metrics |
| Updating the agents | build and upload a new package, update the stack with the new `CodeVersionId`, then change `AGENT_SESSION_SUFFIX` in the backend `.env`: a session keeps running the code it started on until it goes idle |
| Switches | `LLM_ROUTING` (`on` / `off`) and `EXPLAINER` (`llm` / `rules`) in the runtime's environment; `off` and `rules` use the rule-based router and the fixed wording |
| Logs | CloudWatch `/aws/bedrock-agentcore/runtimes/<runtime id>-DEFAULT` (one `agent_action` line per request); the Lambda logs one line per `market_agent` and `classifier_agent` call |

AgentCore only accepts ARM64 binaries. Requests are signed with AWS credentials, so a browser
cannot call the runtime directly; the backend gateway does.

## Deployment status and next gate

The exact reviewed change set was approved and reached `CREATE_COMPLETE` on
2026-11-14. Before any subsequent update, repeat change-set review and obtain user
approval. The remaining approval gates are:

1. A bounded Bedrock Nova Lite acceptance invocation
2. Any additional Lambda invocation
3. Any dataset replacement, CloudFormation update, or cleanup

Read-only inspection found no suitable existing application execution role. IAM
simulation confirms that `WSParticipantRole` may create, configure, pass, and later
delete the unnamed role in this template. Deployment therefore requires
`CAPABILITY_IAM`; it still requires explicit user approval and change-set review.

No temporary credential values belong in `.env` files. Configure the Workshop
Studio credentials locally using the standard AWS credential chain and expose only
the named profile to the application.

See `docs/AWS_DEPLOYMENT_GATE.md` for the readiness checklist, complete resource
inventory, IAM requirements, cost estimate, approvals, and cleanup plan.
