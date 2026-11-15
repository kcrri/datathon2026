"use client";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect } from "react";
import { useFeatureFlags } from "@/features/flags";
import { useLanguage } from "@/i18n";
import { PAGES } from "@/features/registry";

/** /dashboard forwards to the first enabled page, keeping the query string. */
export default function DashboardIndex() {
  const router = useRouter();
  const query = useSearchParams().toString();
  const { loaded, isEnabled } = useFeatureFlags();
  const { t } = useLanguage();
  const first = PAGES.find((f) => isEnabled(f.id));

  useEffect(() => {
    if (loaded && first) router.replace(query ? `${first.path}?${query}` : first.path);
  }, [loaded, first, query, router]);

  if (loaded && !first) {
    return (
      <div className="rounded-lg bg-white p-8 text-center ring-1 ring-slate-200">
        <h2 className="text-xl font-semibold">{t("shell.allOff.title")}</h2>
        <p className="mt-2 text-sm text-slate-600">
          <Link href="/admin" className="font-medium text-link hover:underline">
            {t("shell.off.openAdmin")}
          </Link>{" "}
          {t("shell.allOff.suffix")}
        </p>
      </div>
    );
  }
  return null;
}
