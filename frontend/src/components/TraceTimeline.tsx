"use client";
import type { CSSProperties } from "react";
import { useLanguage } from "@/i18n";
import { agentName, traceAction } from "@/i18n/labels";
import type { TraceStep } from "@/lib/api";
import { plain } from "@/lib/plainLanguage";

export function TraceTimeline({ trace }: { trace: TraceStep[] }) {
  const { t, tOr } = useLanguage();
  return (
    <ol className="trace-list">
      {trace.map((step, index) => (
        <li key={step.step_id} style={{ "--depth": step.parent_id ? 1 : 0 } as CSSProperties}>
          <span className="trace-number">{String(index + 1).padStart(2, "0")}</span>
          <div>
            <div className="trace-agent">
              {agentName(step.agent)}
              <span>{tOr(`status.${step.status}`, step.status)}</span>
            </div>
            <p>{plain(traceAction(step))}</p>
            {step.delegated_to.length > 0 && (
              <small>{t("trace.delegatedTo", { agents: step.delegated_to.map(agentName).join(", ") })}</small>
            )}
          </div>
        </li>
      ))}
    </ol>
  );
}
