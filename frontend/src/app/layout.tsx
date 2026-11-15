import type { Metadata } from "next";
import { Geist_Mono, Montserrat } from "next/font/google";
import { FeatureFlagsProvider } from "@/features/flags";
import { LanguageBoot } from "@/i18n/LanguageBoot";
import "./globals.css";

const brandFont = Montserrat({
  variable: "--font-brand",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "PortfolioGuard AI",
  description: "Evidence-backed fictional portfolio comparison for AlphaForge AI",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" data-scroll-behavior="smooth">
      <body
        className={`${brandFont.variable} ${geistMono.variable} antialiased`}
        suppressHydrationWarning
      >
        <LanguageBoot />
        <FeatureFlagsProvider>{children}</FeatureFlagsProvider>
      </body>
    </html>
  );
}
