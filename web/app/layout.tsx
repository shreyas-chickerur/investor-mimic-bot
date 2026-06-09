import type { Metadata } from "next";
import { Bricolage_Grotesque, Manrope, JetBrains_Mono } from "next/font/google";
import "./globals.css";

// Self-hosted via next/font — no runtime @import per spec.
const bricolage = Bricolage_Grotesque({
  subsets: ["latin"],
  weight: ["500", "700", "800"],
  variable: "--font-bricolage",
  display: "swap",
});

const manrope = Manrope({
  subsets: ["latin"],
  weight: ["400", "500", "700"],
  variable: "--font-manrope",
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "700"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Investor Mimic — Automated Quant Trading Dashboard",
  description:
    "A fully automated, regime-aware quantitative trading system. 9 strategies, daily GitHub Actions pipeline, paper trading with Alpaca. Read-only public snapshot — no live broker access.",
  openGraph: {
    title: "Investor Mimic",
    description: "Automated quant trading dashboard — 9 strategies, daily execution, public read-only snapshot.",
    type: "website",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${bricolage.variable} ${manrope.variable} ${jetbrainsMono.variable}`}>
      <body>{children}</body>
    </html>
  );
}
