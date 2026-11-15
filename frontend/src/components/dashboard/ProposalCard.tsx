"use client";
import { useState } from "react";
import { accountTypeLabel } from "@/i18n/labels";
import { useLanguage } from "@/i18n";
import type { Proposal } from "@/lib/api";
import { RISK_PROFILES } from "@/lib/profiles";
import { RiskMeter } from "./RiskMeter";

export function ProposalCard({
  proposal,
  disabled,
  onApprove,
  onReject,
}: {
  proposal: Proposal;
  disabled: boolean;
  onApprove: (risk: string) => void;
  onReject: () => void;
}) {
  const { t, tOr } = useLanguage();
  const [risk, setRisk] = useState(proposal.risk);
  return (
    <div className="mt-3 space-y-4 rounded-xl bg-slate-50 p-4 ring-1 ring-slate-200">
      <div>
        <div className="text-xs font-medium uppercase tracking-wider text-brand-600">{t("proposal.title")}</div>
        <div className="text-base font-semibold">
          {proposal.account_type_label ?? accountTypeLabel(proposal.account_type)}{" "}
          <span className="font-normal text-slate-500">· {proposal.horizon_label}</span>
        </div>
      </div>
      <fieldset disabled={disabled}>
        <legend className="mb-2 text-xs text-slate-500">{t("proposal.chooseRisk")}</legend>
        <div className="grid gap-2 sm:grid-cols-3">
          {RISK_PROFILES.map((r) => {
            const on = risk === r.id;
            return (
              <label
                key={r.id}
                className={`cursor-pointer rounded-xl bg-white p-3 ring-1 transition hover:ring-brand-300 ${
                  on ? "ring-2 ring-brand-500" : "ring-slate-200"
                }`}
              >
                <input
                  type="radio"
                  name={`risk-${proposal.id}`}
                  value={r.id}
                  checked={on}
                  onChange={() => setRisk(r.id)}
                  className="sr-only"
                />
                <div className="text-sm font-semibold">{tOr(`risk.${r.id}`, r.id)}</div>
                <div className="mb-2 text-xs text-slate-500">{t("proposal.like", { persona: r.persona })}</div>
                <RiskMeter level={r.level} />
              </label>
            );
          })}
        </div>
      </fieldset>
      <div className="flex gap-2">
        <button
          disabled={disabled}
          onClick={() => onApprove(risk)}
          className="rounded-full bg-brand-500 px-5 py-2 text-sm font-medium text-white shadow-sm shadow-brand-200 transition hover:bg-brand-600 disabled:opacity-40"
        >
          {t("proposal.approve")}
        </button>
        <button
          disabled={disabled}
          onClick={onReject}
          className="rounded-full px-4 py-2 text-sm text-slate-500 transition hover:bg-white disabled:opacity-40"
        >
          {t("proposal.decline")}
        </button>
      </div>
    </div>
  );
}
