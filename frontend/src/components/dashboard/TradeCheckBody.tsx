"use client";
import { type Headline, type TradeCheck, type TradeVerdict } from "@/lib/api";
import { useLanguage, type MessageKey } from "@/i18n";
import { fmtNumber } from "@/i18n/format";

const VERDICT_BADGE: Record<TradeVerdict, string> = {
  panic_risk: "bg-amber-100 text-amber-800",
  evidence_supported: "bg-emerald-100 text-emerald-800",
  chasing_risk: "bg-amber-100 text-amber-800",
  falling_knife: "bg-red-100 text-red-800",
  dip_with_context: "bg-sky-100 text-sky-800",
  mixed: "bg-slate-100 text-slate-700",
  no_signal: "bg-slate-100 text-slate-500",
};

export function evidence(check: TradeCheck, key: string) {
  return check.evidence.find((e) => e.evidence_id.endsWith(`:${key}`))?.value ?? null;
}

/** The action and the guard's verdict, named for a normal reader: "Panic sell", "Buying the dip"... */
export function FinalVerdict({ check }: { check: TradeCheck }) {
  const { t, tOr } = useLanguage();
  const label = tOr(`final.${check.action}.${check.verdict}`, t(`verdict.${check.verdict}` as MessageKey));
  return (
    <div className="mt-4 flex items-center gap-2 border-t border-slate-200 pt-3">
      <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">{t("final.label")}</span>
      <span className={`rounded-full px-3 py-1 text-sm font-semibold ${VERDICT_BADGE[check.verdict]}`}>{label}</span>
    </div>
  );
}

type Tone = "upbeat" | "neutral" | "negative";
const toneOf = (value: number): Tone => (value >= 0.3 ? "upbeat" : value <= -0.3 ? "negative" : "neutral");

/** The verdict in one plain sentence, then each signal as a plain classification. Used in the chat. */
export function TradeCheckBody({ check, headlines }: { check: TradeCheck; headlines?: Headline[] | null }) {
  const { t } = useLanguage();
  const k = (key: string) => t(`cls.${key}` as MessageKey);
  const word = (tone: Tone) => {
    const text = t(`holdings.tone.${tone}` as MessageKey);
    return text.charAt(0).toUpperCase() + text.slice(1);
  };

  const drop = -(evidence(check, "drop") ?? 0);
  const rise = evidence(check, "rise") ?? 0;
  const rebound = evidence(check, "rebound") ?? 0;
  const volume = evidence(check, "volume") ?? 1;
  const breadth = evidence(check, "breadth") ?? 0;
  const sentiment = evidence(check, "sentiment");
  const peers = evidence(check, "peer_sentiment");
  const hype = evidence(check, "hype") ?? 0;
  const move = Math.max(drop, rise);

  const rows: Array<[string, string, string?]> = [
    [
      k("price"),
      move < 3 ? k("price.flat") : drop >= rise ? k(move >= 8 ? "price.hugeFall" : "price.bigFall") : k(move >= 8 ? "price.hugeRise" : "price.bigRise"),
      move < 3 ? undefined : t("cls.detail.pct", { n: fmtNumber(Math.round(move)) }),
    ],
  ];
  if (drop >= 3 && drop >= rise) rows.push([k("bounce"), k(rebound >= 3 ? "bounce.strong" : rebound >= 1 ? "bounce.small" : "bounce.none"), rebound >= 1 ? t("cls.detail.pct", { n: fmtNumber(Math.round(rebound)) }) : undefined]);
  rows.push([k("trading"), k(volume >= 2 ? "trading.veryBusy" : volume >= 1.25 ? "trading.busy" : "trading.normal"), volume >= 1.25 ? t("cls.detail.times", { n: fmtNumber(Math.round(volume)) }) : undefined]);
  rows.push([k("others"), k(breadth >= 60 ? "others.most" : breadth >= 30 ? "others.many" : "others.few"), t("cls.detail.ofTracked", { n: fmtNumber(Math.round(breadth)) })]);
  rows.push([k("newsAbout"), k((evidence(check, "company_news") ?? 0) > 50 ? "newsAbout.company" : "newsAbout.market")]);
  if (sentiment !== null) rows.push([k("newsTone"), word(toneOf(sentiment))]);
  if (peers !== null) rows.push([k("peers"), word(toneOf(peers))]);
  if (check.score && check.score.name === "Company-driven vs market-driven") {
    rows.push([k("driver"), k(check.score.value >= 57.5 ? "driver.company" : check.score.value <= 42.5 ? "driver.market" : "driver.mixed")]);
  }
  rows.push([k("hype"), k(hype >= 55 ? "hype.high" : hype >= 35 ? "hype.medium" : "hype.low")]);

  return (
    <>
      <div className="flex items-center gap-2">
        <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${VERDICT_BADGE[check.verdict]}`}>
          {t(`verdict.${check.verdict}` as MessageKey)}
        </span>
        <span className="text-sm font-medium">
          {t(check.action === "buy" ? "holdings.cardBuy" : "holdings.cardSell", { ticker: check.ticker })}
        </span>
      </div>
      <p className="mt-2 text-sm text-slate-700">{t(`plain.${check.verdict}` as MessageKey)}</p>
      <ul className="mt-3 list-disc space-y-1.5 pl-5 text-sm text-slate-700">
        {rows.map(([label, value, detail]) => (
          <li key={label}>
            {label}: <span className="font-medium text-slate-900">{value}</span>
            {detail && <span className="text-slate-500"> ({detail})</span>}
          </li>
        ))}
      </ul>
      {headlines && headlines.length > 0 && (
        <div className="mt-3">
          <div className="text-xs font-semibold text-slate-600">{t("cls.headlines")}</div>
          <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-slate-700">
            {headlines.map((h) => {
              const score = h.sentiment === null || h.sentiment === "" ? null : Number(h.sentiment);
              return (
                <li key={`${h.date}-${h.headline}`}>
                  {h.headline}
                  {score !== null && Number.isFinite(score) && <span className="text-slate-500"> · {word(toneOf(score))}</span>}
                </li>
              );
            })}
          </ul>
        </div>
      )}
      <FinalVerdict check={check} />
    </>
  );
}
