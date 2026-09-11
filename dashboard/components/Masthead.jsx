"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const items = [
  { href: "/", label: "Live console" },
  { href: "/routes", label: "Route map" },
  { href: "/benchmarks", label: "Method comparison" },
  { href: "/disruptions", label: "Disruptions" },
];

export default function Masthead() {
  const pathname = usePathname();

  return (
    <header className="border-b border-slate-200 bg-white sticky top-0 z-50">
      <div className="w-full px-4 sm:px-6 lg:px-10 pt-5 pb-3 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-bold tracking-tight text-slate-900">
              SwarmRoute
            </h1>
            <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-200">
              Autonomous Fleet
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            Fleet Operations & Dynamic Resilience Console
          </p>
        </div>
        <div className="font-mono text-xs text-slate-500 text-left sm:text-right">
          Autonomous Dispatch · Mesh Recovery
        </div>
      </div>
      <nav className="w-full px-4 sm:px-6 lg:px-10 border-t border-slate-100">
        <ul className="flex flex-wrap gap-x-6 text-[13px] font-medium">
          {items.map((item) => {
            const active =
              item.href === "/"
                ? pathname === "/" || pathname === "/live"
                : pathname.startsWith(item.href);
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className={`inline-block py-2.5 border-b-2 -mb-px transition-colors ${
                    active
                      ? "border-blue-600 text-blue-600 font-semibold"
                      : "border-transparent text-slate-500 hover:text-slate-900 hover:border-slate-300"
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
