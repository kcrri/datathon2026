"use client";
import { useLanguage } from "@/i18n";
import { fmtNumber, fmtPercent } from "@/i18n/format";
import { metricLabel } from "@/i18n/labels";
import type { MetricEvidence } from "@/lib/api";

function formatValue(value: number, unit: MetricEvidence["unit"]) {
  if (unit === "percent") return fmtPercent(value * 100, 1);
  return fmtNumber(value, 3);
}

function formatDelta(value: number, unit: MetricEvidence["unit"]) {
  if (unit === "percent") return `${value > 0 ? "+" : ""}${fmtPercent(value * 100, 1)}`;
  return `${value > 0 ? "+" : ""}${fmtNumber(value, 3)}`;
}

export function MetricCards({ metrics }: { metrics: MetricEvidence[] }) {
  const { t } = useLanguage();
  return (
    <div className="metric-grid">
      {metrics.map((metric) => {
        const favorable =
          metric.evidence_id === "metric.maximum_drawdown"
            ? metric.delta > 0
            : metric.evidence_id === "metric.annualized_return" ||
                metric.evidence_id === "metric.total_return"
              ? metric.delta > 0
              : metric.delta < 0;
        return (
          <article className="metric-card" key={metric.evidence_id}>
            <p>{metricLabel(metric.evidence_id, metric.label)}</p>
            <div className="metric-comparison">
              <span>{formatValue(metric.current, metric.unit)}</span>
              <b>→</b>
              <strong>{formatValue(metric.proposed, metric.unit)}</strong>
            </div>
            <small className={favorable ? "delta favorable" : "delta tradeoff"}>
              {t("analysis.change", { value: formatDelta(metric.delta, metric.unit) })}
            </small>
          </article>
        );
      })}
    </div>
  );
}
