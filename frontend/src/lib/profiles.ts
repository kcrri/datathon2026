/** Risk types and the fictional persona each one is modelled on. Labels come from the i18n dictionary. */
export const RISK_PROFILES = [
  { id: "conservative", persona: "Robert", horizon: "short", level: 1 },
  { id: "balanced", persona: "Mateo", horizon: "mid", level: 2 },
  { id: "growth", persona: "Amira", horizon: "long", level: 3 },
] as const;

export const RISK_LEVEL: Record<string, number> = { conservative: 1, balanced: 2, growth: 3 };
