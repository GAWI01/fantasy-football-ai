import type { DashboardEnvelope } from "@/lib/contracts";

/**
 * decision: the target deadline is in the future, so recommendations are actionable.
 * live:     the current Gameweek's deadline has passed and it is not finished.
 * settled:  nothing is live and no actionable plan exists (e.g. between GWs before a model refresh).
 */
export type Phase = "decision" | "live" | "settled";

export type SourceKind = "live" | "official" | "model" | "derived" | "cached";

export type GameState = {
  phase: Phase;
  liveActive: boolean;
  actionsOpen: boolean;
  currentEvent: number | null;
  targetEvent: number | null;
  deadline: string | null;
  stale: boolean;
  degraded: boolean;
  generatedAt: string | null;
  officialFetchedAt: string | null;
  modelVersion: string | null;
  failedAreas: Set<string>;
};

export function deriveGameState(envelope: DashboardEnvelope | null, now = Date.now()): GameState {
  if (!envelope) {
    return {
      phase: "settled",
      liveActive: false,
      actionsOpen: false,
      currentEvent: null,
      targetEvent: null,
      deadline: null,
      stale: false,
      degraded: false,
      generatedAt: null,
      officialFetchedAt: null,
      modelVersion: null,
      failedAreas: new Set(),
    };
  }
  const { meta, data } = envelope;
  const live = data.live;
  const liveActive = live?.status === "LIVE" && live.finished !== true;
  // Missing planning metadata fails closed: a plan without a known deadline is never actionable.
  const deadline = meta.target_deadline_time ?? live?.next_deadline_time ?? null;
  const deadlineAt = deadline ? Date.parse(deadline) : Number.NaN;
  const actionsOpen = meta.actions_locked === false && Number.isFinite(deadlineAt) && deadlineAt > now;
  const stale = Boolean(meta.stale ?? meta.official?.stale ?? false);
  return {
    phase: liveActive ? "live" : actionsOpen ? "decision" : "settled",
    liveActive,
    actionsOpen,
    currentEvent: meta.current_event ?? live?.current_event ?? meta.event ?? data.team.event ?? null,
    targetEvent: meta.prediction_event ?? data.team.prediction_event ?? null,
    deadline,
    stale,
    degraded: Boolean(meta.degraded),
    generatedAt: meta.generated_at ?? null,
    officialFetchedAt: meta.official?.fetched_at ?? null,
    modelVersion: meta.prediction_version ?? data.team.prediction_file ?? null,
    failedAreas: new Set(envelope.errors.map((error) => error.area)),
  };
}

/** Official and live widgets degrade to "cached" when the upstream response is stale. */
export function officialSource(state: Pick<GameState, "stale">): SourceKind {
  return state.stale ? "cached" : "official";
}

export function liveSource(state: Pick<GameState, "stale" | "liveActive">): SourceKind {
  if (state.stale) return "cached";
  return state.liveActive ? "live" : "official";
}
