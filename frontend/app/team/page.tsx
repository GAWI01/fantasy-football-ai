import type { Metadata } from "next";

import { TeamWorkspace } from "@/components/team/TeamWorkspace";

export const metadata: Metadata = { title: "My Team" };

export default function TeamPage() {
  return <TeamWorkspace />;
}
