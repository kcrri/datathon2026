"use client";
import Link from "next/link";
import { RiskMeter } from "@/components/dashboard/RiskMeter";
import { currentProfile } from "@/components/dashboard/RiskSummary";
import { useAccounts } from "@/features/accounts";
import { useLanguage } from "@/i18n";
import { accountName, strategyLabel } from "@/i18n/labels";
import { RISK_LEVEL, RISK_PROFILES } from "@/lib/profiles";

export default function ProfilePage() {
  const { t, tOr } = useLanguage();
  const { accounts } = useAccounts();
  const profile = currentProfile(accounts);
  const persona = profile?.persona;
  const prefs = persona ? [1, 2, 3].map((n) => tOr(`profile.${persona}.pref${n}`, "")) : [];

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <Link href="/dashboard" className="text-sm text-brand-600 hover:text-brand-700">{t("profile.back")}</Link>

      <section className="flex items-center gap-5 rounded-lg bg-white p-6 ring-1 ring-slate-200">
        <div className="flex h-20 w-20 items-center justify-center rounded-full bg-brand-100 text-3xl font-semibold text-brand-700">D</div>
        <div>
          <div className="text-xs uppercase tracking-wider text-brand-600">{t("profile.kicker")}</div>
          <h1 className="text-2xl font-semibold">{t("profile.name")}</h1>
          <p className="text-sm text-slate-500">
            {persona ? t("profile.closest", { persona }) : t("profile.noPersona")}
          </p>
        </div>
      </section>

      <section className="grid gap-4 sm:grid-cols-3">
        {[
          { k: t("profile.riskType"), v: profile ? tOr(`risk.${profile.id}`, profile.id) : t("profile.notSet") },
          { k: t("profile.goal"), v: persona ? tOr(`profile.${persona}.goal`, "—") : "—" },
          { k: t("profile.horizon"), v: persona ? tOr(`profile.${persona}.horizon`, "—") : "—" },
        ].map((x) => (
          <div key={x.k} className="rounded-lg bg-white p-4 ring-1 ring-slate-200">
            <div className="text-xs text-slate-500">{x.k}</div>
            <div className="font-semibold">{x.v}</div>
          </div>
        ))}
      </section>

      {persona && (
        <section className="rounded-lg bg-white p-6 ring-1 ring-slate-200">
          <h2 className="mb-3 font-semibold">{t("profile.preferences")}</h2>
          <div className="flex flex-wrap gap-2">
            {prefs.map((p) => (
              <span key={p} className="rounded-full bg-brand-50 px-3 py-1 text-sm text-brand-700 ring-1 ring-slate-200">{p}</span>
            ))}
          </div>
        </section>
      )}

      <section className="rounded-lg bg-white p-6 ring-1 ring-slate-200">
        <h2 className="mb-3 font-semibold">{t("profile.riskTypes")}</h2>
        <div className="grid gap-3 sm:grid-cols-3">
          {RISK_PROFILES.map((r) => (
            <div key={r.id} className={`rounded-lg p-4 ring-1 ${profile?.id === r.id ? "bg-brand-50 ring-2 ring-brand-500" : "ring-slate-200"}`}>
              <div className="font-semibold">{tOr(`risk.${r.id}`, r.id)}</div>
              <div className="mb-2 text-xs text-slate-500">
                {t("profile.likePersona", { persona: r.persona, horizon: tOr(`horizon.${r.horizon}`, r.horizon) })}
              </div>
              <RiskMeter level={r.level} />
            </div>
          ))}
        </div>
      </section>

      <section className="rounded-lg bg-white p-6 ring-1 ring-slate-200">
        <h2 className="mb-3 font-semibold">{t("profile.accounts", { n: accounts.length })}</h2>
        {accounts.length === 0 ? (
          <p className="text-sm text-slate-500">{t("profile.noAccounts")}</p>
        ) : (
          <ul className="divide-y divide-slate-50">
            {accounts.map((a) => (
              <li key={a.id} className="flex items-center justify-between gap-4 py-3">
                <div>
                  <div className="font-medium">{accountName(a.name)}</div>
                  <div className="text-xs text-slate-500">
                    {tOr(`horizonAgent.${a.horizon}`, a.horizon_agent)} · {a.strategies.map(strategyLabel).join(", ")}
                  </div>
                </div>
                <div className="w-28">
                  <div className="mb-1 text-right text-xs text-brand-700">{tOr(`risk.${a.risk}`, a.risk_label)}</div>
                  <RiskMeter level={RISK_LEVEL[a.risk] ?? 0} />
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <p className="text-center text-xs text-slate-400">{t("profile.footer")}</p>
    </div>
  );
}
