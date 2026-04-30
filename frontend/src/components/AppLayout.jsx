import React, { useEffect, useState } from "react";
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
  AlertTriangle,
  Power,
} from "lucide-react";
import Ticker from "@/components/Ticker";
import { api } from "@/lib/api";
import { toast } from "sonner";

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
  const [bankroll, setBankroll] = useState(null);
  const [engine, setEngine] = useState(null);

  const refresh = async () => {
    try {
      const [b, e] = await Promise.all([api.bankroll(), api.engine()]);
      setBankroll(b);
      setEngine(e);
    } catch {}
  };

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 8000);
    return () => clearInterval(t);
  }, []);

  const toggleSnipe = async () => {
    try {
      const s = await api.settings();
      const next = !s.auto_snipe_enabled;
      await api.saveSettings({ ...s, auto_snipe_enabled: next });
      toast.success(next ? "🎯 AUTO-SNIPE ARMED" : "Auto-snipe disarmed");
      refresh();
    } catch (e) {
      toast.error("Toggle failed");
    }
  };

  const balance = bankroll?.balance_sol ?? 0;
  const initial = bankroll?.initial_sol ?? 10;
  const pnl = balance - initial + (bankroll?.realized_pnl_sol || 0);
  const pnlColor = pnl >= 0 ? "text-neon-green" : "text-neon-red";
  const isSnipeOn = engine?.auto_snipe_enabled;
  const isLocked = engine?.auto_snipe_locked;

  return (
    <div className="min-h-screen flex flex-col bg-[#050505] text-white">
      {/* PAPER TRADING BANNER */}
      <div
        data-testid="paper-trading-banner"
        className="bg-neon-yellow/10 border-b border-neon-yellow/40 px-4 py-1.5 flex items-center justify-center gap-2 font-mono text-[10px] uppercase tracking-widest text-neon-yellow"
      >
        <AlertTriangle className="w-3 h-3" />
        PAPER TRADING MODE ACTIVE · NO REAL FUNDS AT RISK · SIMULATION ONLY
      </div>

      {/* Top header */}
      <header className="border-b border-[#1A1A24] bg-black">
        <div className="flex items-center h-14 px-4 gap-4">
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

          <nav className="hidden md:flex items-center gap-1 ml-2">
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

          <div className="ml-auto flex items-center gap-2 flex-wrap justify-end">
            {/* Bankroll chip */}
            <div
              data-testid="bankroll-chip"
              className="hidden sm:flex items-center gap-2 px-3 py-1.5 border border-[#1A1A24] bg-black"
            >
              <Wallet className="w-3 h-3 text-neon-cyan" />
              <div className="leading-tight font-mono">
                <div className="text-[9px] uppercase tracking-widest text-[#5C5C6E]">Bankroll</div>
                <div className="text-[11px] text-white">
                  {balance.toFixed(3)} <span className="text-[#5C5C6E]">SOL</span>
                </div>
              </div>
              <div className={`font-mono text-[10px] ${pnlColor}`}>
                {pnl >= 0 ? "+" : ""}
                {pnl.toFixed(3)}
              </div>
            </div>

            {/* Auto-snipe toggle */}
            <button
              onClick={toggleSnipe}
              data-testid="auto-snipe-toggle"
              title={isLocked ? "Locked by daily loss limit" : "Toggle auto-snipe engine"}
              className={`flex items-center gap-1.5 px-3 py-2 border font-mono text-[10px] uppercase tracking-widest transition-colors ${
                isLocked
                  ? "border-neon-red text-neon-red bg-neon-red/10 cursor-not-allowed"
                  : isSnipeOn
                  ? "border-neon-green text-neon-green bg-neon-green/10 glow-green"
                  : "border-[#1A1A24] text-[#8A8A9E] hover:border-neon-green hover:text-neon-green"
              }`}
              disabled={isLocked}
            >
              <Power className={`w-3 h-3 ${isSnipeOn ? "animate-pulse-dot" : ""}`} />
              AUTO-SNIPE {isLocked ? "LOCKED" : isSnipeOn ? "ARMED" : "OFF"}
            </button>

            <button
              className="relative w-9 h-9 border border-[#1A1A24] flex items-center justify-center hover:border-neon-cyan group"
              data-testid="alerts-button"
              title="Alerts"
            >
              <Bell className="w-4 h-4 text-[#8A8A9E] group-hover:text-neon-cyan" />
              {engine?.events?.length > 0 && (
                <span className="absolute top-1 right-1 w-1.5 h-1.5 bg-neon-red rounded-full animate-pulse-dot" />
              )}
            </button>
            <button
              className="px-3 py-2 border border-neon-violet text-neon-violet font-mono text-[10px] uppercase tracking-widest hover:bg-neon-violet hover:text-black transition-colors"
              data-testid="connect-wallet-button"
            >
              CONNECT PHANTOM
            </button>
          </div>
        </div>
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

      {/* Engine events strip */}
      {engine?.events?.length > 0 && (
        <div
          data-testid="engine-events-strip"
          className="border-b border-[#1A1A24] bg-[#0A0A0D] px-4 py-1.5 overflow-x-auto whitespace-nowrap flex items-center gap-3 font-mono text-[10px] uppercase tracking-widest"
        >
          <span className="text-neon-violet glow-violet shrink-0">◆ ENGINE:</span>
          {engine.events.slice(0, 8).map((e) => (
            <span
              key={e.id}
              className={`shrink-0 px-2 py-0.5 border ${
                e.kind === "auto_snipe_buy"
                  ? "border-neon-green/40 text-neon-green"
                  : e.kind === "auto_sell"
                  ? "border-neon-cyan/40 text-neon-cyan"
                  : "border-neon-red/40 text-neon-red"
              }`}
            >
              {e.text}
            </span>
          ))}
        </div>
      )}

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
