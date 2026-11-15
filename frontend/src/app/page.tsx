"use client";

import Link from "next/link";
import { useState } from "react";
import { AllocationComparison } from "@/components/AllocationComparison";
import { LanguageToggle } from "@/components/LanguageToggle";
import { useLanguage } from "@/i18n";
import { PERSONAS, allocationLabel, formatCad, proposedAllocations, type PersonaId } from "@/lib/personas";




export default function Home() {
  const [personaId, setPersonaId] = useState<PersonaId>("amira");
  const persona = PERSONAS.find((item) => item.id === personaId)!;
  const { t } = useLanguage();

  return (
    <main className="landing">
      <LanguageToggle className="landing-lang" />

      <section className="hero" id="top">
        <div className="hero-copy">
          <span className="eyebrow">{t("landing.eyebrow")}</span>
          <h1>{t("landing.title1")}<br />{t("landing.title2")}</h1>
          <p>{t("landing.lead")}</p>
        </div>
        <aside className="persona-panel">
          <span className="panel-label">{t("landing.investorContext")}</span>
          <div className="persona-tabs" role="tablist" aria-label={t("shell.investorGroup")}>
            {PERSONAS.map((item) => (
              <button
                key={item.id}
                className={item.id === personaId ? "active" : ""}
                onClick={() => setPersonaId(item.id)}
                role="tab"
                aria-selected={item.id === personaId}
              >
                {item.name}
              </button>
            ))}
          </div>
          <div className="persona-summary">
            <div><strong>{persona.age}</strong><span>{t("landing.age")}</span></div>
            <div><strong>{t(`persona.${personaId}.horizon`)}</strong><span>{t("landing.horizon")}</span></div>
            <div><strong>{t(`persona.${personaId}.risk`)}</strong><span>{t("landing.riskProfile")}</span></div>
          </div>
          <div className="persona-holdings">
            <div><strong>{formatCad(persona.startingBalance)}</strong><span>{t("landing.startingBalance")}</span></div>
            <div><strong>{allocationLabel(persona.allocations)}</strong><span>{t("landing.startingAllocation")}</span></div>
          </div>
          <p>{t("landing.personaNote", { goal: t(`persona.${personaId}.goal`) })}</p>
        </aside>
      </section>

      <section className="workspace">
        <div className="workspace-kicker">
          <span>01</span>
          <p>{t("landing.scenario")}</p>
          <b>{t("account.TFSA")}</b>
        </div>
        <div className="question-row">
          <h2>“{t(`persona.${personaId}.scenario`)}”</h2>
          <Link
            className="analyze-button"
            href={{ pathname: "/dashboard", query: { persona: personaId, run: "1" } }}
          >
            <span>{t("landing.run")}</span>
            <b>↗</b>
          </Link>
        </div>
        <AllocationComparison
          current={persona.allocations}
          proposed={proposedAllocations(persona)}
        />
        <div className="method-strip">
          <span><b>DATA</b> {t("landing.method.data")}</span>
          <span><b>Σ</b> {t("landing.method.calc")}</span>
          <span><b>{t("chat.avatar")}</b> {t("landing.method.ai")}</span>
          <span><b>✓</b> {t("landing.method.rules")}</span>
        </div>
      </section>

      <section className="preflight">
        <div><span>02</span><h2>{t("landing.continue")}</h2></div>
        <p>{t("landing.continueBody")}</p>
        <Link className="cta-link" href={{ pathname: "/dashboard", query: { persona: personaId } }}>
          {t("landing.open")} <b>→</b>
        </Link>
      </section>

      <footer>
        <div className="brand"><span>PG</span><div>PortfolioGuard <b>AI</b></div></div>
        <p>{t("app.footer")}</p>
        <small>{t("landing.footerCredit")}</small>
      </footer>
    </main>
  );
}
