"use client";
import { Suspense } from "react";
import { AccountsProvider } from "@/features/accounts";
import { AnalysisProvider } from "@/features/analysis";
import { ChatProvider } from "@/features/chat";
import { ClaudeProvider } from "@/features/claude";
import { DashboardShell } from "@/features/DashboardShell";
import { MarketProvider } from "@/features/market";
import { PersonaProvider } from "@/features/persona";

/** Shared state for every dashboard page. Each page reads only the pieces it needs. */
export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <Suspense fallback={null}>
      <PersonaProvider>
        <MarketProvider>
          <ClaudeProvider>
            <AccountsProvider>
              <ChatProvider>
                <AnalysisProvider>
                  <DashboardShell>{children}</DashboardShell>
                </AnalysisProvider>
              </ChatProvider>
            </AccountsProvider>
          </ClaudeProvider>
        </MarketProvider>
      </PersonaProvider>
    </Suspense>
  );
}
