import type { Metadata } from "next";

import { FixturesWorkspace } from "@/components/fixtures/FixturesWorkspace";

export const metadata: Metadata = { title: "Fixtures" };

export default function FixturesPage() {
  return <FixturesWorkspace />;
}
