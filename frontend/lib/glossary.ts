/** Plain-language meanings for the few FPL and model words the app cannot avoid. */
export const GLOSSARY = {
  xp: {
    term: "xP (expected points)",
    text: "The points the model expects a player to score. It is a forecast based on form, fixtures and minutes, not a promise.",
  },
  hit: {
    term: "Hit (−4)",
    text: "Every transfer beyond your free ones costs 4 points from your Gameweek score.",
  },
  freeTransfer: {
    term: "Free transfer",
    text: "You get one free transfer each Gameweek. If you skip it, it carries over, up to five.",
  },
  roll: {
    term: "Saving a transfer",
    text: "Making no transfer this week, so you have one more free transfer next week. Useful when nothing clearly beats your current player.",
  },
  chips: {
    term: "Chips",
    text: "One-off boosts you can play: Wildcard (rebuild your squad for free), Free Hit (a new squad for one week), Bench Boost (your bench scores too) and Triple Captain (captain scores ×3).",
  },
  decisionScore: {
    term: "Decision score",
    text: "How the planner ranks options: expected points gained (later weeks count a little less), minus any hit and a safety margin, minus the value of keeping your free transfer. Doing nothing scores 0.",
  },
  confidence: {
    term: "Confidence",
    text: "How sure the model is. It drops when players are doubtful, the gain is small or the forecast is early.",
  },
  xmins: {
    term: "xMins (expected minutes)",
    text: "How many minutes the model expects a player to play. Below 60 often means a doubt or rotation.",
  },
  provisional: {
    term: "Early forecast",
    text: "The previous Gameweek is still being played, so this forecast does not include its results yet. It updates when the Gameweek ends.",
  },
} as const;

export type GlossaryKey = keyof typeof GLOSSARY;
