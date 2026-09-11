"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const items = [
  { href: "/", label: "Overview" },
  { href: "/benchmarks", label: "Method comparison" },
  { href: "/disruptions", label: "Disruptions" },
  { href: "/ppo-training", label: "PPO training" },
  { href: "/routes", label: "Route map" },
  { href: "/live", label: "Live view" },
];

export default function Masthead() {
  const pathname = usePathname();

  return (
    <header className="border-b-2 border-ink bg-paper">
      <div className="max-w-5xl mx-auto px-6 pt-8 pb-5 flex flex-col sm:flex-row sm:items-end sm:justify-between gap-2">
        <div>
          <h1 className="serif text-[1.75rem] leading-none text-ink">
            SwarmRoute
          </h1>
          <p className="mt-1.5 text-sm text-muted max-w-md">
            A decentralized delivery-fleet simulation — resilience benchmark summary
          </p>
        </div>
        <div className="mono text-xs text-muted text-left sm:text-right">
          Solomon C101 / R101 / RC101 · seed 42
          <br />
          software simulation, no live fleet
        </div>
      </div>
      <nav className="max-w-5xl mx-auto px-6 border-t border-rule">
        <ul className="flex flex-wrap gap-x-6 mono text-[13px]">
          {items.map((item) => {
            const active =
              item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className={`inline-block py-2.5 border-b-2 -mb-px transition-colors ${
                    active
                      ? "border-ink text-ink"
                      : "border-transparent text-muted hover:text-ink hover:border-rule"
                  }`}
                >
                  {item.label}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
    </header>
  );
}
