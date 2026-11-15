import type { ChatResponse } from "@/lib/api";
import { useLanguage, type MessageKey } from "@/i18n";
import { fmtCad, fmtNumber } from "@/i18n/format";
import { agentName } from "@/i18n/labels";
import { plain } from "@/lib/plainLanguage";
import { ProposalCard } from "./ProposalCard";
import { TradeCheckBody } from "./TradeCheckBody";

export type ChatMessage =
  | { role: "user"; text: string }
  | { role: "assistant"; data: ChatResponse; resolved?: boolean };

function Rich({ text }: { text: string }) {
  return (
    <div className="space-y-2 whitespace-pre-wrap leading-relaxed">
      {text.split("\n\n").map((block, i) => (
        <p key={i}>
          {block.split(/(\*\*[^*]+\*\*)/g).map((part, j) =>
            part.startsWith("**") ? (
              <b key={j} className="font-semibold text-brand-700">
                {part.slice(2, -2)}
              </b>
            ) : (
              part
            )
          )}
        </p>
      ))}
    </div>
  );
}

export function Message({
  msg,
  busy,
  onSuggestion,
  onApprove,
  onReject,
}: {
  msg: ChatMessage;
  busy: boolean;
  onSuggestion: (s: string) => void;
  onApprove: (id: string, risk: string) => void;
  onReject: (id: string) => void;
}) {
  const { t } = useLanguage();
  if (msg.role === "user") {
    return (
      <div className="ml-auto max-w-[80%] rounded-lg rounded-br-md bg-brand-500 px-4 py-2 text-white">{msg.text}</div>
    );
  }
  const d = msg.data;
  const metrics = Object.entries(d.metrics ?? {});
  return (
    <div className="flex gap-3">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-brand-100 text-sm font-semibold text-brand-700">
        {t("chat.avatar")}
      </div>
      <div className="min-w-0 max-w-[90%] flex-1 rounded-lg rounded-tl-md bg-white px-4 py-3 ring-1 ring-slate-200">
        <Rich text={d.answer} />

        {metrics.length > 0 && (
          <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
            {metrics.map(([k, v]) => (
              <div key={k} className="rounded-lg bg-brand-50 p-2">
                <div className="text-xs text-slate-500">{k}</div>
                <div className="font-mono text-sm font-semibold text-brand-800">{v}</div>
              </div>
            ))}
          </div>
        )}

        {d.trade_check && (
          <div className="mt-3 rounded-md bg-slate-50 p-4 ring-1 ring-slate-200">
            <TradeCheckBody check={d.trade_check} headlines={d.headlines} />
            <p className="mt-2 text-[11px] text-slate-500">
              {d.trade_check.computed_by === "aws-lambda" ? t("chat.computed.aws") : t("chat.computed.local")}
            </p>
            {d.persona_fit && (
              <div className="mt-4 rounded-md bg-white p-3 ring-1 ring-slate-200">
                <div className="text-xs font-semibold text-slate-700">{t("fit.title", { name: d.persona_fit.persona.name })}</div>
                <div className="mt-0.5 text-[11px] text-slate-500">
                  {d.persona_fit.persona.horizon_text
                    ? t("fit.profileText", { risk: d.persona_fit.persona.risk, horizon: d.persona_fit.persona.horizon_text })
                    : t("fit.profile", { risk: d.persona_fit.persona.risk, years: d.persona_fit.persona.horizon_years })}
                </div>
                <div className="mt-2 flex items-start gap-2">
                  <span
                    className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-semibold ${
                      d.persona_fit.stance === "fits"
                        ? "bg-emerald-100 text-emerald-800"
                        : d.persona_fit.stance === "wait"
                          ? "bg-sky-100 text-sky-800"
                          : "bg-amber-100 text-amber-800"
                    }`}
                  >
                    {t(`fit.stance.${d.persona_fit.stance}` as MessageKey)}
                  </span>
                  <p className="text-sm font-medium text-slate-900">{d.persona_fit.headline}</p>
                </div>
                {d.persona_fit.why.length > 0 && (
                  <>
                    <div className="mt-2 text-xs font-semibold text-slate-600">{t("fit.why")}</div>
                    <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-slate-700">
                      {d.persona_fit.why.map((line) => (
                        <li key={line}>{line}</li>
                      ))}
                    </ul>
                  </>
                )}
              </div>
            )}
            {d.position && (
              <div className="mt-4 rounded-md bg-white p-3 ring-1 ring-slate-200">
                <div className="text-xs font-semibold text-slate-700">{t("chat.position.title", { ticker: d.position.ticker })}</div>
                {d.position.holds || d.position.action === "buy" ? (
                  <>
                    <div className="mt-2 grid gap-3 sm:grid-cols-3">
                      <div className="text-xs text-slate-600">
                        {t("holdings.sharesLabel")}
                        <div className="mt-1 text-sm font-medium text-slate-900">{fmtNumber(d.position.sample_qty, 2)}</div>
                      </div>
                      <div className="text-xs text-slate-600">
                        {t("holdings.amountLabel")}
                        <div className="mt-1 text-sm font-medium text-slate-900">{fmtNumber(d.position.sample_amount_cad, 2)}</div>
                      </div>
                      <div className="text-xs text-slate-600">
                        {t("holdings.priceHold")}
                        <div className="mt-1 text-sm font-medium text-slate-900">
                          {t("holdings.priceHoldValue", { price: fmtNumber(d.position.price, 2), owned: fmtNumber(d.position.shares_held, 2) })}
                        </div>
                      </div>
                    </div>
                    <p className="mt-2 text-xs text-slate-500">
                      {t("holdings.tradeSummary", { pct: fmtNumber(d.position.portfolio_pct, 1), cash: fmtCad(d.position.cash_after_cad) })}{" "}
                      {t("chat.position.sample")}
                      {!d.position.affordable && ` ${t("chat.position.unaffordable")}`}
                    </p>
                  </>
                ) : (
                  <p className="mt-2 text-xs text-slate-500">{t("chat.position.notHeld", { ticker: d.position.ticker })}</p>
                )}
              </div>
            )}
          </div>
        )}

        {d.proposal && !msg.resolved && (
          <ProposalCard
            proposal={d.proposal}
            disabled={busy}
            onApprove={(risk) => onApprove(d.proposal!.id, risk)}
            onReject={() => onReject(d.proposal!.id)}
          />
        )}

        {d.suggestions?.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {d.suggestions.map((s) => (
              <button
                key={s}
                onClick={() => onSuggestion(s)}
                disabled={busy}
                className="rounded-full bg-white px-3 py-1 text-sm text-link ring-1 ring-slate-300 transition hover:bg-slate-50 disabled:opacity-40"
              >
                {s}
              </button>
            ))}
          </div>
        )}

        {d.trace?.length > 0 && (
          <details className="mt-3 text-xs text-slate-500">
            <summary className="cursor-pointer text-brand-600 hover:text-brand-700">{t("chat.howIGotThis")}</summary>
            <ol className="mt-2 space-y-1">
              {d.trace.map((step, i) => (
                <li key={i}>
                  {i + 1}. <b className="text-slate-700">{agentName(step.agent)}</b>: {plain(step.action)}
                  {step.runtime && (
                    <span title="Amazon Bedrock AgentCore runtime that ran this step" className="ml-1.5 whitespace-nowrap rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[10px] text-slate-600">
                      AWS · {step.runtime}
                    </span>
                  )}
                </li>
              ))}
            </ol>
            {d.sources?.length > 0 && (
              <ul className="mt-2 list-disc pl-4">
                {d.sources.map((s) => (
                  <li key={s}>{plain(s)}</li>
                ))}
              </ul>
            )}
          </details>
        )}

        {d.warnings?.length > 0 && <p className="mt-2 text-xs text-slate-400">{plain(d.warnings.join(" "))}</p>}
      </div>
    </div>
  );
}
