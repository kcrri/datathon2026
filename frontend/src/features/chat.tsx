"use client";
import { createContext, useCallback, useContext, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import type { ChatMessage } from "@/components/dashboard/Message";
import { translate } from "@/i18n";
import { api, type ChatResponse } from "@/lib/api";
import { useAccounts } from "./accounts";
import { useMarket } from "./market";
import { usePersona } from "./persona";

type ChatContext = {
  isOpen: boolean;
  openChat: () => void;
  closeChat: () => void;
  toggleChat: () => void;
  messages: ChatMessage[];
  input: string;
  setInput: (value: string) => void;
  busy: boolean;
  error: string | null;
  send: (text: string) => void;
  approve: (id: string, risk: string | undefined) => void;
  reject: (id: string) => void;
};

const Context = createContext<ChatContext | null>(null);

/** Chat state lives above the pages so the conversation survives switching tabs. */
export function ChatProvider({ children }: { children: React.ReactNode }) {
  const { refresh } = useAccounts();
  const { personaId } = usePersona();
  const { live } = useMarket();
  const params = useSearchParams();
  const [isOpen, setIsOpen] = useState(() => params.get("chat") === "1"); // /dashboard/...?chat=1 opens the drawer
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = useCallback(
    async (fn: () => Promise<ChatResponse>, userText?: string, resolveId?: string) => {
      setBusy(true);
      setError(null);
      setMessages((current) => {
        let next = current;
        if (resolveId) {
          next = next.map((m) =>
            m.role === "assistant" && m.data.proposal?.id === resolveId ? { ...m, resolved: true } : m
          );
        }
        return userText ? [...next, { role: "user", text: userText }] : next;
      });
      try {
        const data = await fn();
        setMessages((current) => [...current, { role: "assistant", data }]);
        await refresh();
      } catch (reason) {
        setError(reason instanceof Error ? reason.message : translate("common.requestFailed"));
      } finally {
        setBusy(false);
      }
    },
    [refresh]
  );

  const send = useCallback(
    (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || busy) return;
      setInput("");
      void run(() => api.chat(trimmed, personaId, live), trimmed);
    },
    [busy, personaId, live, run]
  );

  const value = useMemo<ChatContext>(
    () => ({
      isOpen,
      openChat: () => setIsOpen(true),
      closeChat: () => setIsOpen(false),
      toggleChat: () => setIsOpen((open) => !open),
      messages,
      input,
      setInput,
      busy,
      error,
      send,
      approve: (id, risk) => void run(() => api.approve(id, risk), translate("chat.approve"), id),
      reject: (id) => void run(() => api.reject(id), translate("chat.decline"), id),
    }),
    [isOpen, messages, input, busy, error, send, run]
  );
  return <Context.Provider value={value}>{children}</Context.Provider>;
}

export function useChat() {
  const value = useContext(Context);
  if (!value) throw new Error("useChat must be used inside ChatProvider");
  return value;
}
