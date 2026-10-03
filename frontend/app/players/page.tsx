import type { Metadata } from "next";

import { PlayersWorkspace, type PlayersSearch } from "@/components/players/PlayersWorkspace";

export const metadata: Metadata = { title: "Players" };

export default async function PlayersPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const params = await searchParams;
  const first = (value: string | string[] | undefined) => (Array.isArray(value) ? value[0] : value);
  const search: PlayersSearch = { position: first(params.position), q: first(params.q), compare: first(params.compare), sort: first(params.sort) };
  return <PlayersWorkspace search={search} />;
}
