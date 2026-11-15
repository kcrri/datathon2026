"use client";
import { DailyRecommendations } from "@/components/dashboard/DailyRecommendations";
import { RiskSummary } from "@/components/dashboard/RiskSummary";
import { useAccounts } from "@/features/accounts";
import { useChat } from "@/features/chat";
import { useFeatureFlags } from "@/features/flags";

export default function InsightsPage() {
  const { accounts } = useAccounts();
  const { send, openChat } = useChat();
  const hasAssistant = useFeatureFlags().isEnabled("assistant");

  return (
    <div className="grid gap-6 md:grid-cols-[minmax(0,320px)_minmax(0,1fr)]">
      <RiskSummary accounts={accounts} />
      <DailyRecommendations
        accounts={accounts}
        disabled={!hasAssistant}
        onAsk={(question) => {
          send(question);
          openChat();
        }}
      />
    </div>
  );
}
