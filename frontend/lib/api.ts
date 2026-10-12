import type {
  ChipSquadsEnvelope,
  DashboardEnvelope,
  EvaluationEnvelope,
  LeagueEnvelope,
  LeaguesEnvelope,
  RivalEnvelope,
  FixtureMatrixEnvelope,
  PlayerMarketEnvelope,
  PriceChangesEnvelope,
  ReviewEnvelope,
  StatusEnvelope,
} from "./contracts";


export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL?.trim().replace(/\/$/, "") ?? "";


export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}


async function readJson<T>(response: Response): Promise<T> {
  const body = (await response.json().catch(() => null)) as
    | { detail?: unknown }
    | T
    | null;

  if (!response.ok) {
    const detail =
      body && typeof body === "object" && "detail" in body
        ? body.detail
        : null;
    throw new ApiError(
      response.status,
      typeof detail === "string"
        ? detail
        : `The Fantasy Football AI API returned ${response.status}`,
    );
  }

  if (
    !body
    || typeof body !== "object"
    || !("data" in body)
    || !("meta" in body)
    || !("errors" in body)
    || !Array.isArray(body.errors)
  ) {
    throw new Error("The Fantasy Football AI API returned an invalid envelope");
  }

  return body as T;
}


function assertDashboardContract(value: DashboardEnvelope): DashboardEnvelope {
  const team = value.data && typeof value.data === "object" ? value.data.team : null;
  if (
    !team
    || typeof team !== "object"
    || !Number.isInteger(team.team_id)
    || typeof team.name !== "string"
    || !Array.isArray(team.picks)
    || typeof value.meta?.generated_at !== "string"
  ) {
    throw new Error("The Fantasy Football AI API returned an invalid dashboard contract");
  }
  return value;
}


export async function fetchDashboard(
  teamId: string,
  signal?: AbortSignal,
  freeTransfers?: number | null,
): Promise<DashboardEnvelope> {
  const normalized = teamId.trim();
  if (!/^\d+$/.test(normalized)) {
    throw new Error("Enter a numeric FPL Team ID");
  }
  const query = freeTransfers == null ? "" : `?free_transfers=${freeTransfers}`;

  const response = await fetch(`${API_BASE_URL}/api/v1/dashboard/${normalized}${query}`, {
    cache: "no-store",
    signal,
  });
  return assertDashboardContract(await readJson<DashboardEnvelope>(response));
}


export async function fetchStatus(signal?: AbortSignal): Promise<StatusEnvelope> {
  const response = await fetch(`${API_BASE_URL}/api/v1/status`, {
    cache: "no-store",
    signal,
  });
  return readJson<StatusEnvelope>(response);
}


export async function fetchReview(
  teamId: string,
  event?: number,
  signal?: AbortSignal,
): Promise<ReviewEnvelope> {
  const normalized = teamId.trim();
  if (!/^\d+$/.test(normalized)) {
    throw new Error("Enter a numeric FPL Team ID");
  }
  if (event !== undefined && (!Number.isInteger(event) || event < 1 || event > 38)) {
    throw new Error("Gameweek must be between 1 and 38");
  }
  const query = event === undefined ? "" : `?event=${event}`;
  const response = await fetch(
    `${API_BASE_URL}/api/v1/review/${normalized}${query}`,
    { cache: "no-store", signal },
  );
  return readJson<ReviewEnvelope>(response);
}


export async function fetchFixtureMatrix(
  horizon = 5,
  signal?: AbortSignal,
): Promise<FixtureMatrixEnvelope> {
  if (!Number.isInteger(horizon) || horizon < 1 || horizon > 8) {
    throw new Error("Fixture horizon must be between 1 and 8");
  }
  const response = await fetch(
    `${API_BASE_URL}/api/v1/fixture-matrix?horizon=${horizon}`,
    { cache: "no-store", signal },
  );
  return readJson<FixtureMatrixEnvelope>(response);
}


export async function fetchPlayers(
  limit = 50,
  signal?: AbortSignal,
): Promise<PlayerMarketEnvelope> {
  if (!Number.isInteger(limit) || limit < 1 || limit > 700) {
    throw new Error("Player limit must be between 1 and 700");
  }
  const response = await fetch(
    `${API_BASE_URL}/api/v1/players?limit=${limit}`,
    { cache: "no-store", signal },
  );
  return readJson<PlayerMarketEnvelope>(response);
}


/** Score the manager's own transfers on the same scale as the recommendation. */
export async function fetchEvaluation(
  teamId: string,
  sell: number[],
  buy: number[],
  freeTransfers?: number | null,
  signal?: AbortSignal,
): Promise<EvaluationEnvelope> {
  const normalized = teamId.trim();
  if (!/^\d+$/.test(normalized)) throw new Error("Enter a numeric FPL Team ID");
  if (!sell.length || sell.length !== buy.length) throw new Error("Choose a player to sell and a player to buy");
  const params = new URLSearchParams({ sell: sell.join(","), buy: buy.join(",") });
  if (freeTransfers != null) params.set("free_transfers", String(freeTransfers));
  const response = await fetch(`${API_BASE_URL}/api/v1/evaluate/${normalized}?${params}`, { cache: "no-store", signal });
  return readJson<EvaluationEnvelope>(response);
}


/** Official FPL price-change progress and projections for every player. */
export async function fetchPriceChanges(signal?: AbortSignal): Promise<PriceChangesEnvelope> {
  const response = await fetch(`${API_BASE_URL}/api/v1/price-changes`, { cache: "no-store", signal });
  return readJson<PriceChangesEnvelope>(response);
}

/** The best Free Hit and Wildcard squads within the manager's budget. */
export async function fetchChipSquads(teamId: string, preferRisers = false, signal?: AbortSignal): Promise<ChipSquadsEnvelope> {
  const query = preferRisers ? "?prefer_risers=true" : "";
  const response = await fetch(`${API_BASE_URL}/api/v1/chip-squads/${numericId(teamId, "FPL Team ID")}${query}`, { cache: "no-store", signal });
  return readJson<ChipSquadsEnvelope>(response);
}

function numericId(value: string | number, label: string): string {
  const text = String(value).trim();
  if (!/^\d+$/.test(text)) throw new Error(`Enter a numeric ${label}`);
  return text;
}

export async function fetchLeagues(teamId: string, signal?: AbortSignal): Promise<LeaguesEnvelope> {
  const response = await fetch(`${API_BASE_URL}/api/v1/leagues/${numericId(teamId, "FPL Team ID")}`, { cache: "no-store", signal });
  return readJson<LeaguesEnvelope>(response);
}

export async function fetchLeague(leagueId: number, teamId: string, signal?: AbortSignal): Promise<LeagueEnvelope> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/league/${numericId(leagueId, "league ID")}?team_id=${numericId(teamId, "FPL Team ID")}`,
    { cache: "no-store", signal },
  );
  return readJson<LeagueEnvelope>(response);
}

export async function fetchRival(leagueId: number, rivalId: number, teamId: string, signal?: AbortSignal): Promise<RivalEnvelope> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/league/${numericId(leagueId, "league ID")}/rival/${numericId(rivalId, "rival ID")}?team_id=${numericId(teamId, "FPL Team ID")}`,
    { cache: "no-store", signal },
  );
  return readJson<RivalEnvelope>(response);
}
