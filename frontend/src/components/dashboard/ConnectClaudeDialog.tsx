"use client";
import { useEffect, useRef, useState } from "react";
import { api, type McpInfo } from "@/lib/api";
import { useLanguage } from "@/i18n";
import { useClaude } from "@/features/claude";

function CopyField({ value, label }: { value: string; label: string }) {
  const { t } = useLanguage();
  const [copied, setCopied] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  async function copy() {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      input.current?.select(); // the browser refused clipboard access: select it so Ctrl+C works
    }
  }
  return (
    <div>
      <label className="text-xs font-semibold text-slate-600" htmlFor={`copy-${label}`}>
        {label}
      </label>
      <div className="mt-1 flex gap-2">
        <input
          id={`copy-${label}`}
          ref={input}
          readOnly
          value={value}
          onFocus={(event) => event.currentTarget.select()}
          className="min-w-0 flex-1 rounded-md bg-slate-50 px-3 py-2 font-mono text-xs text-slate-800 ring-1 ring-slate-300 outline-none focus:ring-2 focus:ring-navy"
        />
        <button
          type="button"
          onClick={copy}
          className="shrink-0 rounded-full bg-brand-500 px-4 py-2 text-xs font-medium text-white transition hover:bg-brand-600"
        >
          {copied ? t("claude.copied") : t("claude.copy")}
        </button>
      </div>
    </div>
  );
}

/** Add the app to Claude as a remote MCP server, then ask Claude for a persona. */
export function ConnectClaudeDialog({ onClose }: { onClose: () => void }) {
  const { t } = useLanguage();
  const { profile, clear, setWatching } = useClaude();
  const [info, setInfo] = useState<McpInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    api.mcpInfo().then(setInfo).catch((reason) => setError(reason instanceof Error ? reason.message : t("common.requestFailed")));
  }, [t]);

  useEffect(() => {
    setWatching(true); // look for Claude's answer every few seconds while this is open
    closeRef.current?.focus();
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => {
      setWatching(false);
      window.removeEventListener("keydown", onKey);
    };
  }, [onClose, setWatching]);

  const prompt = t("claude.promptText");
  const command = info ? `claude mcp add --transport http portfolioguard ${info.url}` : "";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="claude-title"
        className="max-h-[92vh] w-full max-w-xl overflow-y-auto rounded-lg bg-white p-5 shadow-xl ring-1 ring-slate-200"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 id="claude-title" className="text-lg font-semibold text-slate-900">
              {t("claude.title")}
            </h2>
            <p className="mt-1 text-sm text-slate-600">{t("claude.intro")}</p>
          </div>
          <button
            ref={closeRef}
            type="button"
            onClick={onClose}
            aria-label={t("claude.close")}
            className="rounded-full px-3 py-1 text-sm text-slate-600 ring-1 ring-slate-300 hover:bg-slate-50"
          >
            {t("claude.close")}
          </button>
        </div>

        {error && <p className="mt-4 rounded-md bg-amber-50 p-3 text-sm text-amber-900 ring-1 ring-amber-200">{error}</p>}

        {info && (
          <div className="mt-5 space-y-5">
            <section>
              <h3 className="text-sm font-semibold text-slate-800">{t("claude.step1")}</h3>
              <div className="mt-2 space-y-3">
                <CopyField value={info.url} label={t("claude.urlLabel")} />
                {info.local_only && (
                  <p className="rounded-md bg-amber-50 p-3 text-xs text-amber-900 ring-1 ring-amber-200">{t("claude.localOnly")}</p>
                )}
                {!info.stable && <p className="text-xs text-slate-500">{t("claude.unstable")}</p>}
                <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">
                  <li>
                    <b>Claude Code:</b> {t("claude.code")}
                  </li>
                  <li>
                    <b>Claude ({t("claude.webDesktop")}):</b> {t("claude.web")}
                  </li>
                </ul>
                <CopyField value={command} label={t("claude.commandLabel")} />
              </div>
            </section>

            <section>
              <h3 className="text-sm font-semibold text-slate-800">{t("claude.step2")}</h3>
              <div className="mt-2">
                <CopyField value={prompt} label={t("claude.promptLabel")} />
              </div>
              <p className="mt-2 text-xs text-slate-500">{t("claude.toolNote")}</p>
              <details className="mt-2 text-xs text-slate-600">
                <summary className="cursor-pointer text-link">{t("claude.toolDetails")}</summary>
                <pre className="mt-2 max-h-56 overflow-auto rounded-md bg-slate-50 p-3 text-[11px] ring-1 ring-slate-200">
                  {JSON.stringify({ tool: "submit_persona", arguments: info.example, schema: info.tools[0]?.input_schema }, null, 2)}
                </pre>
              </details>
            </section>

            <section aria-live="polite">
              <h3 className="text-sm font-semibold text-slate-800">{t("claude.step3")}</h3>
              {profile ? (
                <div className="mt-2 rounded-md bg-emerald-50 p-3 text-sm text-emerald-900 ring-1 ring-emerald-200">
                  <div className="font-semibold">{t("claude.received")}</div>
                  <div className="mt-1">
                    {profile.name ? `${profile.name} · ` : ""}
                    {t("claude.riskLine", { risk: t(`claude.risk.${profile.risk}` as Parameters<typeof t>[0]), horizon: profile.horizon })}
                  </div>
                  <div className="mt-0.5">{t("claude.goalsLine", { goals: profile.goals.join("; ") })}</div>
                  <button type="button" onClick={() => void clear()} className="mt-2 text-xs font-medium text-emerald-900 underline">
                    {t("claude.clear")}
                  </button>
                </div>
              ) : (
                <p className="mt-2 flex items-center gap-2 text-sm text-slate-600">
                  <span className="h-2 w-2 animate-pulse rounded-full bg-slate-400" aria-hidden="true" />
                  {t("claude.waiting")}
                </p>
              )}
            </section>
          </div>
        )}
      </div>
    </div>
  );
}
