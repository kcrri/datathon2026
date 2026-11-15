"use client";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { api, type ClaudeProfile, type InvestorRecord } from "@/lib/api";
import { usePersona } from "./persona";

type ClaudeContext = {
  /** The profile Claude submitted, if any. */
  profile: ClaudeProfile | null;
  record: InvestorRecord | null;
  /** True once the saved investor has been read and any new profile applied. Saving the investor waits for it. */
  ready: boolean;
  /** True for a moment after a new profile arrives, so the UI can say so. */
  justReceived: boolean;
  /** Poll quickly (while the connect dialog is open). */
  setWatching: (value: boolean) => void;
  clear: () => Promise<void>;
};

const Context = createContext<ClaudeContext | null>(null);

/**
 * Watches for the profile Claude sends through the MCP connector. When a new one arrives the app
 * switches to the matching investor, so everything (Holdings, chat, pop-ups) is personalised to it.
 */
export function ClaudeProvider({ children }: { children: React.ReactNode }) {
  const { setPersonaId } = usePersona();
  const [record, setRecord] = useState<InvestorRecord | null>(null);
  const [ready, setReady] = useState(false);
  const [justReceived, setJustReceived] = useState(false);
  const [watching, setWatching] = useState(false);
  const applied = useRef<string | null>(null);

  const read = useCallback(async () => {
    try {
      const next = await api.getInvestor();
      setRecord(next);
      const stamp = next?.profile?.submitted_at ?? null;
      if (stamp && stamp !== applied.current) {
        const first = applied.current === null;
        applied.current = stamp;
        if (next) setPersonaId(next.persona_id);
        if (!first) setJustReceived(true);
      }
    } catch {
      /* the backend may be starting; the next poll retries */
    } finally {
      setReady(true);
    }
  }, [setPersonaId]);

  useEffect(() => {
    const first = window.setTimeout(() => void read(), 0); // read now, then keep watching
    const timer = window.setInterval(() => void read(), watching ? 3000 : 20000);
    return () => {
      window.clearTimeout(first);
      window.clearInterval(timer);
    };
  }, [read, watching]);

  useEffect(() => {
    if (!justReceived) return;
    const timer = window.setTimeout(() => setJustReceived(false), 8000);
    return () => window.clearTimeout(timer);
  }, [justReceived]);

  const clear = useCallback(async () => {
    await api.clearClaudeProfile();
    applied.current = null;
    await read();
  }, [read]);

  const value = useMemo<ClaudeContext>(
    () => ({ profile: record?.profile ?? null, record, ready, justReceived, setWatching, clear }),
    [record, ready, justReceived, clear]
  );
  return <Context.Provider value={value}>{children}</Context.Provider>;
}

export function useClaude() {
  const value = useContext(Context);
  if (!value) throw new Error("useClaude must be used inside ClaudeProvider");
  return value;
}
