"use client";

import { useState } from "react";
import { AllocationComparison } from "@/components/AllocationComparison";
import { useLanguage } from "@/i18n";
import { fmtPercent } from "@/i18n/format";
import { governanceMessage, governanceTitle, noteText, sourceLabel } from "@/i18n/labels";
import { plain } from "@/lib/plainLanguage";
import { MetricCards } from "@/components/MetricCards";
import { PerformanceChart } from "@/components/PerformanceChart";
import { TraceTimeline } from "@/components/TraceTimeline";
import {
  type AnalysisInput,
  type AnalysisResponse,
  type ApiMeta,
} from "@/lib/api";
import {
  PERSONAS,
  STRATEGY_KEYS,
  allocationLabel,
  formatCad,
  proposedAllocations,
  suggestedScenarios,
  type PersonaId,
  type Scenario,
  type StrategyKey,
} from "@/lib/personas";

const MAX_QUESTION_LENGTH = 500;
const fieldClass =
  "w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-200";

function StatusDot({ ready, verified }: { ready: boolean; verified: boolean }) {
  const color = verified ? "bg-emerald-500" : ready ? "bg-amber-400" : "bg-slate-300";
  return <span aria-hidden="true" className={`h-2.5 w-2.5 rounded-full ${color}`} />;
}

export function LiveAnalysisPanel({
  personaId,
  result,
  busy,
  error,
  meta,
  metaError,
  onRun,
}: {
  personaId: PersonaId;
  result: AnalysisResponse | null;
  busy: boolean;
  error: string | null;
  meta: ApiMeta | null;
  metaError: string | null;
  onRun: (input: AnalysisInput) => void;
}) {
  const { t } = useLanguage();
  const persona = PERSONAS.find((item) => item.id === personaId)!;
  const verified = Boolean(result);

  const [from, setFrom] = useState<StrategyKey>(persona.scenario.from);
  const [to, setTo] = useState<StrategyKey>(persona.scenario.to);
  const [amountPct, setAmountPct] = useState(Math.round(persona.scenario.amount * 100));
  // null means the question follows the selected shift; typing in the box takes it over.
  const [typed, setTyped] = useState<string | null>(null);

  const questionFor = (scenario: Scenario) =>
    scenario.from === persona.scenario.from && scenario.to === persona.scenario.to && scenario.amount === persona.scenario.amount
      ? t(`persona.${personaId}.scenario`)
      : t("analysis.form.template", {
          amount: fmtPercent(scenario.amount * 100),
          from: t(`strategy.short.${scenario.from}`),
          to: t(`strategy.short.${scenario.to}`),
        });

  const scenario: Scenario = { from, to, amount: amountPct / 100 };
  const question = typed ?? questionFor(scenario);
  const maxPct = Math.round(persona.allocations[from] * 100);
  const formError = !question.trim()
    ? t("analysis.form.errEmpty")
    : from === to
      ? t("analysis.form.errSame")
      : !Number.isInteger(amountPct) || amountPct < 1 || amountPct > maxPct
        ? t("analysis.form.errAmount", { max: fmtPercent(maxPct), from: t(`strategy.short.${from}`) })
        : null;

  const mentioned = typed
    ? STRATEGY_KEYS.filter((key) => typed.toLowerCase().includes(t(`strategy.short.${key}`).toLowerCase()))
    : [];
  const mismatch = mentioned.length > 0 && (mentioned.some((key) => key !== from && key !== to) || !mentioned.includes(from) || !mentioned.includes(to));

  const pick = (item: Scenario) => {
    setFrom(item.from);
    setTo(item.to);
    setAmountPct(Math.round(item.amount * 100));
    setTyped(null);
  };

  const services = [
    {
      name: t("analysis.chip.service"),
      ready: Boolean(meta),
      verified: Boolean(meta),
      detail: meta ? t("analysis.chip.connected") : metaError ? t("analysis.chip.unavailable") : t("analysis.chip.checking"),
    },
    {
      name: t("analysis.chip.market"),
      ready: verified || (meta?.integrations.dataset.configured ?? false),
      verified,
      detail: verified ? t("analysis.chip.usedInRun") : t("analysis.chip.readyToUse"),
    },
    {
      name: t("analysis.chip.calc"),
      ready: verified || (meta?.integrations.lambda.configured ?? false),
      verified,
      detail: verified ? t("analysis.chip.verifiedRun") : t("analysis.chip.readyToUse"),
    },
    {
      name: t("analysis.chip.ai"),
      ready: verified || (meta?.integrations.bedrock.configured ?? false),
      verified,
      detail: verified ? t("analysis.chip.verifiedRun") : t("analysis.chip.readyToUse"),
    },
  ];

  return (
    <section className="overflow-hidden rounded-lg bg-white ring-1 ring-slate-200">
      <div className="border-b border-slate-200 bg-navy px-5 py-5 text-white sm:px-6">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-brand-300">
            {t("analysis.kicker")}
          </p>
          <h1 className="mt-1 max-w-3xl text-xl font-semibold leading-snug sm:text-2xl">
            {t("analysis.heading")}
          </h1>
          <p className="mt-2 text-sm text-slate-300">
            {t("analysis.sub", { name: persona.name, horizon: t(`persona.${personaId}.horizon`), risk: t(`persona.${personaId}.risk`).toLowerCase() })}
          </p>
        </div>
      </div>

      <div className="space-y-6 p-5 sm:p-6">
        <form
          className="space-y-4 rounded-md bg-slate-50 p-4 ring-1 ring-slate-200"
          onSubmit={(event) => {
            event.preventDefault();
            if (!formError && !busy) onRun({ question: question.trim(), shift: scenario });
          }}
        >
          <div>
            <label htmlFor="analysis-question" className="text-sm font-semibold text-slate-800">
              {t("analysis.form.question")}
            </label>
            <textarea
              id="analysis-question"
              rows={2}
              maxLength={MAX_QUESTION_LENGTH}
              value={question}
              onChange={(event) => setTyped(event.target.value)}
              className={`${fieldClass} mt-1 resize-y`}
            />
            <p className="mt-1 text-xs text-slate-500">{t("analysis.form.questionHint")}</p>
            {mismatch && (
              <p className="mt-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900" role="status">
                {t("analysis.form.warnMismatch")}
              </p>
            )}
          </div>

          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{t("analysis.form.suggestions")}</p>
            <ul className="mt-2 flex flex-wrap gap-2">
              {suggestedScenarios(persona).map((item) => (
                <li key={`${item.from}-${item.to}-${item.amount}`}>
                  <button
                    type="button"
                    onClick={() => pick(item)}
                    className="rounded-full bg-white px-3 py-1.5 text-left text-xs text-slate-700 ring-1 ring-slate-300 transition hover:bg-brand-50 hover:ring-brand-400"
                  >
                    {questionFor(item)}
                  </button>
                </li>
              ))}
            </ul>
          </div>

          <fieldset>
            <legend className="text-sm font-semibold text-slate-800">{t("analysis.form.shift")}</legend>
            <div className="mt-2 grid gap-3 sm:grid-cols-3">
              <label className="text-xs text-slate-600">
                {t("analysis.form.from")}
                <select value={from} onChange={(event) => setFrom(event.target.value as StrategyKey)} className={`${fieldClass} mt-1`}>
                  {STRATEGY_KEYS.map((key) => (
                    <option key={key} value={key}>{t(`strategy.${key}`)} ({fmtPercent(persona.allocations[key] * 100)})</option>
                  ))}
                </select>
              </label>
              <label className="text-xs text-slate-600">
                {t("analysis.form.to")}
                <select value={to} onChange={(event) => setTo(event.target.value as StrategyKey)} className={`${fieldClass} mt-1`}>
                  {STRATEGY_KEYS.map((key) => (
                    <option key={key} value={key}>{t(`strategy.${key}`)} ({fmtPercent(persona.allocations[key] * 100)})</option>
                  ))}
                </select>
              </label>
              <label className="text-xs text-slate-600">
                {t("analysis.form.amount")}
                <input
                  type="number"
                  min={1}
                  max={maxPct}
                  step={1}
                  value={Number.isNaN(amountPct) ? "" : amountPct}
                  onChange={(event) => setAmountPct(event.target.valueAsNumber)}
                  className={`${fieldClass} mt-1`}
                />
              </label>
            </div>
          </fieldset>

          <div className="flex flex-wrap items-center gap-3">
            <button
              type="submit"
              disabled={busy || Boolean(formError)}
              className="rounded-full bg-brand-500 px-5 py-3 text-sm font-semibold text-white transition hover:bg-brand-600 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {busy ? t("analysis.running") : result ? t("analysis.runAgain") : t("analysis.run")}
            </button>
            {formError && <p className="text-sm text-red-700" role="alert">{formError}</p>}
          </div>
        </form>

        <div className="space-y-4">
          <p className="text-sm text-slate-600">
            {t("analysis.summary", {
              name: persona.name,
              balance: formatCad(persona.startingBalance),
              allocation: allocationLabel(persona.allocations),
            })}
          </p>
          <ul className="flex flex-wrap gap-2">
            {services.map((service) => (
              <li
                key={service.name}
                title={service.detail}
                className="flex items-center gap-2 rounded-full bg-slate-50 px-3 py-1.5 text-xs ring-1 ring-slate-200"
              >
                <StatusDot ready={service.ready} verified={service.verified} />
                <b className="text-slate-700">{service.name}</b>
                <span className="text-slate-500">
                  {service.verified ? t("analysis.chip.verified") : service.ready ? t("analysis.chip.ready") : t("analysis.chip.notConfigured")}
                </span>
              </li>
            ))}
          </ul>
        </div>

        {metaError && (
          <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900" role="status">
            {t("analysis.unreachable")}
          </div>
        )}

        <div className="rounded-md bg-slate-50 p-4 ring-1 ring-slate-200">
          <AllocationComparison
            current={result?.current_allocations ?? persona.allocations}
            proposed={result?.proposed_allocations ?? proposedAllocations(persona, formError ? persona.scenario : scenario)}
          />
        </div>

        {error && (
          <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800" role="alert">
            <b className="block">{t("analysis.failed.title")}</b>
            <span>{plain(error)}</span>
            <p className="mt-1 text-xs text-red-700">
              {t("analysis.failed.body")}
            </p>
          </div>
        )}

        {!result && !error && (
          <div className="rounded-md border border-slate-200 px-4 py-3 text-sm text-slate-500" aria-live="polite">
            {busy ? t("analysis.busy") : t("analysis.idle")}
          </div>
        )}

        {result && (
          <div className="space-y-8" aria-live="polite">
            <div className="rounded-md bg-emerald-950 p-5 text-white">
              <p className="text-xs font-semibold uppercase tracking-[0.14em] text-emerald-300">{t("analysis.answerKicker")}</p>
              <p className="mt-2 text-sm italic text-emerald-100">“{result.question}”</p>
              <h2 className="mt-1 text-2xl font-semibold">
                {t(`analysis.concl.${result.conclusion}` as Parameters<typeof t>[0])}
              </h2>
              <p className="mt-2 max-w-4xl text-sm leading-relaxed text-emerald-50">{result.answer}</p>
              <p className="mt-3 text-xs text-emerald-200">{t("analysis.writtenByAi")}</p>
            </div>

            <div>
              <div className="mb-4 flex items-end justify-between border-b border-navy pb-3">
                <h2 className="text-xl font-semibold">{t("analysis.metrics")}</h2>
                <p className="text-xs text-slate-500">{t("analysis.metricsSource")}</p>
              </div>
              <MetricCards metrics={result.metrics} />
              <PerformanceChart points={result.performance_series} />
            </div>

            <div className="grid gap-8 xl:grid-cols-2">
              <div>
                <h2 className="border-b border-navy pb-3 text-xl font-semibold">{t("analysis.delegation")}</h2>
                <TraceTimeline trace={result.trace} />
              </div>
              <div className="evidence-panel">
                <h2 className="border-b border-navy pb-3 text-xl font-semibold">{t("analysis.controls")}</h2>
                <div className="governance-list">
                  {result.governance.map((finding) => (
                    <article key={finding.rule_id} className={finding.severity}>
                      <span>{governanceTitle(finding.rule_id)}</span>
                      <p>{plain(governanceMessage(finding.rule_id, finding.message))}</p>
                    </article>
                  ))}
                </div>
                <details open>
                  <summary>{t("analysis.assumptions")}</summary>
                  <ul>{result.assumptions.map((item) => <li key={item}>{plain(noteText(item))}</li>)}</ul>
                </details>
                <details>
                  <summary>{t("analysis.limitations")}</summary>
                  <ul>{result.limitations.map((item) => <li key={item}>{plain(noteText(item))}</li>)}</ul>
                </details>
                <details>
                  <summary>{t("analysis.dataUsed")}</summary>
                  <ul className="source-list">{result.data_sources.map((item) => <li key={item}>{sourceLabel(item)}</li>)}</ul>
                </details>
              </div>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
