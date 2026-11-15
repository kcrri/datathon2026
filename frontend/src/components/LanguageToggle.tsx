"use client";
import { useLanguage, type Lang } from "@/i18n";

const OPTIONS: { lang: Lang; label: string; name: string }[] = [
  { lang: "en", label: "EN", name: "English" },
  { lang: "fr", label: "FR", name: "Français" },
];

/** Two-way switch between English and French. The choice is remembered in the browser. */
export function LanguageToggle({ className = "" }: { className?: string }) {
  const { lang, setLang, t } = useLanguage();
  return (
    <div
      role="group"
      aria-label={t("lang.switch")}
      className={`inline-flex rounded-full bg-white p-0.5 text-xs font-semibold ring-1 ring-slate-300 ${className}`}
    >
      {OPTIONS.map((option) => (
        <button
          key={option.lang}
          type="button"
          lang={option.lang}
          title={option.name}
          aria-pressed={lang === option.lang}
          onClick={() => setLang(option.lang)}
          className={`rounded-full px-3 py-1 transition ${
            lang === option.lang ? "bg-brand-500 text-white" : "text-slate-600 hover:bg-slate-50"
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
