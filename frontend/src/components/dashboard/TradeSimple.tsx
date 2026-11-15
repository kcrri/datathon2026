"use client";
import type { TradeCheck } from "@/lib/api";
import { useLanguage, type MessageKey } from "@/i18n";
import { evidence, FinalVerdict } from "./TradeCheckBody";

/** One plain sentence and three short checks, no numbers. The full detail lives in the chat. */
export function TradeSimple({ check }: { check: TradeCheck }) {
  const { t } = useLanguage();
  const drop = -(evidence(check, "drop") ?? 0);
  const rise = evidence(check, "rise") ?? 0;
  const price = Math.max(drop, rise) < 3 ? "flat" : drop >= rise ? "fell" : "rose";
  const about = (evidence(check, "company_news") ?? 0) > 50 ? "company" : "market";
  const sentiment = evidence(check, "sentiment");
  const tone = sentiment === null ? null : sentiment >= 0.3 ? "upbeat" : sentiment <= -0.3 ? "negative" : "neutral";
  const others = (evidence(check, "breadth") ?? 0) >= 30 ? "many" : "few";

  const rows: Array<[string, string]> = [
    [t("check.price"), t(`check.price.${price}` as MessageKey)],
    [t("check.news"), t(`check.news.${about}` as MessageKey) + (tone ? ` · ${t(`holdings.tone.${tone}` as MessageKey)}` : "")],
    [t("check.others"), t(`check.others.${others}` as MessageKey)],
  ];
  return (
    <>
      <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">{t("popup.feeling")}</div>
      <p className="mt-1 text-sm text-slate-700">
        {check.explanation?.popup_text ?? t(`plain.${check.verdict}` as MessageKey)}
      </p>
      <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-slate-700">
        {rows.map(([label, value]) => (
          <li key={label}>
            {label}: <span className="font-medium text-slate-900">{value}</span>
          </li>
        ))}
      </ul>
      {check.persona_fit && (
        <p className="mt-3 text-sm text-slate-700">
          <span className="font-semibold text-slate-900">{t("popup.asPersona", { name: check.persona_fit.persona.name })}</span>{" "}
          {check.persona_fit.headline}
        </p>
      )}
      <FinalVerdict check={check} />
    </>
  );
}
