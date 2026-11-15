"use client";
import { useSearchParams } from "next/navigation";
import { useEffect, useRef } from "react";
import { LiveAnalysisPanel } from "@/components/dashboard/LiveAnalysisPanel";
import { useAnalysis } from "@/features/analysis";
import { usePersona } from "@/features/persona";

export default function AnalysisPage() {
  const { personaId } = usePersona();
  const { result, busy, error, meta, metaError, run } = useAnalysis();
  const autoRun = useSearchParams().get("run") === "1"; // set by the landing page's "Analyze" button
  const started = useRef(false);

  useEffect(() => {
    if (!autoRun || started.current) return;
    started.current = true;
    void run();
  }, [autoRun, run]);

  return (
    <LiveAnalysisPanel
      key={personaId}
      personaId={personaId}
      result={result}
      busy={busy}
      error={error}
      meta={meta}
      metaError={metaError}
      onRun={(input) => void run(input)}
    />
  );
}
