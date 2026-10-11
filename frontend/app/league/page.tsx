import type { Metadata } from "next";

import { LeagueWorkspace } from "@/components/league/LeagueWorkspace";

export const metadata: Metadata = { title: "Mini-leagues" };

export default function LeaguePage() {
  return <LeagueWorkspace />;
}
