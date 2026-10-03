import type { Metadata } from "next";

import { SettingsWorkspace } from "@/components/settings/SettingsWorkspace";

export const metadata: Metadata = { title: "Settings" };

export default function SettingsPage() {
  return <SettingsWorkspace />;
}
