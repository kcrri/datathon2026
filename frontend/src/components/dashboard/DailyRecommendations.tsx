"use client";
import { useSyncExternalStore } from "react";
import { useLanguage } from "@/i18n";
import { fmtLongDate } from "@/i18n/format";
import type { Account } from "@/lib/api";

type Rec = { tag: string; title: string; detail: string; ask: string };

const BY_RISK = new Set(["conservative", "balanced", "growth"]);

export function DailyRecommendations({
  accounts,
  onAsk,
  disabled = false,
}: {
  accounts: Account[];
  onAsk: (q: string) => void;
  disabled?: boolean;
}) {
  const { t } = useLanguage();
  // Format the date in the browser only, so server and client HTML match
  const today = useSyncExternalStore(
    () => () => {},
    () => fmtLongDate(new Date()),
    () => ""
  );

  const rec = (id: string): Rec => ({
    tag: t(`rec.${id}.tag` as Parameters<typeof t>[0]),
    title: t(`rec.${id}.title` as Parameters<typeof t>[0]),
    detail: t(`rec.${id}.detail` as Parameters<typeof t>[0]),
    ask: t(`rec.${id}.ask` as Parameters<typeof t>[0]),
  });

  const recs: Rec[] = [rec("macro")];
  if (!accounts.length) {
    recs.push(rec("start"), rec("learn"));
  } else {
    const risks = Array.from(new Set(accounts.map((a) => a.risk)));
    risks.forEach((r) => BY_RISK.has(r) && recs.push(rec(r)));
    if (risks.length === 1) recs.push(rec("diversify"));
  }

  return (
    <div className="flex h-full flex-col rounded-lg border border-slate-200 bg-white p-6">
      <h2 className="text-xl font-semibold">{t("rec.title")}</h2>
      <div className="h-5 text-xs text-slate-500">{today}</div>
      <ul className="mt-4 flex-1 overflow-y-auto border-t border-slate-200">
        {recs.map((r) => (
          <li key={r.title} className="border-b border-slate-200">
            <button
              onClick={() => onAsk(r.ask)}
              disabled={disabled}
              title={disabled ? t("rec.assistantOff") : undefined}
              className="group w-full py-3 text-left disabled:cursor-default disabled:opacity-60"
            >
              <span className="block text-[10px] font-semibold uppercase tracking-wider text-slate-400">{r.tag}</span>
              <span className="block text-sm font-medium text-link group-hover:underline">{r.title}</span>
              <span className="block text-xs text-slate-500">{r.detail}</span>
            </button>
          </li>
        ))}
      </ul>
      <p className="pt-3 text-[11px] text-slate-400">{t("rec.disclaimer")}</p>
    </div>
  );
}
