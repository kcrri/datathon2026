"use client";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { FEATURES, type FeatureId } from "./registry";

type Flags = Record<FeatureId, boolean>;

const ALL_ON = Object.fromEntries(FEATURES.map((f) => [f.id, true])) as Flags;

function normalise(raw: Record<string, boolean>): Flags {
  // Unknown ids are ignored and missing ids stay on, so a new page never vanishes by accident.
  return Object.fromEntries(FEATURES.map((f) => [f.id, raw[f.id] ?? true])) as Flags;
}

type FlagsContext = {
  flags: Flags;
  loaded: boolean;
  error: string | null;
  isEnabled: (id: FeatureId) => boolean;
  setEnabled: (id: FeatureId, enabled: boolean) => Promise<void>;
  reset: () => Promise<void>;
};

const Context = createContext<FlagsContext | null>(null);
const REFRESH_MS = 15_000;

export function FeatureFlagsProvider({ children }: { children: React.ReactNode }) {
  const [flags, setFlags] = useState<Flags>(ALL_ON);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const refresh = () =>
      api
        .features()
        .then((result) => {
          setFlags(normalise(result.flags));
          setError(null);
        })
        .catch((reason) => {
          // Fail open: if the API is unreachable every page stays available.
          setError(reason instanceof Error ? reason.message : "Could not load feature flags");
        })
        .finally(() => setLoaded(true));
    void refresh();
    const timer = window.setInterval(refresh, REFRESH_MS);
    window.addEventListener("focus", refresh);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("focus", refresh);
    };
  }, []);

  const setEnabled = useCallback(async (id: FeatureId, enabled: boolean) => {
    setFlags(normalise((await api.setFeature(id, enabled)).flags));
  }, []);

  const reset = useCallback(async () => {
    setFlags(normalise((await api.resetFeatures()).flags));
  }, []);

  const value = useMemo<FlagsContext>(
    () => ({ flags, loaded, error, isEnabled: (id) => flags[id], setEnabled, reset }),
    [flags, loaded, error, setEnabled, reset]
  );
  return <Context.Provider value={value}>{children}</Context.Provider>;
}

export function useFeatureFlags() {
  const value = useContext(Context);
  if (!value) throw new Error("useFeatureFlags must be used inside FeatureFlagsProvider");
  return value;
}
