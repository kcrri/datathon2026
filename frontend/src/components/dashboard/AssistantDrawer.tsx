"use client";
import { useEffect, useRef } from "react";
import { useChat } from "@/features/chat";
import { useLanguage } from "@/i18n";
import type { ChatResponse } from "@/lib/api";
import { Message } from "./Message";

function ChatIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-8 w-8" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden>
      <path d="M21 11.5a8.5 8.5 0 0 1-12.4 7.5L3 20.5l1.6-5A8.5 8.5 0 1 1 21 11.5Z" strokeLinejoin="round" />
    </svg>
  );
}

/** Chat that floats over every dashboard page. Open it from the round button; close it with ✕ or Esc. */
export function AssistantDrawer() {
  const { t } = useLanguage();
  const { isOpen, openChat, closeChat, messages, input, setInput, busy, error, send, approve, reject } = useChat();
  const welcome: ChatResponse = {
    answer: t("chat.welcome"),
    trace: [],
    metrics: {},
    sources: [],
    warnings: [],
    proposal: null,
    suggestions: [
      t("chat.suggest.recession"),
      t("chat.suggest.accounts"),
      t("chat.suggest.rates"),
      t("chat.suggest.crypto"),
      t("chat.suggest.create"),
    ],
  };
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, busy, isOpen]);

  useEffect(() => {
    if (isOpen) inputRef.current?.focus();
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return;
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && closeChat();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [isOpen, closeChat]);

  return (
    <>
      {!isOpen && (
        <button
          type="button"
          onClick={openChat}
          aria-label={t("chat.open")}
          title={t("chat.openTitle")}
          className="fixed bottom-6 right-6 z-30 flex h-[4.5rem] w-[4.5rem] items-center justify-center rounded-full bg-brand-500 text-white shadow-lg shadow-brand-200 transition hover:scale-105 hover:bg-brand-600"
        >
          <ChatIcon />
        </button>
      )}

      {isOpen && <div className="fixed inset-0 z-30 bg-black/20 sm:hidden" onClick={closeChat} aria-hidden />}

      <aside
        role="dialog"
        aria-label={t("chat.title")}
        aria-hidden={!isOpen}
        className={`fixed bottom-4 right-4 top-4 z-40 flex w-[calc(100%-2rem)] max-w-[500px] flex-col overflow-hidden rounded-[28px] border border-slate-200 bg-slate-50 transition-transform duration-300 ${
          isOpen
            ? "translate-x-0 shadow-[0_12px_48px_rgba(0,48,77,0.28)]"
            : "pointer-events-none translate-x-[calc(100%+2rem)]"
        }`}
      >
        <header className="flex items-center justify-between border-b border-slate-200 bg-navy px-5 py-4 text-white">
          <div>
            <h2 className="font-semibold">{t("chat.title")}</h2>
            <p className="text-xs text-slate-300">{t("chat.subtitle")}</p>
          </div>
          <button
            type="button"
            onClick={closeChat}
            aria-label={t("chat.close")}
            className="flex h-9 w-9 items-center justify-center rounded-full text-lg text-white/80 transition hover:bg-white/10 hover:text-white"
          >
            ✕
          </button>
        </header>

        <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto p-4">
          <Message key="welcome" msg={{ role: "assistant", data: welcome }} busy={busy} onSuggestion={send} onApprove={approve} onReject={reject} />
          {messages.map((m, i) => (
            <Message key={i} msg={m} busy={busy} onSuggestion={send} onApprove={approve} onReject={reject} />
          ))}
          {busy && (
            <div className="flex items-center gap-2 pl-11 text-sm text-brand-600">
              <span className="h-2 w-2 animate-bounce rounded-full bg-brand-400" />
              <span className="h-2 w-2 animate-bounce rounded-full bg-brand-400 [animation-delay:120ms]" />
              <span className="h-2 w-2 animate-bounce rounded-full bg-brand-400 [animation-delay:240ms]" />
            </div>
          )}
          {error && <div className="pl-11 text-sm text-red-600">{error}</div>}
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            send(input);
          }}
          className="flex gap-2 border-t border-slate-200 bg-white p-3"
        >
          <input
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={t("chat.placeholder")}
            className="min-w-0 flex-1 rounded-full bg-white px-4 py-2.5 text-sm outline-none ring-1 ring-slate-300 transition placeholder:text-slate-400 focus:ring-2 focus:ring-navy"
          />
          <button
            disabled={busy || !input.trim()}
            className="rounded-full bg-brand-500 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-brand-600 disabled:opacity-40"
          >
            {t("chat.send")}
          </button>
        </form>
      </aside>
    </>
  );
}
