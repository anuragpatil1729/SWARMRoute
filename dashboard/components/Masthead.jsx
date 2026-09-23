"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "../lib/AuthContext";

const managerItems = [
  { href: "/", label: "Operations Overview" },
  { href: "/fleet", label: "Fleet Telematics" },
  { href: "/orders", label: "Orders" },
  { href: "/customer", label: "Customer Portal" },
  { href: "/routes", label: "GIS Routes" },
  { href: "/network", label: "BLE Mesh Network" },
  { href: "/simulator", label: "⚡ API Simulator" },
];

const partnerItems = [
  { href: "/partner", label: "🛵 My Deliveries & Active Route" },
  { href: "/network", label: "📡 BLE Mesh Network" },
  { href: "/simulator", label: "⚡ API Simulator" },
];

export default function Masthead() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, profile, role, signOut, loading } = useAuth();
  const isPartner = role === "partner";
  const navItems = (!user || loading) ? [] : isPartner ? partnerItems : managerItems;

  const handleSignOut = async () => {
    try {
      await signOut();
      router.push("/login");
    } catch (err) {
      console.error("Failed to sign out:", err);
    }
  };

  return (
    <header className="border-b border-slate-200 bg-white sticky top-0 z-50 shadow-sm">
      <div className="w-full px-4 sm:px-6 lg:px-10 pt-4 pb-3 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <div className="flex items-center gap-2.5 flex-wrap">
            <h1 className="text-xl font-bold tracking-tight text-slate-900">
              SWARMRoute
            </h1>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            Autonomous fleet operations · real-time GIS routing · BLE mesh resilience
          </p>
        </div>

        {/* User Auth & Role Bar */}
        <div className="flex items-center gap-3">
          {loading ? (
            <div className="text-xs text-slate-400 animate-pulse font-mono">Connecting...</div>
          ) : user ? (
            <div className="flex items-center gap-2.5 bg-slate-50 p-1.5 rounded-xl border border-slate-200">
              <div className="px-2.5 py-1 rounded-lg bg-white border border-slate-200 shadow-xs flex items-center gap-2">
                <span className="text-xs">
                  {role === "manager" ? "🏢" : "🛵"}
                </span>
                <div className="text-left">
                  <div className="text-xs font-bold text-slate-800 leading-tight">
                    {profile?.full_name || user.email?.split("@")[0]}
                  </div>
                  <div className="text-[10px] text-slate-500 font-mono leading-tight">
                    {role === "manager"
                      ? `Company Manager · ${profile?.city && profile.city !== "Bengaluru" ? profile.city : "Maharashtra"}`
                      : `Delivery Partner · ${profile?.city && profile.city !== "Bengaluru" ? profile.city : "Maharashtra"}`}
                  </div>
                </div>
              </div>

              <button
                type="button"
                onClick={handleSignOut}
                className="px-2.5 py-1.5 text-xs font-semibold text-rose-600 hover:text-rose-700 hover:bg-rose-50 rounded-lg transition-colors border border-transparent hover:border-rose-200"
                title="Sign out of current account"
              >
                Sign Out
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <Link
                href="/login"
                className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors border ${
                  pathname === "/login"
                    ? "bg-blue-50 text-blue-700 border-blue-200 shadow-xs"
                    : "text-slate-700 hover:text-slate-900 bg-slate-100 hover:bg-slate-200 border-slate-200"
                }`}
              >
                Sign In
              </Link>
              <Link
                href="/signup"
                className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors shadow-xs ${
                  pathname === "/signup"
                    ? "bg-blue-700 text-white ring-2 ring-blue-300"
                    : "text-white bg-blue-600 hover:bg-blue-700"
                }`}
              >
                Register
              </Link>
            </div>
          )}
        </div>
      </div>

      {navItems.length > 0 && (
        <nav className="w-full px-4 sm:px-6 lg:px-10 border-t border-slate-100 overflow-x-auto scrollbar-none">
          <ul className="flex items-center gap-x-6 text-[13px] font-medium whitespace-nowrap min-w-max">
            {navItems.map((item) => {
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
      )}
    </header>
  );
}
