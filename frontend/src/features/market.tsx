"use client";
import { createContext, useContext, useMemo, useState } from "react";

type MarketContext = { live: boolean; setLive: (value: boolean) => void };

const Context = createContext<MarketContext | null>(null);
const KEY = "pg.market.live";

function read(): boolean {
  try {
    return window.sessionStorage.getItem(KEY) === "1";
  } catch {
    return false;
  }
}

/**
 * Whether this browser has refreshed the market. The server keeps no market state, so every
 * user and every backend instance behaves the same: this flag is sent with each request.
 * It is kept in session storage so the chat and the Holdings tab agree and a reload keeps it.
 */
export function MarketProvider({ children }: { children: React.ReactNode }) {
  const [live, setLiveState] = useState(false);
  const [hydrated, setHydrated] = useState(false);
  if (!hydrated && typeof window !== "undefined") {
    setHydrated(true);
    setLiveState(read());
  }
  const value = useMemo<MarketContext>(
    () => ({
      live,
      setLive: (next) => {
        setLiveState(next);
        try {
          window.sessionStorage.setItem(KEY, next ? "1" : "0");
        } catch {
          /* storage can be unavailable (private windows); the flag then lives in memory only */
        }
      },
    }),
    [live]
  );
  return <Context.Provider value={value}>{children}</Context.Provider>;
}

export function useMarket() {
  const value = useContext(Context);
  if (!value) throw new Error("useMarket must be used inside MarketProvider");
  return value;
}
