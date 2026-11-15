import { getLang } from "./index";

const locale = () => (getLang() === "fr" ? "fr-CA" : "en-CA");

/** Whole dollars in CAD: "$150,000" in English, "150 000 $" in French. */
export const fmtCad = (amount: number) =>
  new Intl.NumberFormat(locale(), { style: "currency", currency: "CAD", maximumFractionDigits: 0 }).format(amount);

/** A plain number with a fixed count of decimals, using the language's separators. */
export const fmtNumber = (value: number, digits = 0) =>
  new Intl.NumberFormat(locale(), { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(value);

/** A value already expressed as a percentage ("12.5" becomes "12.5%" or "12,5 %"). */
export const fmtPercent = (value: number, digits = 0) =>
  `${fmtNumber(value, digits)}${getLang() === "fr" ? " %" : "%"}`;

/** Like fmtPercent but with an explicit plus sign for gains. */
export const fmtSignedPercent = (value: number, digits = 1) => `${value > 0 ? "+" : ""}${fmtPercent(value, digits)}`;

export const fmtSigned = (value: number, digits = 2) => `${value > 0 ? "+" : ""}${fmtNumber(value, digits)}`;

export const fmtLongDate = (date: Date) =>
  date.toLocaleDateString(locale(), { weekday: "long", month: "short", day: "numeric" });

/** An ISO date such as "2026-11-12" as a short readable date. */
export const fmtShortDate = (iso: string) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString(locale(), { year: "numeric", month: "short", day: "numeric" });
