"use client";
import Link from "next/link";
import { useState } from "react";
import { usePathname } from "next/navigation";
import { AssistantDrawer } from "@/components/dashboard/AssistantDrawer";
import { Header } from "@/components/dashboard/Header";
import { ConnectClaudeDialog } from "@/components/dashboard/ConnectClaudeDialog";
import { RuntimeBadge } from "@/components/dashboard/RuntimeBadge";
import { useLanguage } from "@/i18n";
import { PERSONAS } from "@/lib/personas";
import { useClaude } from "./claude";
import { useFeatureFlags } from "./flags";
import { usePersona } from "./persona";
import { PAGES, featureForPath } from "./registry";

function PersonaSwitcher() {
  const { personaId, setPersonaId } = usePersona();
  const { t } = useLanguage();
  return (
    <div className="flex items-center gap-2" role="group" aria-label={t("shell.investorGroup")}>
      <span className="hidden text-xs uppercase tracking-wide text-slate-500 sm:inline">{t("shell.investor")}</span>
      {PERSONAS.map((p) => (
        <button
          key={p.id}
          type="button"
          onClick={() => setPersonaId(p.id)}
          aria-pressed={personaId === p.id}
          className={`rounded-full px-3.5 py-1.5 text-sm font-medium ring-1 transition ${
            personaId === p.id
              ? "bg-brand-500 text-white ring-brand-500"
              : "bg-white text-slate-600 ring-slate-300 hover:bg-slate-50"
          }`}
        >
          {p.name}
        </button>
      ))}
    </div>
  );
}

function ConnectClaudeButton({ onClick }: { onClick: () => void }) {
  const { t } = useLanguage();
  const { profile } = useClaude();
  return (
    <button
      type="button"
      onClick={onClick}
      style={{ color: "#fff" }}
      className={`inline-flex shrink-0 items-center gap-2 whitespace-nowrap rounded-full py-1.5 pl-3 pr-4 text-sm font-medium text-white shadow-sm ring-1 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 ${
        profile ? "bg-emerald-600 ring-emerald-600 hover:bg-emerald-700" : "bg-navy ring-navy hover:opacity-90"
      }`}
    >
      <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        {profile ? (
          <path d="M4.5 10.5l3.5 3.5 7.5-8" />
        ) : (
          <path d="M8.5 11.5l3-3M7 9L5.2 10.8a2.8 2.8 0 004 4L11 13m2-2l1.8-1.8a2.8 2.8 0 00-4-4L9 7" />
        )}
      </svg>
      {profile ? t("claude.connected") : t("claude.connect")}
    </button>
  );
}

function ClaudeBanner() {
  const { t } = useLanguage();
  const { profile, justReceived, clear } = useClaude();
  if (!profile) return null;
  return (
    <div
      role="status"
      className={`mb-4 flex flex-wrap items-center justify-between gap-2 rounded-md px-4 py-2.5 text-sm ring-1 ${
        justReceived ? "bg-emerald-100 text-emerald-900 ring-emerald-300" : "bg-emerald-50 text-emerald-900 ring-emerald-200"
      }`}
    >
      <span>
        <b>{justReceived ? t("claude.bannerNew") : t("claude.banner")}</b>{" "}
        {profile.name ? `${profile.name} · ` : ""}
        {t("claude.riskLine", { risk: t(`claude.risk.${profile.risk}` as Parameters<typeof t>[0]), horizon: profile.horizon })} ·{" "}
        {t("claude.goalsLine", { goals: profile.goals.join("; ") })}
      </span>
      <button type="button" onClick={() => void clear()} className="text-xs font-medium underline">
        {t("claude.clear")}
      </button>
    </div>
  );
}

function Notice({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg bg-white p-8 text-center ring-1 ring-slate-200">
      <h2 className="text-xl font-semibold">{title}</h2>
      <p className="mt-2 text-sm text-slate-600">{children}</p>
    </div>
  );
}

/** Header, tab bar and investor switcher around every dashboard page. */
export function DashboardShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { t } = useLanguage();
  const { loaded, isEnabled } = useFeatureFlags();
  const [connectOpen, setConnectOpen] = useState(false);
  const tabs = PAGES.filter((f) => isEnabled(f.id));
  const current = featureForPath(pathname);
  const label = (id: string) => t(`feature.${id}.label` as Parameters<typeof t>[0]);

  let content = children;
  if (!loaded) {
    content = <p className="py-16 text-center text-sm text-slate-500">{t("shell.loading")}</p>;
  } else if (current && !isEnabled(current.id)) {
    content = (
      <Notice title={t("shell.off.title", { label: label(current.id) })}>
        {t("shell.off.body")}{" "}
        {tabs[0] ? (
          <Link href={tabs[0].path} className="font-medium text-link hover:underline">
            {t("shell.off.goto", { label: label(tabs[0].id) })}
          </Link>
        ) : (
          <Link href="/admin" className="font-medium text-link hover:underline">
            {t("shell.off.openAdmin")}
          </Link>
        )}
      </Notice>
    );
  }

  return (
    <div className="min-h-screen">
      <Header />
      <div className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-x-6 gap-y-2 px-4 py-2">
          <nav aria-label={t("shell.pages")} className="-mb-2 flex gap-1 overflow-x-auto">
            {tabs.map((f) => {
              const active = current?.id === f.id;
              return (
                <Link
                  key={f.id}
                  href={f.path}
                  aria-current={active ? "page" : undefined}
                  className={`whitespace-nowrap border-b-2 px-3 py-2.5 text-sm font-medium transition ${
                    active
                      ? "border-brand-500 text-navy"
                      : "border-transparent text-slate-500 hover:text-slate-800"
                  }`}
                >
                  {label(f.id)}
                </Link>
              );
            })}
          </nav>
          <div className="ml-auto flex flex-wrap items-center justify-end gap-x-3 gap-y-2">
            <RuntimeBadge />
            <PersonaSwitcher />
            <ConnectClaudeButton onClick={() => setConnectOpen(true)} />
          </div>
        </div>
      </div>
      <main className="mx-auto max-w-6xl px-4 py-6">
        <ClaudeBanner />
        {content}
      </main>
      {connectOpen && <ConnectClaudeDialog onClose={() => setConnectOpen(false)} />}
      <p className="pb-8 text-center text-xs text-slate-400">{t("app.footer")}</p>
      {loaded && isEnabled("assistant") && <AssistantDrawer />}
    </div>
  );
}
