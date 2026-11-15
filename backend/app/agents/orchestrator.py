from __future__ import annotations

import re
import unicodedata
from typing import Any, Callable, Dict, List
from uuid import uuid4

from app.agents.accounts import RRSPAccountAgent, TFSAAccountAgent
from app.agents.explainability import ExplainabilityAgent
from app.agents.governance import GovernanceAgent
from app.agents.profile import get_persona
from app.agents import account_creation, knowledge, profile, trade_intent
from app.agents.orchestrator_text import DISCLAIMER
from app.agents import trade_pipeline
from app import i18n, store
from app.profiles import PROFILES
from app.agents.signals import macro
from app.domain.models import (
    AnalysisRequest,
    AnalysisResponse,
    MetricEvidence,
    PerformancePoint,
    TraceStep,
)
from app.domain.presets import PERSONAS, STRATEGY_HOLDINGS
from app.services import sell_guard_service
from app.services.lambda_tools import invoke



ACCOUNT_AGENTS = {
    "TFSA": TFSAAccountAgent,
    "RRSP": RRSPAccountAgent,
}


class GlobalOrchestrator:
    """Coordinate observable agent delegation and real AWS tool calls."""

    def __init__(
        self,
        financial_tool: Callable[[str, Dict], Dict] = invoke,
        explainability_agent: ExplainabilityAgent | None = None,
    ):
        self.financial_tool = financial_tool
        self.explainability_agent = explainability_agent or ExplainabilityAgent()
        self.governance_agent = GovernanceAgent()

    def run(self, request: AnalysisRequest) -> AnalysisResponse:
        analysis_id = str(uuid4())
        persona = get_persona(request.persona_id)
        account_agent = ACCOUNT_AGENTS[request.account_type]()
        account_finding = account_agent.plan(request.model_dump(mode="json"))
        strategy_findings = account_agent.delegate(request)
        delegated_names = [finding.agent for finding in strategy_findings]

        trace = [
            TraceStep(
                step_id="orchestrator.plan",
                agent="global_orchestrator",
                action="Resolve persona, account, and requested scenario",
                delegated_to=[account_agent.name],
                details={
                    "persona": persona["name"],
                    "account_type": request.account_type,
                },
            ),
            TraceStep(
                step_id="account.delegate",
                parent_id="orchestrator.plan",
                agent=account_agent.name,
                action="Delegate the account scenario to relevant strategy agents",
                delegated_to=delegated_names,
            ),
        ]
        for index, finding in enumerate(strategy_findings, start=1):
            trace.append(
                TraceStep(
                    step_id=f"strategy.{index}",
                    parent_id="account.delegate",
                    agent=finding.agent,
                    action=finding.summary,
                    details={"requested_operations": finding.requested_operations},
                )
            )

        lambda_payload = request.model_dump(mode="json")
        lambda_payload.update(
            {
                "analysis_id": analysis_id,
                "strategy_holdings": STRATEGY_HOLDINGS,
            }
        )
        calculation = self.financial_tool("compare_strategy_shift", lambda_payload)
        metrics = [MetricEvidence.model_validate(item) for item in calculation["metrics"]]
        evidence_ids = [metric.evidence_id for metric in metrics]
        trace.append(
            TraceStep(
                step_id="tool.financial_lambda",
                parent_id="account.delegate",
                agent="aws_financial_tools",
                action="Calculate current and proposed portfolio metrics from verified market data",
                evidence_ids=evidence_ids,
                details={"aws_request_id": calculation.get("aws_request_id", "unknown")},
            )
        )

        governance = self.governance_agent.evaluate(
            request, calculation["conclusion"], metrics
        )
        trace.append(
            TraceStep(
                step_id="governance.review",
                parent_id="orchestrator.plan",
                agent=self.governance_agent.name,
                action="Apply simulation, profile, evidence, and trade-off controls",
                evidence_ids=sorted(
                    {
                        evidence_id
                        for finding in governance
                        for evidence_id in finding.evidence_ids
                    }
                ),
            )
        )

        explanation = self.explainability_agent.explain(
            request.question,
            calculation["conclusion"],
            metrics,
            governance,
            calculation["assumptions"],
            calculation["limitations"],
            language=i18n.normalize(request.language),
        )
        trace.append(
            TraceStep(
                step_id="explainability.synthesize",
                parent_id="governance.review",
                agent=self.explainability_agent.name,
                action="Use an AI model to write an explanation grounded in the verified evidence",
                evidence_ids=explanation.evidence_ids,
                details={"model_id": explanation.model_id},
            )
        )

        return AnalysisResponse(
            analysis_id=analysis_id,
            question=request.question,
            persona_id=request.persona_id,
            account_type=request.account_type,
            answer=explanation.answer,
            conclusion=calculation["conclusion"],
            current_allocations=calculation["current_allocations"],
            proposed_allocations=calculation["proposed_allocations"],
            metrics=metrics,
            performance_series=[
                PerformancePoint.model_validate(item)
                for item in calculation["performance_series"]
            ],
            agent_findings=[account_finding, *strategy_findings],
            governance=governance,
            trace=trace,
            assumptions=calculation["assumptions"],
            limitations=[*calculation["limitations"], *explanation.limitations],
            data_sources=calculation["data_sources"],
            model_id=explanation.model_id,
        )

    def chat(
        self, user_id: str, message: str, lang: str = "en", holdings_persona: str | None = None, live: bool = False
    ) -> Dict[str, Any]:
        """Handle the conversational account and knowledge-base flow."""
        lang = i18n.normalize(lang)
        p = lambda en, fr: i18n.pick(lang, en, fr)  # noqa: E731  (en/fr picker)
        trace: List[Dict[str, Any]] = [
            {"agent": "Global Orchestrator", "action": p("detect intent", "détecter l'intention")}
        ]
        disclaimer = p(DISCLAIMER, "Simulation seulement. Ce ne sont pas des conseils financiers.")
        if self._is_create_intent(message):
            trace.append(
                {
                    "agent": "Investor Profile Agent",
                    "action": p(
                        "read horizon and risk, recommend account",
                        "lire l'horizon et le risque, recommander un compte",
                    ),
                }
            )
            recommendation = profile.recommend(message, lang)
            if recommendation.get("needs") == "horizon":
                return self._reply(
                    p("What's the time horizon for this account?", "Quel est l'horizon de placement de ce compte ?"),
                    trace,
                    suggestions=[
                        p("Create a short-term account", "Créer un compte à court terme"),
                        p("Create a mid-term account", "Créer un compte à moyen terme"),
                        p("Create a long-term account", "Créer un compte à long terme"),
                    ],
                )
            trace.append(
                {
                    "agent": "Governance Agent",
                    "action": p(
                        "check fit with profile, require user approval",
                        "vérifier l'adéquation avec le profil, exiger l'approbation de l'utilisateur",
                    ),
                }
            )
            action_id = store.new_id()
            store.PENDING[action_id] = {"user_id": user_id, "type": "create_account", "payload": recommendation}
            return self._reply(
                p(
                    f"I recommend a **{recommendation['account_type_label']}** account for "
                    f"{recommendation['horizon_label'].lower()}. {recommendation['reason']} "
                    f"Suggested risk: **{recommendation['risk_label']}** (like {recommendation['persona']}). "
                    "You can change the risk before approving.",
                    f"Je recommande un compte **{recommendation['account_type_label']}** pour "
                    f"un {recommendation['horizon_label'].lower()}. {recommendation['reason']} "
                    f"Risque suggéré : **{recommendation['risk_label']}** (comme {recommendation['persona']}). "
                    "Vous pouvez modifier le risque avant d'approuver.",
                ),
                trace,
                proposal={"id": action_id, "type": "create_account", **recommendation},
            )

        trade = trade_intent.parse(message)
        if trade:
            return self._trade_check_reply(trade[0], trade[1], trace, lang, holdings_persona, live, user_id)

        entry = knowledge.match(message, lang)
        if entry:
            routed = i18n.agent_names(lang, entry["agents"])
            trace[0]["action"] = p(
                f"detect intent: question ({entry['id']}), route to {routed}",
                f"détecter l'intention : question ({entry['id']}), acheminer vers {routed}",
            )
            extra: Dict[str, Any] = {
                "metrics": {},
                "sources": [p(f"Knowledge base: {entry['id']}", f"Base de connaissances : {entry['id']}")],
                "warnings": [],
            }
            answer = entry["answer"]
            for agent in entry["agents"]:
                if agent == "Macro Signal Agent":
                    trace.append(
                        {
                            "agent": agent,
                            "action": p(
                                "read yield curve and unemployment (Market Data)",
                                "lire la courbe des taux et le chômage (données de marché)",
                            ),
                        }
                    )
                    signal = macro.recession_signals(lang)
                    extra["metrics"].update(signal.get("metrics", {}))
                    extra["sources"] += signal.get("sources", [])
                    extra["warnings"] += signal.get("warnings", [])
                    if signal.get("notes"):
                        answer += "\n\n" + "\n".join(f"- {note}" for note in signal["notes"])
                elif agent == "Risk Agent":
                    accounts = store.accounts(user_id)
                    trace.append(
                        {
                            "agent": agent,
                            "action": p(
                                "map exposure to your accounts" if accounts else "no accounts yet",
                                "relier l'exposition à vos comptes" if accounts else "aucun compte pour l'instant",
                            ),
                        }
                    )
                    if accounts:
                        header = p("Your accounts:", "Vos comptes :")
                        short = p(
                            ", shortest horizon, most exposed to a near-term downturn",
                            ", horizon le plus court, le plus exposé à un repli à court terme",
                        )
                        handled = p("handled by", "géré par")
                        answer += f"\n\n{header}\n" + "\n".join(
                            f"- {i18n.account_name(lang, account['name'])} "
                            f"({i18n.risk_label(lang, account['risk_label'])}): {handled} "
                            f"{i18n.horizon_agent(lang, account['horizon_agent'])}"
                            + (short if account["horizon"] == "short" else "")
                            for account in accounts
                        )
                else:
                    trace.append(
                        {"agent": agent, "action": p("answer from knowledge base", "répondre à partir de la base de connaissances")}
                    )
            trace.append(
                {"agent": "Explainability Agent", "action": p("attach sources and limits", "joindre les sources et les limites")}
            )
            extra["warnings"].append(disclaimer)
            return self._reply(answer, trace, **extra)
        return self._reply(
            p(
                "I don't have that in my knowledge base yet. Try one of these:",
                "Je n'ai pas encore cette information dans ma base de connaissances. Essayez l'une de ces questions :",
            ),
            trace,
            suggestions=knowledge.suggestions(lang) + [p("Create a short-term account", "Créer un compte à court terme")],
        )

    def approve(self, action_id: str, risk: str | None = None, lang: str = "en") -> Dict[str, Any]:
        lang = i18n.normalize(lang)
        p = lambda en, fr: i18n.pick(lang, en, fr)  # noqa: E731
        action = store.PENDING.pop(action_id, None)
        if action is None:
            return self._reply(p("That proposal has expired.", "Cette proposition a expiré."), [])
        payload = dict(action["payload"])
        if risk in PROFILES:
            payload["risk"] = risk
        account = account_creation.create(action["user_id"], payload)
        name = i18n.account_name(lang, account["name"])
        label = i18n.risk_label(lang, account["risk_label"])
        agent = i18n.horizon_agent(lang, account["horizon_agent"])
        strategies = ", ".join(i18n.strategies(lang, account["strategies"]))
        return self._reply(
            p(
                f"Created **{name}** ({label}). It's managed by the {agent} with {strategies} strategies.",
                f"**{name}** ({label}) a été créé. Il est géré par l'{agent} avec les stratégies {strategies}.",
            ),
            [
                {"agent": "Governance Agent", "action": p("user approved", "approuvé par l'utilisateur")},
                {"agent": "Account Creation Agent", "action": p(f"created {name}", f"{name} créé")},
                {"agent": account["horizon_agent"], "action": p(f"assigned {strategies}", f"stratégies attribuées : {strategies}")},
            ],
            warnings=[p(DISCLAIMER, "Simulation seulement. Ce ne sont pas des conseils financiers.")],
        )

    def reject(self, action_id: str, lang: str = "en") -> Dict[str, Any]:
        lang = i18n.normalize(lang)
        store.PENDING.pop(action_id, None)
        return self._reply(
            i18n.pick(lang, "No problem, nothing was created.", "Aucun problème, rien n'a été créé."),
            [{"agent": "Global Orchestrator", "action": i18n.pick(lang, "user declined", "refusé par l'utilisateur")}],
        )

    @staticmethod
    def _is_create_intent(text: str) -> bool:
        folded = "".join(
            c for c in unicodedata.normalize("NFD", text.lower()) if unicodedata.category(c) != "Mn"
        )
        return bool(
            re.search(r"(create|open|new|start|set up|creer|ouvrir|nouveau|nouvelle|ouverture|demarrer)", folded)
            and re.search(r"account|compte", folded)
        )

    def _trade_check_reply(
        self, action: str, ticker: str, trace: List[Dict[str, Any]], lang: str, persona_id: str | None = None, live: bool = False,
        user_id: str | None = None,
    ) -> Dict[str, Any]:
        """Answer "should I sell/buy X?" by running Intake, Market, Classifier and Explainer in order."""
        p = lambda en, fr: i18n.pick(lang, en, fr)  # noqa: E731
        verb = p("selling" if action == "sell" else "buying", "la vente" if action == "sell" else "l'achat")
        fr_check = "vérification de vente" if action == "sell" else "vérification d'achat"
        trace[0]["action"] = p(
            f"detect intent: {action} check for {ticker}, run Intake, Market, Classifier and Explainer in order",
            f"détecter l'intention : {fr_check} pour {ticker}, exécuter Intake, Market, Classifier et Explainer dans l'ordre",
        )
        warnings = [p(DISCLAIMER, "Simulation seulement. Ce ne sont pas des conseils financiers.")]
        try:
            outcome = trade_pipeline.run(action, ticker, persona_id, None, live, lang, message=None, user_id=user_id)
        except LookupError:
            return self._reply(
                p(
                    f"I can check {verb} {ticker} once the live market is loaded. Refresh the market on the Holdings tab, then ask again.",
                    f"Je peux vérifier {verb} de {ticker} une fois le marché en direct chargé. Actualisez le marché dans l'onglet Titres, puis redemandez.",
                ),
                trace,
                warnings=warnings,
            )
        except ValueError:
            return self._reply(
                p(
                    f"I don't have market data for {ticker} in this simulation.",
                    f"Je n'ai pas de données de marché pour {ticker} dans cette simulation.",
                ),
                trace,
                warnings=warnings,
            )
        reply = trade_pipeline.chat_reply(action, ticker, outcome, lang)
        reply["trace"] = trace + outcome["trace"]
        return reply

    @staticmethod
    def _reply(answer: str, trace: List[Dict[str, Any]], **kwargs: Any) -> Dict[str, Any]:
        return {
            "answer": answer,
            "trace": trace,
            "metrics": kwargs.get("metrics", {}),
            "sources": kwargs.get("sources", []),
            "warnings": kwargs.get("warnings", []),
            "proposal": kwargs.get("proposal"),
            "suggestions": kwargs.get("suggestions", []),
            "trade_check": kwargs.get("trade_check"),
            "position": kwargs.get("position"),
            "headlines": kwargs.get("headlines"),
            "persona_fit": kwargs.get("persona_fit"),
        }
