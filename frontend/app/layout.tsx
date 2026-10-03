import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";

import type { ReactNode } from "react";
import { TeamProvider } from "./providers/TeamProvider";
import { AppShell } from "@/components/shell/AppShell";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: {
    default: "FPL-AI · Gameweek intelligence",
    template: "%s · FPL-AI",
  },
  description: "Independent Fantasy Premier League decision support: transfers, captaincy, lineup, chips and a live Gameweek cockpit. Recommendations only; FPL-AI never changes your official team.",
};

export const viewport: Viewport = {
  themeColor: "#060811",
  colorScheme: "dark",
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable}`}>
      <body>
        <TeamProvider>
          <AppShell>{children}</AppShell>
        </TeamProvider>
      </body>
    </html>
  );
}
