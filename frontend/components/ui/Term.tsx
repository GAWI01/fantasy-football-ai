"use client";

import { useState, type ReactNode } from "react";

import { Sheet } from "@/components/ui/Sheet";
import { GLOSSARY, type GlossaryKey } from "@/lib/glossary";

/** A word with a dotted underline; tapping it explains it in plain language. */
export function Term({ k, children }: { k: GlossaryKey; children?: ReactNode }) {
  const [open, setOpen] = useState(false);
  const entry = GLOSSARY[k];
  return (
    <>
      <button type="button" className="term" onClick={(event) => { event.stopPropagation(); event.preventDefault(); setOpen(true); }} aria-haspopup="dialog" aria-label={`What is ${entry.term}?`}>
        {children ?? entry.term}
      </button>
      <Sheet open={open} onClose={() => setOpen(false)} title={entry.term}>
        <p className="term-text">{entry.text}</p>
      </Sheet>
    </>
  );
}
