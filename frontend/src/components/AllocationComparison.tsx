"use client";
import { useLanguage } from "@/i18n";
import { fmtPercent } from "@/i18n/format";

const STRATEGY_COLORS: Record<string, string> = {
  growth: "var(--coral)",
  dividend: "var(--blue)",
  momentum: "var(--gold)",
  preservation: "var(--sage)",
};

function AllocationColumn({
  title,
  allocations,
}: {
  title: string;
  allocations: Record<string, number>;
}) {
  const { t, tOr } = useLanguage();
  const label = (strategy: string) => tOr(`strategy.${strategy}`, strategy);
  return (
    <div className="allocation-column">
      <div className="allocation-title-row">
        <h3>{title}</h3>
        <span>{t("account.TFSA")}</span>
      </div>
      <div className="allocation-stack" aria-label={t("alloc.aria", { title })}>
        {Object.entries(allocations).map(([strategy, weight]) => (
          <div
            key={strategy}
            style={{ width: `${weight * 100}%`, background: STRATEGY_COLORS[strategy] }}
            title={`${label(strategy)} ${fmtPercent(weight * 100)}`}
          />
        ))}
      </div>
      <dl className="allocation-list">
        {Object.entries(allocations).map(([strategy, weight]) => (
          <div key={strategy}>
            <dt>
              <i style={{ background: STRATEGY_COLORS[strategy] }} />
              {label(strategy)}
            </dt>
            <dd>{fmtPercent(weight * 100)}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

export function AllocationComparison({
  current,
  proposed,
}: {
  current: Record<string, number>;
  proposed: Record<string, number>;
}) {
  const { t } = useLanguage();
  // The size of the move is the largest change in any strategy's weight, in percentage points.
  const shift = Math.round(
    Math.max(0, ...Object.keys(current).map((key) => Math.abs((proposed[key] ?? 0) - (current[key] ?? 0)))) * 100
  );
  return (
    <div className="allocation-grid">
      <AllocationColumn title={t("alloc.current")} allocations={current} />
      <div className="shift-marker" aria-label={t("alloc.shiftAria", { n: shift })}>
        <span>{t("alloc.shiftLabel", { n: shift })}</span>
        <b>→</b>
      </div>
      <AllocationColumn title={t("alloc.proposed")} allocations={proposed} />
    </div>
  );
}
