import type { Metadata } from "next";

import { PricesWorkspace } from "@/components/prices/PricesWorkspace";

export const metadata: Metadata = { title: "Price changes" };

export default function PricesPage() {
  return <PricesWorkspace />;
}
