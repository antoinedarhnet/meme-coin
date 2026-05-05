import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  Zap,
  Shield,
  Twitter,
  Flame,
  Activity,
  Bot,
  ChevronRight,
} from "lucide-react";
import { api } from "@/lib/api";
import { fmtPct, fmtUsd } from "@/lib/format";
import ScoreRing from "@/components/ScoreRing";
import RiskBadge from "@/components/RiskBadge";

const FEATURES = [
  {
    icon: Activity,
    title: "Real-time Token Feed",
    body: "Streaming Solana memecoins from Pump.fun, Raydium & DexScreener — millisecond latency, sortable by score, age, MC, liquidity.",
    accent: "text-neon-green border-neon-green/30",
  },
  {
    icon: Bot,
    title: "AI Score 0-100",
    body: "Proprietary algorithm weighting LP lock, holder concentration, momentum, buy/sell pressure & socials. A→F grade in seconds.",
    accent: "text-neon-violet border-neon-violet/30",
  },
  {
    icon: Shield,
    title: "Rug & Honeypot Shield",
    body: "Auto-flag dev history, sybil wallets, mint authority, locked LP. Color-coded SAFE / RISKY / DANGER / RUG.",
    accent: "text-neon-red border-neon-red/30",
  },
  {
    icon: Twitter,
    title: "KOL Cross-Calls",
    body: "Track 6+ top callers. When 2+ KOLs name the same CA inside a tight window, you get a high-priority convergence signal.",
    accent: "text-neon-cyan border-neon-cyan/30",
  },
  {
    icon: Flame,
    title: "Narrative Heatmap",
    body: "AI Agents, PolitiFi, Animals, Pure Memes — see which meta is exploding before the chart does.",
    accent: "text-neon-yellow border-neon-yellow/30",
  },
  {
    icon: Zap,
    title: "1-Click Live Snipe",
    body: "Execute trades in one click with configurable slippage, TP/SL ladder, priority fee, and full live P&L tracker — built for speed.",
    accent: "text-neon-green border-neon-green/30",
  },
];

export default function Landing() {
  const [preview, setPreview] = useState([]);

  useEffect(() => {
    api
      .liveTokens({ limit: 6, sort: "score" })
      .then((d) => setPreview(d.tokens || []))
      .catch(() => {});
  }, []);

  return (
    <div className="min-h-screen bg-[#050505] text-white relative overflow-x-hidden">
      {/* Top nav */}
      <header className="sticky top-0 z-30 border-b border-[#1A1A24] bg-black/80 backdrop-blur">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 border border-neon-green flex items-center justify-center">
              <Zap className="w-4 h-4 text-neon-green" />
            </div>
            <div>
              <div className="font-display font-bold tracking-tight">SNIPER.SOL</div>
              <div className="font-mono text-[9px] uppercase tracking-widest text-neon-green glow-green -mt-0.5">
                TERMINAL · V1
              </div>
            </div>
          </div>
          <nav className="hidden md:flex items-center gap-7 font-mono text-xs uppercase tracking-widest text-[#8A8A9E]">
            <a href="#features" className="hover:text-white">
              Features
            </a>
            <a href="#feed" className="hover:text-white">
              Live Feed
            </a>
            <a href="#stack" className="hover:text-white">
              Stack
            </a>
            <a href="#disclaimer" className="hover:text-white">
              Risk
            </a>
          </nav>
          <Link
            to="/app"
            data-testid="hero-launch-button"
            className="btn-neon-green flex items-center gap-2"
          >
            LAUNCH TERMINAL <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      </header>

      {/* HERO */}
      <section className="relative">
        <div className="absolute inset-0 bg-grid opacity-40 pointer-events-none" />
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            background:
              "radial-gradient(circle at 70% 50%, rgba(0,255,102,0.15) 0%, transparent 60%)",
          }}
        />
        <div className="relative max-w-7xl mx-auto px-6 pt-20 pb-24 grid lg:grid-cols-12 gap-10">
          <div className="lg:col-span-7 flex flex-col justify-center">
            <div className="inline-flex items-center gap-2 self-start px-3 py-1 border border-[#1A1A24] bg-black mb-6">
              <span className="w-1.5 h-1.5 bg-neon-green rounded-full animate-pulse-dot" />
              <span className="font-mono text-[10px] uppercase tracking-widest text-[#8A8A9E]">
                Solana · Mainnet · DexScreener Live
              </span>
            </div>
            <h1 className="font-display font-extrabold uppercase text-5xl sm:text-6xl lg:text-7xl tracking-tighter leading-[0.9] mb-6">
              Snipe the next
              <br />
              <span className="text-neon-green glow-green">10X memecoin</span>
              <br />
              before the chart does.
            </h1>
            <p className="text-[#8A8A9E] text-base sm:text-lg max-w-xl mb-8 leading-relaxed">
              A pro-grade Solana terminal that fuses live token feeds, AI scoring, rug detection
              and KOL cross-call surveillance into one ruthless dashboard. No more switching tabs.
            </p>
            <div className="flex flex-col sm:flex-row gap-3">
              <Link to="/app" className="btn-neon-green inline-flex items-center justify-center gap-2" data-testid="cta-launch-terminal">
                LAUNCH TERMINAL <ArrowRight className="w-4 h-4" />
              </Link>
              <a href="#features" className="btn-ghost text-center" data-testid="cta-explore-features">
                EXPLORE FEATURES
              </a>
            </div>

            <div className="mt-12 grid grid-cols-3 gap-4 max-w-md">
              {[
                { k: "8+", v: "Data Sources" },
                { k: "0-100", v: "AI Score" },
                { k: "<200ms", v: "Stream Latency" },
              ].map((s) => (
                <div key={s.v} className="border-t border-[#1A1A24] pt-3">
                  <div className="font-mono text-2xl text-neon-cyan glow-cyan">{s.k}</div>
                  <div className="font-mono text-[10px] uppercase tracking-widest text-[#5C5C6E]">
                    {s.v}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Mock terminal preview */}
          <div className="lg:col-span-5">
            <div className="terminal-panel relative overflow-hidden shadow-[0_0_60px_rgba(0,255,102,0.08)]">
              <div className="flex items-center justify-between px-3 py-2 border-b border-[#1A1A24] bg-black">
                <div className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-widest text-[#8A8A9E]">
                  <div className="flex gap-1">
                    <span className="w-2 h-2 rounded-full bg-neon-red" />
                    <span className="w-2 h-2 rounded-full bg-neon-yellow" />
                    <span className="w-2 h-2 rounded-full bg-neon-green" />
                  </div>
                  TOP SCORES // LIVE
                </div>
                <span className="font-mono text-[10px] text-neon-green">● STREAMING</span>
              </div>
              <div className="divide-y divide-[#1A1A24]">
                {(preview.length ? preview : Array(5).fill(null)).slice(0, 5).map((t, i) => (
                  <div
                    key={t?.address || i}
                    className="flex items-center gap-3 px-3 py-2.5 hover:bg-[#14141A]"
                  >
                    <div className="w-7 h-7 bg-[#1A1A24] flex items-center justify-center font-mono text-[10px] text-neon-cyan border border-[#1A1A24]">
                      {t?.symbol?.[0] || "?"}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="font-mono text-sm text-white truncate">
                        ${t?.symbol || "—"}{" "}
                        <span className="text-[#5C5C6E] text-[10px]">{t?.name || "loading…"}</span>
                      </div>
                      <div className="font-mono text-[10px] text-[#5C5C6E]">
                        MC {fmtUsd(t?.market_cap)} · LIQ {fmtUsd(t?.liquidity_usd)}
                      </div>
                    </div>
                    <div
                      className={`font-mono text-xs ${
                        (t?.price_change_24h || 0) >= 0 ? "text-neon-green" : "text-neon-red"
                      }`}
                    >
                      {fmtPct(t?.price_change_24h)}
                    </div>
                    <ScoreRing score={t?.score || 0} size={36} stroke={3} />
                  </div>
                ))}
              </div>
              <div className="px-3 py-2 border-t border-[#1A1A24] bg-black flex items-center justify-between font-mono text-[10px] uppercase tracking-widest">
                <span className="text-[#5C5C6E]">SOURCE: DEXSCREENER</span>
                <Link to="/app" className="text-neon-green hover:underline" data-testid="hero-mock-cta">
                  OPEN FULL FEED →
                </Link>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Features bento */}
      <section id="features" className="border-t border-[#1A1A24]">
        <div className="max-w-7xl mx-auto px-6 py-20">
          <div className="flex items-end justify-between mb-10 flex-wrap gap-4">
            <div>
              <div className="font-mono text-[10px] uppercase tracking-widest text-neon-green mb-2">
                / 01 — ARSENAL
              </div>
              <h2 className="font-display text-4xl sm:text-5xl uppercase tracking-tight">
                Built for traders
                <br />
                who don't sleep.
              </h2>
            </div>
            <p className="max-w-md text-[#8A8A9E] text-sm">
              Six modules engineered to give you an edge on every new launch. Each one is opinionated,
              fast, and designed for the chaos of memecoin markets.
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-px bg-[#1A1A24] border border-[#1A1A24]">
            {FEATURES.map((f, idx) => (
              <div
                key={f.title}
                className="bg-[#0A0A0D] p-7 hover:bg-[#0D0D12] transition-colors group min-h-[220px] flex flex-col"
                data-testid={`feature-card-${idx}`}
              >
                <div
                  className={`w-10 h-10 border ${f.accent} flex items-center justify-center mb-5`}
                >
                  <f.icon className="w-5 h-5" />
                </div>
                <div className="font-mono text-[10px] uppercase tracking-widest text-[#5C5C6E] mb-2">
                  / 0{idx + 1}
                </div>
                <h3 className="font-display text-xl mb-3">{f.title}</h3>
                <p className="text-sm text-[#8A8A9E] leading-relaxed">{f.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Live feed strip */}
      <section id="feed" className="border-t border-[#1A1A24] bg-black">
        <div className="max-w-7xl mx-auto px-6 py-20">
          <div className="flex items-end justify-between mb-8 flex-wrap gap-4">
            <div>
              <div className="font-mono text-[10px] uppercase tracking-widest text-neon-cyan mb-2">
                / 02 — LIVE
              </div>
              <h2 className="font-display text-4xl uppercase tracking-tight">Top scores right now</h2>
            </div>
            <Link
              to="/app"
              className="font-mono text-xs uppercase tracking-widest text-neon-green hover:underline flex items-center gap-1"
              data-testid="open-full-terminal"
            >
              Open full terminal <ChevronRight className="w-4 h-4" />
            </Link>
          </div>
          <div className="terminal-panel overflow-x-auto">
            <table className="w-full font-mono text-xs">
              <thead className="bg-[#0A0A0D] text-[#5C5C6E] uppercase">
                <tr>
                  <th className="text-left py-3 px-4">Token</th>
                  <th className="text-right px-3">Price</th>
                  <th className="text-right px-3">24h</th>
                  <th className="text-right px-3">MC</th>
                  <th className="text-right px-3">Liq</th>
                  <th className="text-center px-3">Risk</th>
                  <th className="text-center px-3">Score</th>
                </tr>
              </thead>
              <tbody>
                {(preview.length ? preview : Array(6).fill(null)).map((t, i) => (
                  <tr key={t?.address || i} className="border-t border-[#1A1A24] hover:bg-[#14141A]">
                    <td className="px-4 py-2.5 flex items-center gap-2">
                      <div className="w-6 h-6 bg-[#1A1A24] flex items-center justify-center text-neon-cyan text-[10px] border border-[#1A1A24]">
                        {t?.symbol?.[0] || "?"}
                      </div>
                      <span className="text-white">${t?.symbol || "—"}</span>
                    </td>
                    <td className="px-3 text-right">{fmtUsd(t?.price_usd)}</td>
                    <td
                      className={`px-3 text-right ${
                        (t?.price_change_24h || 0) >= 0 ? "text-neon-green" : "text-neon-red"
                      }`}
                    >
                      {fmtPct(t?.price_change_24h)}
                    </td>
                    <td className="px-3 text-right">{fmtUsd(t?.market_cap)}</td>
                    <td className="px-3 text-right">{fmtUsd(t?.liquidity_usd)}</td>
                    <td className="px-3 text-center">
                      {t?.risk ? <RiskBadge risk={t.risk} /> : "—"}
                    </td>
                    <td className="px-3 text-center">
                      <div className="inline-block">
                        <ScoreRing score={t?.score || 0} size={32} stroke={3} />
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* Stack */}
      <section id="stack" className="border-t border-[#1A1A24]">
        <div className="max-w-7xl mx-auto px-6 py-20 grid lg:grid-cols-2 gap-12">
          <div>
            <div className="font-mono text-[10px] uppercase tracking-widest text-neon-violet mb-2">
              / 03 — STACK
            </div>
            <h2 className="font-display text-4xl uppercase tracking-tight mb-6">
              Engineered for low-latency hunting.
            </h2>
            <p className="text-[#8A8A9E] mb-8">
              FastAPI streaming layer, MongoDB persistence, DexScreener public API ingestion,
              proprietary scoring algorithm — all wrapped in a Bloomberg-style terminal UI.
            </p>
            <div className="grid grid-cols-2 gap-px bg-[#1A1A24] border border-[#1A1A24]">
              {[
                ["DexScreener", "Token Stream"],
                ["Pump.fun", "New Launches"],
                ["Helius RPC", "On-chain Data"],
                ["Birdeye", "Analytics"],
                ["X / Twitter", "KOL Surveillance"],
                ["MongoDB", "Persistence"],
              ].map(([a, b]) => (
                <div key={a} className="bg-black p-4">
                  <div className="font-mono text-sm text-white">{a}</div>
                  <div className="font-mono text-[10px] uppercase tracking-widest text-[#5C5C6E]">
                    {b}
                  </div>
                </div>
              ))}
            </div>
          </div>
          <div className="terminal-panel p-6 relative overflow-hidden">
            <div className="absolute inset-0 bg-grid-sm opacity-30 pointer-events-none" />
            <pre className="relative font-mono text-[11px] leading-relaxed text-[#8A8A9E] whitespace-pre-wrap">
{`# scoring algorithm
score = liquidity_score * 0.25
      + volume_liq_ratio * 0.15
      + buy_sell_pressure * 0.15
      + price_momentum * 0.20
      + tx_per_second * 0.10
      + social_presence * 0.10
      + age_score * 0.05

if liq < 3000:    risk = RUG
elif liq < 10K:   risk = DANGER
elif liq < 30K:   risk = RISKY
else:             risk = SAFE`}
            </pre>
            <div className="mt-4 flex items-center justify-between font-mono text-[10px] uppercase tracking-widest">
              <span className="text-neon-green">● algorithm.live</span>
              <span className="text-[#5C5C6E]">v1.0.2</span>
            </div>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="border-t border-[#1A1A24] bg-black">
        <div className="max-w-5xl mx-auto px-6 py-24 text-center relative">
          <div className="absolute inset-0 bg-grid opacity-30 pointer-events-none" />
          <h2 className="relative font-display text-5xl sm:text-6xl uppercase tracking-tighter font-bold mb-6">
            The market is open
            <br />
            <span className="text-neon-green glow-green">24/7. So are we.</span>
          </h2>
          <p className="relative text-[#8A8A9E] mb-8 max-w-xl mx-auto">
            Plug into the terminal. Hunt the next launch. Walk away or get rekt — at least it'll be
            an informed decision.
          </p>
          <Link to="/app" className="relative btn-neon-green inline-flex items-center gap-2" data-testid="cta-bottom-launch">
            LAUNCH TERMINAL <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      </section>

      <footer
        id="disclaimer"
        className="border-t border-[#1A1A24] bg-black px-6 py-8 text-center font-mono text-[10px] uppercase tracking-widest text-[#5C5C6E]"
      >
        ⚠ DISCLAIMER · MEMECOINS ARE EXTREMELY VOLATILE · YOU CAN LOSE EVERYTHING · THIS IS NOT
        FINANCIAL ADVICE · DYOR
      </footer>
    </div>
  );
}
