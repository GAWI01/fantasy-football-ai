import type { Metadata, Viewport } from "next";
import { Barlow_Condensed, Geist, Geist_Mono } from "next/font/google";

import type { ReactNode } from "react";
import { TeamProvider } from "./providers/TeamProvider";
import { AppShell } from "@/components/shell/AppShell";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const display = Barlow_Condensed({
  variable: "--font-display-face",
  subsets: ["latin", "latin-ext"],
  weight: ["500", "600", "700", "800"],
  style: ["normal", "italic"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: {
    default: "Fantasy Football AI · Gameweek intelligence",
    template: "%s · Fantasy Football AI",
  },
  description: "Independent Fantasy Premier League decision support: transfers, captaincy, lineup, chips and a live Gameweek cockpit. Fantasy Football AI is an independent, free tool and never changes your official team.",
};

export const viewport: Viewport = {
  themeColor: "#04060d",
  colorScheme: "dark",
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} ${display.variable}`}>
      <body>
        <TeamProvider>
          <AppShell>{children}</AppShell>
        </TeamProvider>
      </body>
    </html>
  );
}
