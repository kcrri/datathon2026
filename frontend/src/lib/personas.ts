import { fmtPercent } from "@/i18n/format";
import { translateOr } from "@/i18n";

export { fmtCad as formatCad } from "@/i18n/format";

export type PersonaId = "amira" | "mateo" | "robert";

export type StrategyKey = "growth" | "dividend" | "momentum" | "preservation";

/** Move `amount` (a share of the portfolio) from one strategy to another. */
export type Scenario = { from: StrategyKey; to: StrategyKey; amount: number };

/**
 * The three fictional investors. Only numbers and ids live here; every piece of text
 * (goal, horizon, risk label, scenario question) is in the i18n dictionary under `persona.<id>.*`.
 */
export type Persona = {
  id: PersonaId;
  name: string;
  age: number;
  startingBalance: number; // CAD
  allocations: Record<StrategyKey, number>;
  scenario: Scenario;
};

export const PERSONAS: Persona[] = [
  {
    id: "amira",
    name: "Amira",
    age: 26,
    startingBalance: 15000,
    allocations: { growth: 0.55, dividend: 0.1, momentum: 0.25, preservation: 0.1 },
    scenario: { from: "growth", to: "dividend", amount: 0.2 },
  },
  {
    id: "mateo",
    name: "Mateo",
    age: 41,
    startingBalance: 60000,
    allocations: { growth: 0.3, dividend: 0.35, momentum: 0.1, preservation: 0.25 },
    scenario: { from: "growth", to: "preservation", amount: 0.1 },
  },
  {
    id: "robert",
    name: "Robert",
    age: 59,
    startingBalance: 150000,
    allocations: { growth: 0.15, dividend: 0.3, momentum: 0.05, preservation: 0.5 },
    scenario: { from: "dividend", to: "preservation", amount: 0.1 },
  },
];

/** "55% growth · 25% momentum · …", largest first, in the current language. */
export const allocationLabel = (allocations: Persona["allocations"]) =>
  Object.entries(allocations)
    .sort((a, b) => b[1] - a[1])
    .map(([name, weight]) => `${fmtPercent(weight * 100)} ${translateOr(`strategy.short.${name}`, name)}`)
    .join(" · ");

export const proposedAllocations = (persona: Persona, scenario: Scenario = persona.scenario): Record<StrategyKey, number> => {
  const { from, to, amount } = scenario;
  return {
    ...persona.allocations,
    [from]: persona.allocations[from] - amount,
    [to]: persona.allocations[to] + amount,
  };
};

const SUGGESTION_POOL: Scenario[] = [
  { from: "growth", to: "dividend", amount: 0.1 },
  { from: "growth", to: "preservation", amount: 0.1 },
  { from: "dividend", to: "preservation", amount: 0.1 },
  { from: "momentum", to: "preservation", amount: 0.1 },
  { from: "growth", to: "dividend", amount: 0.2 },
];

const sameScenario = (a: Scenario, b: Scenario) => a.from === b.from && a.to === b.to && a.amount === b.amount;

/** The investor's own scenario first, then a few other shifts they actually have enough in the source strategy to make. */
export const suggestedScenarios = (persona: Persona): Scenario[] => [
  persona.scenario,
  ...SUGGESTION_POOL.filter(
    (item) => persona.allocations[item.from] >= item.amount && !sameScenario(item, persona.scenario)
  ),
].slice(0, 4);

export const STRATEGY_KEYS: StrategyKey[] = ["growth", "dividend", "momentum", "preservation"];
