"use client";
import { useEffect, useState } from "react";
import { api, type RuntimeInfo } from "@/lib/api";
import { useLanguage } from "@/i18n";

type State = { kind: "checking" } | { kind: "aws" | "local"; info: RuntimeInfo } | { kind: "error"; message: string };

/** Shows where calculations really run, from a live call to the backend and on to AWS. */
export function RuntimeBadge() {
  const { t } = useLanguage();
  const [state, setState] = useState<State>({ kind: "checking" });

  useEffect(() => {
    let alive = true;
    const check = () =>
      api
        .runtime()
        .then((info) => alive && setState({ kind: info.engine === "aws-lambda" && info.agents === "agentcore" ? "aws" : "local", info }))
        .catch((reason) => alive && setState({ kind: "error", message: reason instanceof Error ? reason.message : "" }));
    check();
    const timer = window.setInterval(check, 60_000);
    return () => {
      alive = false;
      window.clearInterval(timer);
    };
  }, []);

  const style =
    state.kind === "aws"
      ? { dot: "bg-emerald-500", box: "bg-emerald-50 text-emerald-800 ring-emerald-200" }
      : state.kind === "checking"
        ? { dot: "bg-slate-400", box: "bg-white text-slate-600 ring-slate-300" }
        : { dot: "bg-amber-500", box: "bg-amber-50 text-amber-900 ring-amber-200" };
  const label =
    state.kind === "aws" ? t("runtime.aws") : state.kind === "local" ? t("runtime.local") : state.kind === "error" ? t("runtime.error") : t("runtime.checking");
  const title =
    state.kind === "aws"
      ? t("runtime.title.aws", {
          agents: state.info.agent_runtime ?? "",
          fn: state.info.function ?? "",
          region: state.info.region ?? "",
          data: state.info.data,
        })
      : state.kind === "local"
        ? t("runtime.title.local")
        : state.kind === "error"
          ? `${t("runtime.title.error")} ${state.message}`
          : "";
  return (
    <span title={title} role="status" className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ring-1 ${style.box}`}>
      <span className={`h-2 w-2 rounded-full ${style.dot}`} aria-hidden="true" />
      {label}
    </span>
  );
}
