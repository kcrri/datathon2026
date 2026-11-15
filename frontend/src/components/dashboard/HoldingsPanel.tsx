"use client";
import { useEffect, useRef, useState } from "react";
import { api, type Holding, type MarketStatus, type Portfolio, type TradeAction, type TradeCheck } from "@/lib/api";
import { translate, useLanguage } from "@/i18n";
import { fmtCad, fmtNumber, fmtPercent } from "@/i18n/format";
import { accountName } from "@/i18n/labels";
import { accountValue } from "@/lib/accountValue";
import { PERSONAS, type PersonaId } from "@/lib/personas";
import { useAccounts } from "@/features/accounts";
import { useChat } from "@/features/chat";
import { useClaude } from "@/features/claude";
import { useMarket } from "@/features/market";
import { TradeWarningDialog } from "./TradeWarningDialog";

export function HoldingsPanel({ personaId }: { personaId: PersonaId }) {
  const { t } = useLanguage();
  const chat = useChat();
  const claude = useClaude();
  const { live: marketLive, setLive } = useMarket();
  const persona = PERSONAS.find((p) => p.id === personaId)!;
  const [data, setData] = useState<Portfolio | null>(null);
  const { accounts } = useAccounts(); // the same list, with the same values, as the Accounts page
  const [accountType, setAccountType] = useState("Non-registered");
  const [market, setMarket] = useState<MarketStatus | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [check, setCheck] = useState<TradeCheck | null>(null);
  const [deltas, setDeltas] = useState<Record<string, number>>({}); // fictional share changes
  const [cashDelta, setCashDelta] = useState(0);
  const [shares, setShares] = useState("");
  const [note, setNote] = useState<string | null>(null);
  const [warnOpen, setWarnOpen] = useState(false); // the signals popup, shown every time Buy or Sell is clicked
  const cardRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let live = true;
    api
      .portfolio(personaId, accountType, marketLive)
      .then((result) => {
        if (!live) return;
        setData(result);
        setError(null);
      })
      .catch((reason) => {
        if (live) setError(reason instanceof Error ? reason.message : translate("holdings.err.load"));
      });
    api.market(marketLive).then((status) => live && setMarket(status)).catch(() => {});
    return () => {
      live = false;
    };
  }, [personaId, accountType, marketLive]);

  // Tell the agents who is selected: the investor and account are saved to S3 whenever they change.
  // Wait until the saved investor has been read, so a profile Claude just sent is applied, not overwritten.
  useEffect(() => {
    if (!claude.ready) return;
    api.setInvestor(personaId, accountType, claude.profile?.submitted_at ?? null).catch(() => {}); // a failed save is repaired by the next trade check
  }, [personaId, accountType, claude.ready, claude.profile?.submitted_at]);

  const refreshed = data?.refreshed ?? false;

  // Bring the trade card into view every time a Buy/Sell click opens one, even for the same stock.
  useEffect(() => {
    if (check) cardRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [check]);

  async function refreshMarket() {
    setRefreshing(true);
    setError(null);
    try {
      setMarket(await api.refreshMarket());
      setLive(true);
      setData(await api.portfolio(personaId, accountType, true));
      setCheck(null);
      setNote(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t("holdings.err.refresh"));
    } finally {
      setRefreshing(false);
    }
  }

  async function resetMarket() {
    setMarket(await api.resetMarket());
    setLive(false);
    setData(await api.portfolio(personaId, accountType, false));
    setCheck(null);
    setDeltas({});
    setCashDelta(0);
    setNote(null);
  }

  async function startTrade(ticker: string, action: TradeAction) {
    setNote(null);
    try {
      const holding = data?.holdings.find((h) => h.ticker === ticker);
      const owned = holding ? holding.shares + (deltas[ticker] ?? 0) : 0;
      setShares(String(Math.max(1, Math.round(owned * 0.1))));
      setCheck(await api.tradeCheck(ticker, action, personaId, marketLive, accountType));
      setWarnOpen(true);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t("holdings.err.check"));
    }
  }

  const sharesOf = (h: Holding) => Math.max(0, h.shares + (deltas[h.ticker] ?? 0));
  const rows = data?.holdings ?? [];
  const cash = (data?.cash_cad ?? 0) + cashDelta;
  const invested = rows.reduce((sum, h) => sum + sharesOf(h) * h.price, 0);
  const total = invested + cash;
  const tradeHolding = check ? rows.find((h) => h.ticker === check.ticker) : undefined;
  const qty = Number.parseFloat(shares);
  const price = tradeHolding?.price ?? 0;
  const amount = Number.isFinite(qty) ? qty * price : 0;
  const owned = tradeHolding ? sharesOf(tradeHolding) : 0;
  const tradeError =
    !check || !Number.isFinite(qty) || qty <= 0
      ? t("holdings.err.zero")
      : check.action === "sell" && qty > owned + 1e-9
        ? t("holdings.err.onlyHold", { owned: fmtNumber(owned, 2) })
        : check.action === "buy" && amount > cash + 1e-9
          ? t("holdings.err.cash", { cash: fmtCad(cash) })
          : null;

  function backOut() {
    if (check) setNote(t(check.action === "buy" ? "holdings.note.cancelBuy" : "holdings.note.cancelSell", { ticker: check.ticker }));
    setWarnOpen(false);
    setCheck(null);
  }

  /** Close the popup and ask the assistant, where the full detail lives. */
  function openDetails() {
    if (!check) return;
    const question = t(check.action === "buy" ? "warn.q.buy" : "warn.q.sell", { ticker: check.ticker });
    setWarnOpen(false);
    setCheck(null);
    chat.openChat();
    chat.send(question);
  }

  function confirmTrade() {
    if (!check || tradeError) return;
    const sign = check.action === "buy" ? 1 : -1;
    setDeltas((d) => ({ ...d, [check.ticker]: (d[check.ticker] ?? 0) + sign * qty }));
    setCashDelta((c) => c - sign * amount);
    setNote(
      t(check.action === "buy" ? "holdings.note.bought" : "holdings.note.sold", {
        qty: fmtNumber(qty, 2),
        ticker: check.ticker,
        amount: fmtCad(amount),
      })
    );
    setCheck(null);
  }

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 sm:p-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-2xl font-semibold">{t("holdings.title", { name: persona.name })}</h2>
          <p className="text-xs text-slate-500">
            {refreshed
              ? t("holdings.refreshed", { rows: market?.new_price_rows ?? 0, headlines: market?.new_headlines ?? 0 })
              : t("holdings.refreshHint")}
          </p>
        </div>
        <div className="w-full sm:max-w-[31rem]">
          <div className="mb-1.5 flex items-center justify-between">
            <span className="text-[10px] font-bold uppercase tracking-[0.14em] text-slate-500">
              {t("holdings.account")}
            </span>
            <span className="text-[10px] text-slate-400">{t("holdings.accountHint")}</span>
          </div>
          <div className="grid grid-cols-3 gap-1 rounded-xl bg-slate-100 p-1 ring-1 ring-slate-200">
            {accounts.map((account) => {
              const active = account.type === accountType;
              return (
                <button
                  key={account.id}
                  type="button"
                  aria-pressed={active}
                  onClick={() => {
                    setAccountType(account.type);
                    setCheck(null);
                    setDeltas({});
                    setCashDelta(0);
                    setNote(null);
                  }}
                  className={`group rounded-lg px-2.5 py-2 text-left transition ${
                    active
                      ? "bg-white text-navy shadow-sm ring-1 ring-slate-200"
                      : "text-slate-500 hover:bg-white/70 hover:text-slate-800"
                  }`}
                >
                  <span className="flex items-center gap-1.5">
                    <span className="truncate text-[11px] font-semibold">{accountName(account.name)}</span>
                  </span>
                  <span className="mt-1 block text-[10px] tabular-nums text-slate-400">
                    {fmtCad(accountValue(account))}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-3">
          {refreshed ? (
            <>
              <span className="flex items-center gap-2 rounded-full bg-emerald-50 px-4 py-2 text-sm font-medium text-emerald-700 ring-1 ring-emerald-200">
                <span className="h-2 w-2 rounded-full bg-emerald-500" /> {t("holdings.updated")}
              </span>
              <button type="button" onClick={resetMarket} className="text-xs font-medium text-slate-500 hover:text-slate-800 hover:underline">
                {t("holdings.reset")}
              </button>
            </>
          ) : (
            <button
              type="button"
              onClick={refreshMarket}
              disabled={refreshing}
              className="flex items-center gap-2 rounded-full bg-brand-500 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-brand-600 disabled:cursor-wait disabled:opacity-70"
            >
              <span className={refreshing ? "animate-spin" : ""} aria-hidden>↻</span>
              {refreshing ? t("holdings.loading") : t("holdings.refresh")}
            </button>
          )}
        </div>
      </div>

      {error && <p className="mt-3 text-sm text-red-600">{error}</p>}

      {data && (
        <dl className="mt-5 grid grid-cols-3 divide-x divide-slate-200 rounded-md bg-slate-50 ring-1 ring-slate-200">
          {[
            [t("holdings.total"), total],
            [t("holdings.invested"), invested],
            [t("holdings.cash"), cash],
          ].map(([label, value], i) => (
            <div key={label as string} className="px-4 py-3">
              <dt className="text-[11px] uppercase tracking-wide text-slate-500">{label}</dt>
              <dd className={`tabular-nums ${i === 0 ? "text-2xl font-semibold" : "text-lg font-medium text-slate-700"}`}>
                {fmtCad(value as number)}
              </dd>
            </div>
          ))}
        </dl>
      )}

      <div className="mt-5 overflow-hidden rounded-md ring-1 ring-slate-200">
        <div className="grid grid-cols-[1fr_auto_auto] items-center gap-x-4 bg-slate-50 px-4 py-2 text-[11px] font-medium uppercase tracking-wide text-slate-500 sm:grid-cols-[minmax(5rem,1fr)_7rem_7.5rem_5rem_9rem]">
          <span>{t("holdings.col.holding")}</span>
          <span className="hidden text-right sm:block">{t("holdings.col.shares")}</span>
          <span className="text-right">{t("holdings.col.value")}</span>
          <span className="hidden text-right sm:block">{t("holdings.col.change")}</span>
          <span className="text-right">{t("holdings.col.trade")}</span>
        </div>
        <ul className="divide-y divide-slate-200">
          {rows.map((h) => (
            <li
              key={h.ticker}
              className="grid grid-cols-[1fr_auto_auto] items-center gap-x-4 px-4 py-3 text-sm sm:grid-cols-[minmax(5rem,1fr)_7rem_7.5rem_5rem_9rem]"
            >
              <span className="font-semibold text-slate-800">{h.ticker}</span>
              <span className="hidden text-right tabular-nums text-slate-500 sm:block">{fmtNumber(sharesOf(h), 2)}</span>
              <span className="text-right font-medium tabular-nums">{fmtCad(sharesOf(h) * h.price)}</span>
              <span
                className={`hidden text-right text-xs font-semibold tabular-nums sm:block ${
                  !refreshed || h.move_pct === 0 ? "text-slate-400" : h.move_pct < 0 ? "text-red-600" : "text-emerald-600"
                }`}
              >
                {refreshed ? `${h.move_pct > 0 ? "+" : ""}${fmtPercent(h.move_pct, 1)}` : "—"}
              </span>
              <span className="flex justify-end gap-1.5">
                {(["buy", "sell"] as const).map((action) => (
                  <button
                    key={action}
                    type="button"
                    disabled={!refreshed}
                    onClick={() => startTrade(h.ticker, action)}
                    title={refreshed ? t(action === "buy" ? "holdings.buyTitle" : "holdings.sellTitle", { ticker: h.ticker }) : t("holdings.refreshFirst")}
                    className={`rounded-full px-3 py-1 text-xs font-semibold ring-1 transition disabled:cursor-not-allowed disabled:opacity-35 ${
                      action === "buy"
                        ? "text-emerald-700 ring-emerald-300 hover:bg-emerald-50"
                        : "text-red-700 ring-red-300 hover:bg-red-50"
                    }`}
                  >
                    {t(action === "buy" ? "holdings.buy" : "holdings.sell")}
                  </button>
                ))}
              </span>
            </li>
          ))}
        </ul>
      </div>

      {check && !warnOpen && (
        <div ref={cardRef} className="mt-4 scroll-mt-20 rounded-md bg-slate-50 p-4 ring-1 ring-slate-200">
          <div className="text-sm font-medium">
            {t(check.action === "buy" ? "holdings.cardBuy" : "holdings.cardSell", { ticker: check.ticker })}
          </div>
          <div className="mt-3 grid gap-3 rounded-md bg-white p-3 ring-1 ring-slate-200 sm:grid-cols-3">
            <label className="text-xs text-slate-600">
              {t("holdings.sharesLabel")}
              <input
                type="number"
                min="0"
                step="any"
                value={shares}
                onChange={(e) => setShares(e.target.value)}
                className="mt-1 w-full rounded-md px-3 py-2 text-sm text-slate-900 ring-1 ring-slate-300 outline-none focus:ring-2 focus:ring-navy"
              />
            </label>
            <label className="text-xs text-slate-600">
              {t("holdings.amountLabel")}
              <input
                type="number"
                min="0"
                step="any"
                value={Number.isFinite(amount) && amount > 0 ? amount.toFixed(2) : ""}
                onChange={(e) => {
                  const value = Number.parseFloat(e.target.value);
                  setShares(price > 0 && Number.isFinite(value) ? String(Math.round((value / price) * 100) / 100) : "");
                }}
                className="mt-1 w-full rounded-md px-3 py-2 text-sm text-slate-900 ring-1 ring-slate-300 outline-none focus:ring-2 focus:ring-navy"
              />
            </label>
            <div className="text-xs text-slate-600">
              {t("holdings.priceHold")}
              <div className="mt-1 py-2 text-sm font-medium text-slate-900">
                {t("holdings.priceHoldValue", { price: fmtNumber(price, 2), owned: fmtNumber(owned, 2) })}
              </div>
            </div>
            <p className="text-xs text-slate-500 sm:col-span-3">
              {tradeError ??
                t("holdings.tradeSummary", {
                  pct: fmtNumber((amount / Math.max(total, 1)) * 100, 1),
                  cash: fmtCad(cash + (check.action === "buy" ? -amount : amount)),
                })}
            </p>
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={confirmTrade}
              disabled={tradeError !== null}
              className="rounded-full bg-brand-500 px-4 py-2 text-sm font-medium text-white transition hover:bg-brand-600 disabled:opacity-40"
            >
              {Number.isFinite(qty) && qty > 0
                ? t(check.action === "buy" ? "holdings.confirmBuy" : "holdings.confirmSell", { qty: fmtNumber(qty, 2) })
                : t(check.action === "buy" ? "holdings.confirmBuyNoQty" : "holdings.confirmSellNoQty")}
            </button>
            <button
              type="button"
              onClick={() => {
                setNote(t(check.action === "buy" ? "holdings.note.cancelBuy" : "holdings.note.cancelSell", { ticker: check.ticker }));
                setCheck(null);
              }}
              className="rounded-full px-4 py-2 text-sm font-medium text-slate-700 ring-1 ring-slate-300 transition hover:bg-white"
            >
              {t("holdings.cancel")}
            </button>
          </div>
        </div>
      )}

      {warnOpen && check && <TradeWarningDialog check={check} onBack={backOut} onProceed={() => setWarnOpen(false)} onDetails={openDetails} />}

      {note && <p className="mt-3 text-sm text-slate-600">{note}</p>}
    </section>
  );
}
