"use client";
import { AccountsPanel } from "@/components/dashboard/AccountsPanel";
import { useAccounts } from "@/features/accounts";
import { useAnalysis } from "@/features/analysis";
import { useChat } from "@/features/chat";
import { useFeatureFlags } from "@/features/flags";
import { usePersona } from "@/features/persona";

export default function AccountsPage() {
  const { personaId } = usePersona();
  const { result } = useAnalysis();
  const { accounts, selected, select, remove } = useAccounts();
  const { send, setInput, openChat } = useChat();
  const hasAssistant = useFeatureFlags().isEnabled("assistant");

  return (
    <AccountsPanel
      personaId={personaId}
      analysis={result}
      accounts={accounts}
      selectedId={selected?.id ?? null}
      canCreate={hasAssistant}
      onSelect={(account) => {
        select(account);
        if (hasAssistant) {
          setInput(`How risky is my ${account.name}?`);
          openChat();
        }
      }}
      onNew={() => {
        send("I want to create a new account");
        openChat();
      }}
      onDelete={(id) => void remove(id)}
    />
  );
}
