"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const items = [
  { href: "/", label: "Overview" },
  { href: "/benchmarks", label: "Method comparison" },
  { href: "/disruptions", label: "Disruption scenarios" },
  { href: "/ppo-training", label: "PPO training" },
  { href: "/routes", label: "Route map" },
  { href: "/live", label: "Live view" },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-full md:w-56 shrink-0 border-b md:border-b-0 md:border-r border-border bg-panel">
      <div className="px-5 pt-6 pb-5">
        <div className="flex items-baseline gap-2">
          <span className="text-lg font-semibold tracking-tight text-white">
            SwarmRoute
          </span>
        </div>
        <div className="mt-1 text-xs text-muted mono">
          fleet resilience console
        </div>
      </div>
      <nav className="px-2 pb-6 flex md:block overflow-x-auto md:overflow-visible gap-1">
        {items.map((item) => {
          const active =
            item.href === "/"
              ? pathname === "/"
              : pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`block whitespace-nowrap px-3 py-2 text-sm rounded-none transition-colors ${
                active
                  ? "bg-panel2 text-white border-l-2 border-accent"
                  : "text-muted hover:text-white border-l-2 border-transparent"
              }`}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>
      <div className="hidden md:block px-5 py-4 mt-auto border-t border-border text-[11px] text-muted mono leading-relaxed">
        Solomon C101 · seed 42
        <br />
        pure software simulation
      </div>
    </aside>
  );
}
