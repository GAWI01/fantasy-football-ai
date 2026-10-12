"use client";

import { createContext, useContext, useId, useLayoutEffect, useRef, type ReactNode } from "react";

import { CountUp } from "@/components/ui/CountUp";
import type { SourceKind } from "@/lib/model/phase";
import { useDataLabels } from "@/lib/preferences";
import { useSectionOpen, type SectionDefaults } from "@/lib/sections";

const SOURCE_COPY: Record<SourceKind, { label: string; hint: string }> = {
  live: { label: "Live", hint: "Live official match data for the Gameweek in progress. Can still change." },
  // "FPL data", not "Official": the data comes from the game, the app is not official.
  official: { label: "FPL data", hint: "Data from the Fantasy Premier League game for your public team. Fantasy Football AI is independent and not affiliated with FPL." },
  model: { label: "Model", hint: "Fantasy Football AI model projection. A forecast, not a result." },
  derived: { label: "Derived", hint: "Calculated by Fantasy Football AI from official and model data." },
  cached: { label: "Cached", hint: "The official FPL service did not respond, so the last cached response is shown." },
};

// Sources already labelled at the top of the surrounding card. A badge for one of
// them inside the card would only repeat it, so it is left out: every number keeps
// a visible source, once per card instead of once per number.
const ScopeSources = createContext<readonly SourceKind[]>([]);

/** Marks a region whose header already shows these sources (used by Card, and by heroes that are not Cards). */
export function SourceScope({ kinds, children }: { kinds: readonly SourceKind[]; children: ReactNode }) {
  return <ScopeSources.Provider value={kinds}>{children}</ScopeSources.Provider>;
}

// Labels that say something about the data right now show even when labels are off.
const ALWAYS_SHOWN: readonly SourceKind[] = ["live", "cached"];

/** `pinned` badges are the region's own header labels. `always` shows a badge even with data labels off (the Settings guide). */
export function SourceBadge({ kind, label, pinned = false, always = false }: { kind: SourceKind; label?: string; pinned?: boolean; always?: boolean }) {
  const scope = useContext(ScopeSources);
  const labels = useDataLabels();
  const copy = SOURCE_COPY[kind];
  if (!always && !labels && !ALWAYS_SHOWN.includes(kind)) return null;
  if (!pinned && !label && scope.includes(kind)) return null;
  return (
    <span className={`src src-${kind}`} title={copy.hint}>
      {kind === "live" ? <i className="src-pulse" aria-hidden="true" /> : null}
      {label ?? copy.label}
    </span>
  );
}

/** Makes a card collapsible: the header opens and closes it, and the choice is remembered. */
export type CardCollapse = {
  id: string;
  /** One line shown while the card is closed, so its gist stays visible. */
  summary?: ReactNode;
  defaults: SectionDefaults;
  /** A stable key for something new that opens the card until the reader closes it. */
  signal?: string | null;
};

const ALWAYS_OPEN: SectionDefaults = { mobile: true, desktop: true };

export function Card({
  title,
  eyebrow,
  source,
  action,
  children,
  className,
  id,
  icon,
  labelledBy,
  tone,
  collapse,
}: {
  title?: ReactNode;
  eyebrow?: ReactNode;
  source?: SourceKind | SourceKind[];
  action?: ReactNode;
  children: ReactNode;
  className?: string;
  id?: string;
  icon?: ReactNode;
  labelledBy?: string;
  tone?: "accent" | "live" | "warn" | "risk";
  collapse?: CardCollapse;
}) {
  const autoId = useId();
  const [stateOpen, toggle] = useSectionOpen(collapse?.id ?? autoId, collapse?.defaults ?? ALWAYS_OPEN, collapse?.signal);
  const open = collapse ? stateOpen : true;
  const sources = source ? (Array.isArray(source) ? source : [source]) : [];
  const headingId = labelledBy ?? (id ? `${id}-title` : collapse ? `${autoId}-title` : undefined);
  const bodyId = `${autoId}-body`;
  const content = sources.length ? <SourceScope kinds={sources}>{children}</SourceScope> : children;
  return (
    <section
      className={["card", tone ? `card-${tone}` : "", collapse ? "card-collapsible" : "", collapse && !open ? "is-collapsed" : "", className].filter(Boolean).join(" ")}
      id={id}
      aria-labelledby={title && headingId ? headingId : undefined}
    >
      {title || action || sources.length ? (
        <header className="card-head">
          <div className="card-title">
            {icon ? <span className="card-icon" aria-hidden="true">{icon}</span> : null}
            <div>
              {eyebrow ? <span className="eyebrow">{eyebrow}</span> : null}
              {title ? (
                <h2 id={headingId}>
                  {collapse ? (
                    <button type="button" className="card-toggle" aria-expanded={open} aria-controls={bodyId} onClick={toggle}>
                      {title}<span className="card-chevron" aria-hidden="true" />
                    </button>
                  ) : title}
                </h2>
              ) : null}
              {collapse?.summary && !open ? <span className="card-summary">{collapse.summary}</span> : null}
            </div>
          </div>
          <div className="card-meta">
            {sources.map((kind) => <SourceBadge key={kind} kind={kind} pinned />)}
            {action}
          </div>
        </header>
      ) : null}
      {collapse ? (
        <div className="card-body" id={bodyId} data-open={open ? "true" : "false"} inert={!open}>
          <div className="card-body-inner">{content}</div>
        </div>
      ) : content}
    </section>
  );
}

export function Stat({
  label,
  value,
  unit,
  sub,
  source,
  tone,
  size = "md",
}: {
  label: ReactNode;
  value: ReactNode;
  unit?: ReactNode;
  sub?: ReactNode;
  source?: SourceKind;
  tone?: "pos" | "neg" | "warn" | "accent" | "live";
  size?: "sm" | "md" | "lg" | "xl";
}) {
  return (
    <div className={`stat stat-${size}`}>
      <span className="stat-label">{label}{source ? <SourceBadge kind={source} /> : null}</span>
      <strong className={["stat-value", tone ? `tone-${tone}` : ""].filter(Boolean).join(" ")}>
        {value}{unit ? <small className="stat-unit">{unit}</small> : null}
      </strong>
      {sub ? <span className="stat-sub">{sub}</span> : null}
    </div>
  );
}

export function Delta({ value, digits = 1, unit, neutralBelow = 0.05, animate = false }: { value: number | null | undefined; digits?: number; unit?: string; neutralBelow?: number; animate?: boolean }) {
  if (typeof value !== "number" || !Number.isFinite(value)) return <span className="delta">—</span>;
  const tone = Math.abs(value) < neutralBelow ? "flat" : value > 0 ? "pos" : "neg";
  const format = (n: number) => (Math.abs(n) < neutralBelow ? (0).toFixed(digits) : `${n > 0 ? "+" : "−"}${Math.abs(n).toFixed(digits)}`);
  const text = tone === "flat" ? (0).toFixed(digits) : format(value);
  return (
    <span className={`delta delta-${tone}`}>
      {animate && tone !== "flat" ? <CountUp value={value} decimals={digits} format={format} /> : text}
      {unit ? <small>{unit}</small> : null}
    </span>
  );
}

export function Meter({ value, tone = "accent", label }: { value: number | null | undefined; tone?: "accent" | "pos" | "warn" | "neg" | "live"; label: string }) {
  const clamped = typeof value === "number" && Number.isFinite(value) ? Math.max(0, Math.min(1, value)) : null;
  return (
    <span className={`meter meter-${tone}`} role="meter" aria-label={label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={clamped == null ? undefined : Math.round(clamped * 100)}>
      <i style={{ width: `${(clamped ?? 0) * 100}%` }} />
    </span>
  );
}

export function Segmented<T extends string>({
  options,
  value,
  onChange,
  label,
  size = "md",
}: {
  options: Array<{ value: T; label: ReactNode; disabled?: boolean }>;
  value: T;
  onChange: (value: T) => void;
  label: string;
  size?: "sm" | "md";
}) {
  const ref = useRef<HTMLDivElement>(null);
  // One pill slides to the pressed option. Measured on the element directly, so
  // it follows wraps and font loading without re-rendering.
  useLayoutEffect(() => {
    const root = ref.current;
    if (!root) return;
    const place = () => {
      const active = root.querySelector<HTMLButtonElement>('button[aria-pressed="true"]');
      if (!active) { delete root.dataset.slide; return; }
      root.style.setProperty("--seg-x", `${active.offsetLeft}px`);
      root.style.setProperty("--seg-y", `${active.offsetTop}px`);
      root.style.setProperty("--seg-w", `${active.offsetWidth}px`);
      root.style.setProperty("--seg-h", `${active.offsetHeight}px`);
      root.dataset.slide = "true";
    };
    place();
    if (typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(place);
    observer.observe(root);
    return () => observer.disconnect();
  }, [value, options.length]);
  return (
    <div ref={ref} className={`seg seg-${size}`} role="group" aria-label={label}>
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          aria-pressed={option.value === value}
          disabled={option.disabled}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

export function Skeleton({ lines = 3, height }: { lines?: number; height?: number }) {
  return (
    <div className="skeleton" aria-hidden="true" style={height ? { minHeight: height } : undefined}>
      {Array.from({ length: lines }, (_, index) => <i key={index} />)}
    </div>
  );
}

export function FdrChip({ difficulty, children, title }: { difficulty: number | null | undefined; children: ReactNode; title?: string }) {
  const level = typeof difficulty === "number" ? Math.max(1, Math.min(5, Math.round(difficulty))) : 0;
  return <span className={`fdr fdr-${level}`} title={title ?? (level ? `Difficulty ${difficulty}` : "No fixture")}>{children}</span>;
}

export function Kbd({ children }: { children: ReactNode }) {
  return <kbd className="kbd">{children}</kbd>;
}
