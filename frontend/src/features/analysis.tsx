"use client";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { translate } from "@/i18n";
import { api, runAnalysis, type AnalysisInput, type AnalysisResponse, type ApiMeta } from "@/lib/api";
import type { PersonaId } from "@/lib/personas";
import { usePersona } from "./persona";

type AnalysisContext = {
  result: AnalysisResponse | null;
  busy: boolean;
  error: string | null;
  meta: ApiMeta | null;
  metaError: string | null;
  run: (input?: AnalysisInput) => Promise<void>;
};

const Context = createContext<AnalysisContext | null>(null);

type Stored<T> = { personaId: PersonaId; value: T };

/** Holds the latest live analysis. A result belongs to one investor, so switching persona hides it. */
export function AnalysisProvider({ children }: { children: React.ReactNode }) {
  const { personaId } = usePersona();
  const [stored, setStored] = useState<Stored<AnalysisResponse> | null>(null);
  const [failure, setFailure] = useState<Stored<string> | null>(null);
  const [busy, setBusy] = useState(false);
  const [meta, setMeta] = useState<ApiMeta | null>(null);
  const [metaError, setMetaError] = useState<string | null>(null);

  useEffect(() => {
    api
      .meta()
      .then(setMeta)
      .catch((reason) => setMetaError(reason instanceof Error ? reason.message : translate("analysis.reachFail")));
  }, []);

  const run = useCallback(async (input?: AnalysisInput) => {
    setBusy(true);
    setFailure(null);
    try {
      setStored({ personaId, value: await runAnalysis(personaId, input) });
    } catch (reason) {
      setStored(null);
      setFailure({ personaId, value: reason instanceof Error ? reason.message : translate("analysis.failedGeneric") });
    } finally {
      setBusy(false);
    }
  }, [personaId]);

  const value = useMemo<AnalysisContext>(
    () => ({
      result: stored?.personaId === personaId ? stored.value : null,
      busy,
      error: failure?.personaId === personaId ? failure.value : null,
      meta,
      metaError,
      run,
    }),
    [stored, failure, busy, meta, metaError, personaId, run]
  );
  return <Context.Provider value={value}>{children}</Context.Provider>;
}

export function useAnalysis() {
  const value = useContext(Context);
  if (!value) throw new Error("useAnalysis must be used inside AnalysisProvider");
  return value;
}
