import { translateOr } from "./index";

/** "Short-Term Agent" and "short_term_agent" both become "short_term_agent". */
const normalise = (value: string) =>
  value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");

/** Display name of an agent, from either a backend id or a chat label. Unknown names pass through. */
export const agentName = (agent: string) => translateOr(`agent.${normalise(agent)}`, agent);

const ACCOUNT_TYPES = ["Non-registered", "TFSA", "RRSP", "FHSA"];

/** "TFSA" becomes "CELI" in French. */
export const accountTypeLabel = (type: string) => translateOr(`account.${type}`, type);

/** "TFSA #1" becomes "CELI #1" in French. */
export function accountName(name: string) {
  const type = ACCOUNT_TYPES.find((candidate) => name.startsWith(candidate));
  return type ? accountTypeLabel(type) + name.slice(type.length) : name;
}

export const riskLabel = (risk: string, fallback = risk) => translateOr(`risk.${risk}`, fallback);

/** Display name of a strategy, from a key ("growth") or a backend label ("Balanced Index"). */
export const strategyLabel = (strategy: string) => translateOr(`strategy.${normalise(strategy)}`, strategy);

export const metricLabel = (evidenceId: string, fallback: string) => translateOr(evidenceId, fallback);

/** Text of one analysis trace step, from its id (and agent, for strategy steps). */
export function traceAction(step: { step_id: string; agent: string; action: string }) {
  const key = step.step_id.startsWith("strategy.") ? `trace.strategy.${step.agent}` : `trace.${step.step_id}`;
  return translateOr(key, step.action);
}

export const governanceTitle = (ruleId: string) => translateOr(`rule.${ruleId}.title`, ruleId.replaceAll("_", " "));
export const governanceMessage = (ruleId: string, fallback: string) => translateOr(`rule.${ruleId}.message`, fallback);

const WINDOW = /^The analysis window is (\S+) through (\S+) \((\d+) common observations\)\.$/;

/** Assumptions and limitations arrive as English sentences; match them to their translation. */
export function noteText(sentence: string) {
  const window = WINDOW.exec(sentence);
  if (window) return translateOr("note.window", sentence, { from: window[1], to: window[2], n: window[3] });
  return translateOr(`note.${sentence}`, sentence);
}

/** A raw data-source reference (an s3:// path with version info) as a readable name. */
export function sourceLabel(reference: string) {
  if (/prices_daily/i.test(reference)) return translateOr("source.prices", "Daily market prices");
  if (/fx_usdcad/i.test(reference)) return translateOr("source.fx", "USD/CAD exchange rates");
  if (/manifest/i.test(reference)) return translateOr("source.manifest", "Data integrity record");
  if (/macro/i.test(reference)) return translateOr("source.macro", "Interest-rate and economic data");
  return translateOr("source.other", "Market data file");
}
