"use client";
import { useEffect } from "react";
import { bootLanguage } from "./index";

/** Loads the saved language once the page has hydrated. Render it before the rest of the app. */
export function LanguageBoot() {
  useEffect(() => {
    bootLanguage();
  }, []);
  return null;
}
