import React from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import {
  Activity,
  Twitter,
  Flame,
  Wallet,
  Settings as SettingsIcon,
  Bell,
  Zap,
  ChevronRight,
} from "lucide-react";
import Ticker from "@/components/Ticker";

const NAV = [
  { to: "/app", label: "Live Feed", icon: Activity, end: true },
  { to: "/app/kol", label: "KOL Watchlist", icon: Twitter },
  { to: "/app/trending", label: "Narratives", icon: Flame },
  { to: "/app/portfolio", label: "Portfolio", icon: Wallet },
  { to: "/app/settings", label: "Settings", icon: SettingsIcon },
];

export default function AppLayout() {
  const location = useLocation();
  const crumbs = location.pathname.split("/").filter(Boolean);

  return (
    <div className="min-h-screen flex flex-col bg-[#050505] text-white">
      {/* Top header */}
      <header className="border-b border-[#1A1A24] bg-black">
        <div className="flex items-center h-14 px-4 gap-6">
          <Link to="/" className="flex items-center gap-2" data-testid="brand-link">
            <div className="w-7 h-7 border border-neon-green flex items-center justify-center">
              <Zap className="w-4 h-4 text-neon-green" />
            </div>
            <div className="leading-tight">
              <div className="font-display font-bold text-sm tracking-tight">SNIPR.SOL</div>
              <div className="font-mono text-[9px] uppercase tracking-widest text-neon-green glow-green">
                TERMINAL // V1
              </div>
            </div>
          </Link>

          <nav className="hidden md:flex items-center gap-1 ml-4">
            {NAV.map((n) => (
              <NavLink
                key={n.to}
                to={n.to}
                end={n.end}
                data-testid={`nav-${n.label.toLowerCase().replace(/\s/g, "-")}`}
                className={({ isActive }) =>
                  `px-3 py-1.5 font-mono text-xs uppercase tracking-widest border ${
                    isActive
                      ? "border-neon-green text-neon-green bg-neon-green/5"
                      : "border-transparent text-[#8A8A9E] hover:text-white hover:border-[#1A1A24]"
                  }`
                }
              >
                <span className="flex items-center gap-1.5">
                  <n.icon className="w-3 h-3" />
                  {n.label}
                </span>
              </NavLink>
            ))}
          </nav>

          <div className="ml-auto flex items-center gap-3">
            <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 border border-[#1A1A24] font-mono text-[10px] uppercase">
              <span className="w-1.5 h-1.5 bg-neon-green rounded-full animate-pulse-dot" />
              <span className="text-[#8A8A9E]">RPC</span>
              <span className="text-neon-green">42ms</span>
            </div>
            <button
              className="relative w-9 h-9 border border-[#1A1A24] flex items-center justify-center hover:border-neon-cyan group"
              data-testid="alerts-button"
              title="Alerts"
            >
              <Bell className="w-4 h-4 text-[#8A8A9E] group-hover:text-neon-cyan" />
              <span className="absolute top-1 right-1 w-1.5 h-1.5 bg-neon-red rounded-full animate-pulse-dot" />
            </button>
            <button
              className="px-4 py-2 border border-neon-violet text-neon-violet font-mono text-[11px] uppercase tracking-widest hover:bg-neon-violet hover:text-black transition-colors"
              data-testid="connect-wallet-button"
            >
              CONNECT PHANTOM
            </button>
          </div>
        </div>
        {/* mobile nav */}
        <div className="flex md:hidden border-t border-[#1A1A24] overflow-x-auto">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.end}
              className={({ isActive }) =>
                `flex-1 px-3 py-2 font-mono text-[10px] uppercase tracking-widest border-r border-[#1A1A24] text-center ${
                  isActive ? "text-neon-green bg-neon-green/5" : "text-[#8A8A9E]"
                }`
              }
            >
              {n.label}
            </NavLink>
          ))}
        </div>
      </header>

      <Ticker />

      {/* Breadcrumb / status row */}
      <div className="border-b border-[#1A1A24] bg-[#0A0A0D]/50">
        <div className="px-4 h-8 flex items-center gap-2 font-mono text-[10px] uppercase tracking-widest text-[#5C5C6E]">
          <span>SOLANA / MAINNET</span>
          {crumbs.map((c, i) => (
            <React.Fragment key={i}>
              <ChevronRight className="w-3 h-3" />
              <span className={i === crumbs.length - 1 ? "text-white" : ""}>{c}</span>
            </React.Fragment>
          ))}
          <span className="ml-auto text-neon-green">DEXSCREENER · CONNECTED</span>
        </div>
      </div>

      <main className="flex-1">
        <Outlet />
      </main>

      <footer className="border-t border-[#1A1A24] bg-black px-4 py-2 flex items-center justify-between font-mono text-[10px] uppercase tracking-widest text-[#5C5C6E]">
        <span>© SNIPR.SOL · NOT FINANCIAL ADVICE · DYOR</span>
        <span>PAPER TRADING MODE</span>
      </footer>
    </div>
  );
}
