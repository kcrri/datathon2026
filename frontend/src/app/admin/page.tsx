"use client";
import Link from "next/link";
import { useState } from "react";
import { Header } from "@/components/dashboard/Header";
import { useFeatureFlags } from "@/features/flags";
import { useLanguage } from "@/i18n";
import { FEATURES, type FeatureId } from "@/features/registry";

function Switch({ on, busy, label, onChange }: { on: boolean; busy: boolean; label: string; onChange: () => void }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-label={label}
      disabled={busy}
      onClick={onChange}
      className={`relative h-7 w-12 shrink-0 rounded-full transition disabled:opacity-60 ${on ? "bg-emerald-500" : "bg-slate-300"}`}
    >
      <span
        className={`absolute top-0.5 h-6 w-6 rounded-full bg-white shadow transition-all ${on ? "left-[1.375rem]" : "left-0.5"}`}
      />
    </button>
  );
}

export default function AdminPage() {
  const { t } = useLanguage();
  const { flags, loaded, error: loadError, setEnabled, reset } = useFeatureFlags();
  const [pending, setPending] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const enabledCount = FEATURES.filter((f) => flags[f.id]).length;

  async function change(action: () => Promise<void>, key: string) {
    setPending(key);
    setError(null);
    try {
      await action();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t("admin.saveFailed"));
    } finally {
      setPending(null);
    }
  }

  return (
    <div className="min-h-screen">
      <Header />
      <main className="mx-auto max-w-3xl space-y-6 px-4 py-8">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-brand-600">{t("admin.kicker")}</p>
            <h1 className="text-2xl font-semibold">{t("admin.title")}</h1>
            <p className="text-sm text-slate-600">
              {t("admin.intro")}
            </p>
          </div>
          <div className="flex items-center gap-4">
            <span className="text-sm text-slate-500">
              {t("admin.count", { n: enabledCount, total: FEATURES.length })}
            </span>
            <button
              type="button"
              onClick={() => change(reset, "reset")}
              disabled={pending !== null}
              className="rounded-full px-4 py-2 text-sm font-medium text-slate-700 ring-1 ring-slate-300 transition hover:bg-slate-50 disabled:opacity-50"
            >
              {t("admin.reset")}
            </button>
          </div>
        </div>

        {(loadError || error) && (
          <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900" role="status">
            {error ?? t("admin.unreachable")}
          </div>
        )}

        <ul className="divide-y divide-slate-200 rounded-lg bg-white ring-1 ring-slate-200">
          {FEATURES.map((f) => (
            <li key={f.id} className="flex items-center gap-4 px-5 py-4">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <h2 className="font-semibold">{t(`feature.${f.id}.label` as Parameters<typeof t>[0])}</h2>
                  <span
                    className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${
                      flags[f.id] ? "bg-emerald-100 text-emerald-800" : "bg-slate-100 text-slate-500"
                    }`}
                  >
                    {flags[f.id] ? t("admin.on") : t("admin.off")}
                  </span>
                </div>
                <p className="mt-0.5 text-sm text-slate-600">{t(`feature.${f.id}.description` as Parameters<typeof t>[0])}</p>
                {flags[f.id] && f.path && (
                  <Link href={f.path} className="mt-1 inline-block text-xs font-medium text-link hover:underline">
                    {t("admin.open", { path: f.path })}
                  </Link>
                )}
              </div>
              <Switch
                on={flags[f.id]}
                busy={!loaded || pending !== null}
                label={t("admin.switch", { label: t(`feature.${f.id}.label` as Parameters<typeof t>[0]) })}
                onChange={() => change(() => setEnabled(f.id as FeatureId, !flags[f.id]), f.id)}
              />
            </li>
          ))}
        </ul>

        <p className="text-xs text-slate-500">
          {t("admin.note")}
        </p>
        <Link href="/dashboard" className="text-sm font-medium text-link hover:underline">
          {t("admin.back")}
        </Link>
      </main>
    </div>
  );
}
