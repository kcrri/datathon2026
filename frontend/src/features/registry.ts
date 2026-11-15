/**
 * The dashboard's pages. This is the one place to add, rename or reorder one.
 *
 * A feature is either a page (has a `path`, gets a tab) or a widget (`path: null`, rendered by
 * the dashboard shell on every page, like the assistant drawer). Its label and description are
 * in the i18n dictionary as `feature.<id>.label` and `feature.<id>.description`.
 *
 * To add a page:
 *   1. add an entry here,
 *   2. add its label and description to `src/i18n/en.ts` and `src/i18n/fr.ts`,
 *   3. create `src/app/dashboard/<path>/page.tsx` (keep it thin: render a component),
 *   4. add the same `id` to FEATURE_IDS in `backend/app/services/features.py`
 *      so the admin panel can switch it on and off.
 */
export type FeatureDef = {
  id: string;
  path: string | null;
};

export const FEATURES = [
  { id: "analysis", path: "/dashboard/analysis" },
  { id: "holdings", path: "/dashboard/holdings" },
  { id: "assistant", path: null },
  { id: "accounts", path: "/dashboard/accounts" },
  { id: "insights", path: "/dashboard/insights" },
] as const satisfies readonly FeatureDef[];

export type FeatureId = (typeof FEATURES)[number]["id"];
export type Feature = (typeof FEATURES)[number];

export type PageFeature = Feature & { path: string };

/** Features that are pages: they get a route and a tab. */
export const PAGES = FEATURES.filter((f): f is PageFeature => f.path !== null);

export function featureForPath(pathname: string): PageFeature | undefined {
  return PAGES.find((f) => pathname === f.path || pathname.startsWith(`${f.path}/`));
}
