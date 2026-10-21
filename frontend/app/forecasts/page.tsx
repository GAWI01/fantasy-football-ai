import type { Metadata } from "next";

import { ForecastsWorkspace } from "@/components/forecasts/ForecastsWorkspace";

export const metadata: Metadata = { title: "Match forecasts" };

export default function ForecastsPage() {
  return <ForecastsWorkspace />;
}
