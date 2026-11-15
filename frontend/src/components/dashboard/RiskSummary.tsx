"use client";
import type { Account } from "@/lib/api";
import { useLanguage } from "@/i18n";
import { RiskMeter } from "./RiskMeter";
import { RISK_LEVEL, RISK_PROFILES } from "@/lib/profiles";

export function currentProfile(accounts: Account[]) {
  if (!accounts.length) return null;
  const avg = Math.round(accounts.reduce((s, a) => s + (RISK_LEVEL[a.risk] ?? 0), 0) / accounts.length);
  return RISK_PROFILES.find((p) => p.level === avg) ?? null;
}

export function RiskSummary({ accounts }: { accounts: Account[] }) {
  const { t, tOr } = useLanguage();
  const profile = currentProfile(accounts);
  const level = profile?.level ?? 0;
  const rows = [
    { k: t("risk.accounts"), v: accounts.length },
    ...RISK_PROFILES.map((p) => ({ k: tOr(`risk.${p.id}`, p.id), v: accounts.filter((a) => a.risk === p.id).length })),
  ];

  return (
    <div className="flex-1 rounded-lg border border-slate-200 bg-white p-5">
      <h2 className="text-sm font-semibold text-slate-500">{t("risk.title")}</h2>
      <div className="mt-1 text-2xl font-semibold text-navy">
        {profile ? tOr(`risk.${profile.id}`, profile.id) : t("risk.notSet")}
      </div>
      <div className="text-xs text-slate-500">
        {profile ? tOr(`horizonFocus.${profile.horizon}`, "") : t("risk.openToSet")}
      </div>
      <div className="mt-4">
        <div className="mb-1 flex justify-between text-[11px] text-slate-500">
          <span>{t("risk.low")}</span>
          <span>{t("risk.high")}</span>
        </div>
        <RiskMeter level={level} size="lg" />
      </div>
      <dl className="mt-5 divide-y divide-slate-200 border-y border-slate-200 text-sm">
        {rows.map((r) => (
          <div key={r.k} className="flex justify-between py-2">
            <dt className="text-slate-500">{r.k}</dt>
            <dd className="font-semibold">{r.v}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
