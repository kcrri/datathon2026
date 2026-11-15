"use client";
import { useEffect, useRef } from "react";
import type { TradeCheck } from "@/lib/api";
import { useLanguage, type MessageKey } from "@/i18n";
import { TradeSimple } from "./TradeSimple";

/** True when the guard flags the trade as risky (as opposed to a plain buy confirmation). */
function isWarning(check: TradeCheck): boolean {
  return (
    (check.action === "sell" && check.verdict === "panic_risk") ||
    (check.action === "buy" && (check.verdict === "chasing_risk" || check.verdict === "falling_knife"))
  );
}

/**
 * Shown every time Buy or Sell is clicked, before the share form: one plain sentence and three
 * short checks. The full detail lives in the chat, one click away.
 */
export function TradeWarningDialog({
  check,
  onBack,
  onProceed,
  onDetails,
}: {
  check: TradeCheck;
  onBack: () => void;
  onProceed: () => void;
  onDetails: () => void;
}) {
  const { t } = useLanguage();
  const backRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    backRef.current?.focus();
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && onBack();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onBack]);

  const warning = isWarning(check);
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4" onClick={onBack}>
      <div
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="warn-title"
        className="max-h-[90vh] w-full max-w-md overflow-y-auto rounded-lg bg-white p-5 shadow-xl ring-1 ring-slate-200"
        onClick={(event) => event.stopPropagation()}
      >
        <h2 id="warn-title" className={`text-lg font-semibold ${warning ? "text-amber-800" : "text-slate-900"}`}>
          {check.explanation?.popup_title ??
            (warning
              ? t(`warn.title.${check.verdict}` as MessageKey)
              : t(check.action === "buy" ? "warn.buyTitle" : "warn.sellTitle", { ticker: check.ticker }))}
        </h2>
        <div className="mt-3">
          <TradeSimple check={check} />
        </div>
        <p className="mt-3 text-xs text-slate-500">{t("warn.footer")}</p>
        {check.trace && check.trace.length > 0 && (
          <details className="mt-3 text-xs text-slate-500" open>
            <summary className="cursor-pointer text-brand-600 hover:text-brand-700">AWS agents that ran</summary>
            <ol className="mt-2 space-y-1.5">
              {check.trace.map((step, i) => (
                <li key={i}>
                  {i + 1}. <b className="text-slate-700">{step.agent}</b>: {step.action}
                  {step.runtime && (
                    <span className="ml-1.5 whitespace-nowrap rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[10px] text-slate-600">AWS · {step.runtime}</span>
                  )}
                </li>
              ))}
            </ol>
          </details>
        )}
        <button type="button" onClick={onDetails} className="mt-3 text-sm text-link underline-offset-2 hover:underline">
          {t("warn.details")}
        </button>
        <div className="mt-4 flex flex-wrap justify-end gap-2">
          <button
            type="button"
            onClick={onProceed}
            className="rounded-full px-4 py-2 text-sm font-medium text-slate-700 ring-1 ring-slate-300 transition hover:bg-slate-50"
          >
            {warning ? t("warn.proceed") : t("warn.continue")}
          </button>
          <button
            ref={backRef}
            type="button"
            onClick={onBack}
            className="rounded-full bg-brand-500 px-4 py-2 text-sm font-medium text-white transition hover:bg-brand-600"
          >
            {t("warn.back")}
          </button>
        </div>
      </div>
    </div>
  );
}
