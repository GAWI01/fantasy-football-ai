"use client";

import { AlertTriangle, ChevronRight, CircleCheck, Crown, Info, Repeat2, Zap } from "lucide-react";
import Link from "next/link";
import { useState, type ReactNode } from "react";

import { FreeTransfersControl } from "@/components/plan/FreeTransfersControl";
import { WhySheet } from "@/components/plan/WhySheet";
import { Term } from "@/components/ui/Term";
import { fixed, signed } from "@/lib/format";
import { CHIP_LABEL, type GameweekPlan } from "@/lib/model/plan";

function Row({ href, icon, tone, title, children }: { href: string; icon: ReactNode; tone?: "accent" | "warn" | "calm"; title: ReactNode; children?: ReactNode }) {
  return (
    // The title link covers the whole row; word explanations inside sit above it.
    <li className={`todo-row${tone ? ` todo-${tone}` : ""}`}>
      <span className="todo-icon" aria-hidden="true">{icon}</span>
      <span className="todo-text">
        <Link href={href} className="todo-link"><b>{title}</b></Link>
        {children ? <small>{children}</small> : null}
      </span>
      <ChevronRight size={18} className="todo-chevron" aria-hidden="true" />
    </li>
  );
}

function transferLine(plan: GameweekPlan): { title: string; detail: ReactNode } {
  if (plan.verdict === "TRANSFER") {
    const moves = plan.recommended.moves;
    const hit = plan.recommended.hit ?? 0;
    const title = moves.length === 1 ? `${moves[0].outName} → ${moves[0].inName}` : `${moves.length} transfers: ${moves.map((move) => move.inName).join(", ")} in`;
    const gain = plan.recommended.nextGwGain;
    return {
      title,
      detail: <>{gain != null ? <>{signed(gain)} points next Gameweek · </> : null}{hit ? <>costs a <Term k="hit">−{hit} hit</Term></> : <>uses a <Term k="freeTransfer">free transfer</Term></>}</>,
    };
  }
  const next = plan.freeTransfers != null ? Math.min(5, plan.freeTransfers + 1) : null;
  return {
    title: "No transfer this week",
    detail: <><Term k="roll">Save it</Term>{next ? `: you will have ${next} free transfers next week` : ""}. Nothing clearly beats your squad.</>,
  };
}

function chipLine(plan: GameweekPlan): { title: string; detail: string | null } {
  if (plan.chip.recommended) return { title: `Play your ${CHIP_LABEL[plan.chip.recommended]}`, detail: plan.chip.reason };
  const available = plan.chip.outlook.filter((item) => item.available);
  if (plan.chip.outlook.length && !available.length) return { title: "No chips left this half", detail: null };
  const next = available.filter((item) => item.best_window).sort((left, right) => (left.best_window!.gameweek) - (right.best_window!.gameweek))[0];
  return { title: "Keep your chips", detail: next?.best_window ? `${next.label} looks best in GW${next.best_window.gameweek}` : "No week stands out yet" };
}

/** The Gameweek as a short to-do list: transfer, captain, chip and the one thing to check. */
export function TodoCard({ plan, event, modelVersion, locked, provisional }: {
  plan: GameweekPlan;
  event: number | null;
  modelVersion: string | null;
  locked: boolean;
  provisional: boolean;
}) {
  const [whyOpen, setWhyOpen] = useState(false);
  const transfer = transferLine(plan);
  const chip = chipLine(plan);
  const lowConfidence = plan.confidence?.label === "LOW";
  return (
    <section className="todo-card" aria-labelledby="todo-title">
      <header className="todo-head">
        <span className="eyebrow">Gameweek {event ?? "—"}</span>
        <h2 id="todo-title">{locked ? "Last plan" : "Your to-do"}</h2>
        <div className="todo-flags">
          {locked ? <span className="pill pill-warn">Deadline passed</span> : null}
          {provisional ? <span className="pill pill-accent"><Term k="provisional" /></span> : null}
          {lowConfidence ? <span className="pill pill-warn"><Term k="confidence">Low confidence</Term></span> : null}
        </div>
      </header>
      <ol className="todo-list">
        <Row href="/plan#transfers" icon={<Repeat2 size={18} />} tone={plan.verdict === "TRANSFER" ? "accent" : undefined} title={transfer.title}>{transfer.detail}</Row>
        <Row href="/plan#captain" icon={<Crown size={18} />} title={plan.captain ? `Captain ${plan.captain.name}` : "Captain"}>
          {plan.captain ? <>{fixed(plan.captain.xp)} <Term k="xp">xP</Term>{plan.captain.opponent ? ` vs ${plan.captain.opponent}${plan.captain.home == null ? "" : plan.captain.home ? " (home)" : " (away)"}` : ""}{plan.vice ? ` · vice ${plan.vice.name}` : ""}</> : "Unavailable"}
        </Row>
        <Row href="/plan#chips" icon={<Zap size={18} />} tone={plan.chip.recommended ? "warn" : undefined} title={chip.title}>{chip.detail}{plan.chipBudgetIsEstimate ? <>{chip.detail ? " · " : ""}<span>Squad affordability estimated from market prices.</span></> : null}</Row>
        {plan.mainRisk.tone !== "calm" ? (
          <Row href="/team" icon={<AlertTriangle size={18} />} tone="warn" title={`Check ${plan.mainRisk.title}`}>{plan.mainRisk.detail}</Row>
        ) : (
          <Row href="/team" icon={<CircleCheck size={18} />} tone="calm" title="No injury worries">{plan.mainRisk.detail}</Row>
        )}
      </ol>
      {!locked ? <div className="todo-ft"><FreeTransfersControl count={plan.freeTransfers} source={plan.freeTransfersSource} /></div> : null}
      <footer className="todo-foot">
        <button type="button" className="btn btn-sm" onClick={() => setWhyOpen(true)}><Info size={14} aria-hidden="true" />Why?</button>
        <span>Make the changes yourself in the official FPL app.</span>
      </footer>
      <WhySheet open={whyOpen} onClose={() => setWhyOpen(false)} plan={plan} modelVersion={modelVersion} />
    </section>
  );
}
