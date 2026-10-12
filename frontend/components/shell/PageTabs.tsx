"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { navTabs, type NavKey } from "@/lib/navigation";

/** Tabs between sibling pages of one menu destination, such as Explore's Players, Prices and Fixtures. */
export function PageLinkTabs({ parent, label }: { parent: NavKey; label: string }) {
  const pathname = usePathname();
  return (
    <nav className="page-tabs" aria-label={label}>
      {navTabs(parent).map((item) => (
        <Link key={item.key} href={item.href} className="page-tab" aria-current={pathname === item.href ? "page" : undefined}>
          {item.key === parent ? "Players" : item.short}
        </Link>
      ))}
    </nav>
  );
}

/** Tabs that switch sections within one page. */
export function PageSectionTabs<T extends string>({ tabs, value, onChange, label }: {
  tabs: Array<{ value: T; label: ReactNode }>;
  value: T;
  onChange: (value: T) => void;
  label: string;
}) {
  return (
    <div className="page-tabs page-tabs-sticky" role="tablist" aria-label={label}>
      {tabs.map((tab) => (
        <button key={tab.value} type="button" role="tab" id={`tab-${tab.value}`} aria-selected={tab.value === value} aria-controls={`panel-${tab.value}`} className="page-tab" onClick={() => onChange(tab.value)}>
          {tab.label}
        </button>
      ))}
    </div>
  );
}
