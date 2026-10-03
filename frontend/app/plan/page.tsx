import type { Metadata } from "next";

import { PlanWorkspace } from "@/components/plan/PlanWorkspace";

export const metadata: Metadata = { title: "Plan & Transfers" };

export default function PlanPage() {
  return <PlanWorkspace />;
}
