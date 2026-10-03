import type {
  DashboardEnvelope,
  FixtureMatrixEnvelope,
  PlayerMarketEnvelope,
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
): Promise<DashboardEnvelope> {
  const normalized = teamId.trim();
  if (!/^\d+$/.test(normalized)) {
    throw new Error("Enter a numeric FPL Team ID");
  }

  const response = await fetch(`${API_BASE_URL}/api/v1/dashboard/${normalized}`, {
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
