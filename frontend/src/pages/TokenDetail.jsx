import React, { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { api } from "@/lib/api";
import { fmtPct, fmtUsd, fmtAge, shorten } from "@/lib/format";
import ScoreRing from "@/components/ScoreRing";
import RiskBadge from "@/components/RiskBadge";
import { ArrowLeft, Copy, ExternalLink, Zap, TrendingUp, TrendingDown, Target, DollarSign } from "lucide-react";
import { toast } from "sonner";

export default function TokenDetail() {
  const { addr } = useParams();
  const [data, setData] = useState(null);
  const [positions, setPositions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [amount, setAmount] = useState(0.5);
  const [slippage, setSlippage] = useState(30);

  const load = async () => {
    try {
      const [d, p] = await Promise.all([
        api.tokenDetail(addr),
        api.positions({ token_address: addr }),
      ]);
      setData(d);
      setPositions(p.positions || []);
    } catch (e) {
      toast.error("Token fetch failed");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    const t = setInterval(load, 30000);
    return () => clearInterval(t);
    // eslint-disable-next-line
  }, [addr]);

  const snipe = async () => {
    if (!data?.token) return;
    try {
      await api.buy({
        token_address: data.token.address,
        symbol: data.token.symbol,
        name: data.token.name,
        image: data.token.image,
        price_usd: data.token.price_usd || 0.000001,
        market_cap: data.token.market_cap,
        amount_sol: Number(amount),
        slippage: Number(slippage),
      });
      toast.success(`Sniped ${amount} SOL of $${data.token.symbol}`);
      load();
    } catch (e) {
      toast.error("Snipe failed");
    }
  };

  const sellPosition = async (pos) => {
    if (!data?.token?.price_usd) {
      toast.error("Live price unavailable");
      return;
    }
    try {
      await api.close({ position_id: pos.id, exit_price_usd: data.token.price_usd });
      toast.success(`SOLD $${pos.symbol}`, {
        description: `Closed ${pos.amount_sol} SOL position`,
      });
      load();
    } catch (e) {
      toast.error("Sell failed");
    }
  };

  if (loading) {
    return (
      <div className="px-4 py-8 text-center font-mono text-xs uppercase text-[#5C5C6E]">
        Resolving token…
      </div>
    );
  }
  if (!data?.token) {
    return (
      <div className="px-4 py-8 text-center font-mono text-xs uppercase text-[#5C5C6E]">
        Token not found
      </div>
    );
  }

  const t = data.token;
  const s = data.score;

  return (
    <div className="px-4 py-4 space-y-3">
      <div className="terminal-panel">
        <div className="flex flex-wrap items-center gap-3 px-4 py-3 border-b border-[#1A1A24]">
          <Link
            to="/app"
            className="flex items-center gap-1 font-mono text-[10px] uppercase tracking-widest text-[#5C5C6E] hover:text-white"
            data-testid="back-to-feed"
          >
            <ArrowLeft className="w-3 h-3" /> Feed
          </Link>
          {t.image ? (
            <img src={t.image} alt="" className="w-12 h-12 border border-[#1A1A24]" onError={(e) => (e.target.style.display = "none")} />
          ) : (
            <div className="w-12 h-12 bg-[#1A1A24] border border-[#1A1A24] flex items-center justify-center font-display font-bold text-xl text-neon-cyan">
              {t.symbol?.[0]}
            </div>
          )}
          <div>
            <div className="font-display text-2xl font-bold flex items-center gap-2">
              ${t.symbol}
              <span className="font-mono text-xs text-[#5C5C6E]">{t.name}</span>
            </div>
            <button
              onClick={() => {
                navigator.clipboard.writeText(t.address);
                toast.success("CA copied");
              }}
              data-testid="copy-ca-button"
              className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-widest text-[#5C5C6E] hover:text-neon-cyan mt-0.5"
            >
              {shorten(t.address, 6)} <Copy className="w-3 h-3" />
            </button>
          </div>
          <div className="ml-auto flex items-center gap-3">
            <RiskBadge risk={t.risk} />
            <ScoreRing score={s?.score || t.score || 0} size={64} stroke={5} />
            {t.url && (
              <a
                href={t.url}
                target="_blank"
                rel="noreferrer"
                className="px-3 py-2 border border-[#1A1A24] hover:border-neon-cyan font-mono text-[10px] uppercase tracking-widest text-[#8A8A9E] hover:text-neon-cyan flex items-center gap-1.5"
                data-testid="dex-screener-link"
              >
                DexScreener <ExternalLink className="w-3 h-3" />
              </a>
            )}
          </div>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 divide-x divide-[#1A1A24]">
          <Metric label="Price" value={fmtUsd(t.price_usd)} />
          <Metric
            label="24h"
            value={fmtPct(t.price_change_24h)}
            color={(t.price_change_24h || 0) >= 0 ? "text-neon-green" : "text-neon-red"}
          />
          <Metric label="Market Cap" value={fmtUsd(t.market_cap)} />
          <Metric label="Liquidity" value={fmtUsd(t.liquidity_usd)} />
          <Metric label="Volume 24h" value={fmtUsd(t.volume_24h)} />
          <Metric label="Age" value={fmtAge(t.age_minutes)} />
        </div>
      </div>

      {/* Positions panel - show user's trades on this token */}
      {positions.length > 0 && (
        <div className="terminal-panel" data-testid="my-trades-panel">
          <div className="px-3 py-2 border-b border-[#1A1A24] font-mono text-[11px] uppercase tracking-widest flex items-center gap-2">
            <Target className="w-3.5 h-3.5 text-neon-green" />
            <span className="text-neon-green glow-green">MY TRADES ON THIS TOKEN</span>
            <span className="ml-auto text-[#5C5C6E]">{positions.filter((p) => p.status === "open").length} OPEN · {positions.filter((p) => p.status === "closed").length} CLOSED</span>
          </div>
          <div className="divide-y divide-[#1A1A24]">
            {positions.map((p) => {
              const currentPrice = t.price_usd || 0;
              const isOpen = p.status === "open";
              const livePnlPct = isOpen
                ? ((currentPrice - p.entry_price) / p.entry_price) * 100
                : p.pnl_pct;
              const liveProfit = (livePnlPct || 0) >= 0;
              const finalPnlPct = isOpen ? livePnlPct : p.pnl_pct;
              const finalPnlSol = isOpen
                ? p.amount_sol * ((livePnlPct || 0) / 100)
                : p.pnl_sol;
              return (
                <div
                  key={p.id}
                  className="p-3 hover:bg-[#14141A]"
                  data-testid={`my-position-${p.id}`}
                >
                  <div className="grid grid-cols-1 md:grid-cols-12 gap-3 items-center">
                    {/* Status */}
                    <div className="md:col-span-2 flex items-center gap-2">
                      <span
                        className={`px-1.5 py-0.5 border font-mono text-[10px] uppercase tracking-widest ${
                          isOpen
                            ? "border-neon-cyan text-neon-cyan"
                            : "border-[#1A1A24] text-[#8A8A9E]"
                        }`}
                      >
                        {isOpen ? "● OPEN" : "CLOSED"}
                      </span>
                      <span className="font-mono text-[10px] text-[#5C5C6E]">
                        {new Date(p.opened_at).toLocaleString(undefined, {
                          month: "short",
                          day: "2-digit",
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </span>
                    </div>

                    {/* Entry marker */}
                    <div className="md:col-span-3">
                      <div className="font-mono text-[10px] uppercase tracking-widest text-[#5C5C6E]">
                        ▶ ENTRY
                      </div>
                      <div className="font-mono text-sm text-white">
                        {fmtUsd(p.entry_price, { compact: false })}
                      </div>
                      <div className="font-mono text-[10px] text-[#5C5C6E]">
                        {p.amount_sol} SOL · {p.tokens?.toLocaleString(undefined, { maximumFractionDigits: 0 })} tk
                      </div>
                    </div>

                    {/* Current / exit price */}
                    <div className="md:col-span-3">
                      <div className="font-mono text-[10px] uppercase tracking-widest text-[#5C5C6E]">
                        {isOpen ? "◆ NOW" : "✕ EXIT"}
                      </div>
                      <div className="font-mono text-sm text-white">
                        {fmtUsd(isOpen ? currentPrice : p.exit_price, { compact: false })}
                      </div>
                      {isOpen && (
                        <div className="font-mono text-[10px] text-neon-cyan">
                          live · auto-refresh
                        </div>
                      )}
                    </div>

                    {/* PnL */}
                    <div className="md:col-span-2">
                      <div
                        className={`font-mono text-lg font-bold ${
                          liveProfit ? "text-neon-green glow-green" : "text-neon-red glow-red"
                        }`}
                      >
                        {fmtPct(finalPnlPct)}
                      </div>
                      <div
                        className={`font-mono text-[10px] ${
                          liveProfit ? "text-neon-green" : "text-neon-red"
                        }`}
                      >
                        {(finalPnlSol || 0).toFixed(3)} SOL
                      </div>
                    </div>

                    {/* Action */}
                    <div className="md:col-span-2 flex justify-end">
                      {isOpen ? (
                        <button
                          onClick={() => sellPosition(p)}
                          data-testid={`sell-position-${p.id}`}
                          className="px-4 py-2 border border-neon-red text-neon-red hover:bg-neon-red hover:text-black font-mono text-xs uppercase tracking-widest font-bold flex items-center gap-1.5 transition-colors"
                        >
                          <DollarSign className="w-3 h-3" /> SELL
                        </button>
                      ) : (
                        <span className="font-mono text-[10px] uppercase tracking-widest text-[#5C5C6E]">
                          SETTLED
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Visual entry-to-current bar (only for open) */}
                  {isOpen && currentPrice > 0 && (
                    <div className="mt-3 relative h-6 bg-black border border-[#1A1A24]">
                      <div className="absolute inset-y-0 left-0 flex items-center px-2 font-mono text-[9px] uppercase tracking-widest text-[#5C5C6E] z-10">
                        ENTRY
                      </div>
                      <div className="absolute inset-y-0 right-0 flex items-center px-2 font-mono text-[9px] uppercase tracking-widest text-[#5C5C6E] z-10">
                        NOW
                      </div>
                      <div
                        className={`absolute inset-y-0 left-0 ${
                          liveProfit ? "bg-neon-green/20" : "bg-neon-red/20"
                        }`}
                        style={{
                          width: `${Math.min(100, Math.max(5, 50 + (livePnlPct || 0) / 4))}%`,
                          borderRight: `2px solid ${liveProfit ? "#00FF66" : "#FF3366"}`,
                          boxShadow: `0 0 8px ${liveProfit ? "#00FF66" : "#FF3366"}`,
                        }}
                      />
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      <div className="grid lg:grid-cols-3 gap-3">
        {/* Chart */}
        <div className="lg:col-span-2 terminal-panel">
          <div className="px-3 py-2 border-b border-[#1A1A24] font-mono text-[11px] uppercase tracking-widest flex items-center gap-2">
            <span>Live Chart</span>
            <span className="ml-auto text-[#5C5C6E]">DexScreener Embed</span>
          </div>
          {/* Entry markers strip above chart */}
          {positions.filter((p) => p.status === "open").length > 0 && (
            <div className="border-b border-[#1A1A24] bg-black px-3 py-1.5 flex items-center gap-2 flex-wrap" data-testid="entry-markers-strip">
              <span className="font-mono text-[9px] uppercase tracking-widest text-[#5C5C6E]">
                ▶ YOUR ENTRIES:
              </span>
              {positions
                .filter((p) => p.status === "open")
                .map((p) => {
                  const inProfit = (t.price_usd || 0) >= p.entry_price;
                  return (
                    <span
                      key={p.id}
                      className={`font-mono text-[10px] px-1.5 py-0.5 border ${
                        inProfit
                          ? "border-neon-green text-neon-green"
                          : "border-neon-red text-neon-red"
                      }`}
                    >
                      {fmtUsd(p.entry_price, { compact: false })} · {p.amount_sol} SOL
                    </span>
                  );
                })}
            </div>
          )}
          <div className="aspect-video bg-black">
            {t.pair_address ? (
              <iframe
                title="chart"
                src={`https://dexscreener.com/solana/${t.pair_address}?embed=1&theme=dark&trades=0&info=0`}
                className="w-full h-full border-0"
              />
            ) : (
              <div className="h-full flex items-center justify-center font-mono text-xs uppercase text-[#5C5C6E]">
                No pair available
              </div>
            )}
          </div>
        </div>

        {/* Snipe panel */}
        <div className="terminal-panel">
          <div className="px-3 py-2 border-b border-[#1A1A24] font-mono text-[11px] uppercase tracking-widest text-neon-green glow-green flex items-center gap-2">
            <Zap className="w-3.5 h-3.5" /> 1-CLICK SNIPE
          </div>
          <div className="p-4 space-y-3">
            <div>
              <label className="font-mono text-[10px] uppercase tracking-widest text-[#5C5C6E]">
                Amount (SOL)
              </label>
              <input
                data-testid="snipe-amount-input"
                type="number"
                step="0.1"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                className="w-full bg-black border border-[#1A1A24] px-3 py-2 font-mono text-sm mt-1 outline-none focus:border-neon-green"
              />
              <div className="flex gap-1 mt-2">
                {[0.1, 0.5, 1, 2.5, 5].map((v) => (
                  <button
                    key={v}
                    onClick={() => setAmount(v)}
                    className="flex-1 px-2 py-1 border border-[#1A1A24] hover:border-neon-green font-mono text-[10px]"
                  >
                    {v}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="font-mono text-[10px] uppercase tracking-widest text-[#5C5C6E]">
                Slippage %
              </label>
              <input
                data-testid="slippage-input"
                type="number"
                value={slippage}
                onChange={(e) => setSlippage(e.target.value)}
                className="w-full bg-black border border-[#1A1A24] px-3 py-2 font-mono text-sm mt-1 outline-none focus:border-neon-green"
              />
            </div>
            <button
              onClick={snipe}
              data-testid="execute-snipe-button"
              className="btn-neon-green w-full flex items-center justify-center gap-2 py-3"
            >
              <Zap className="w-4 h-4" /> SNIPE NOW
            </button>
            <div className="font-mono text-[10px] uppercase tracking-widest text-[#5C5C6E] text-center">
              MEV-protected · Priority fee auto
            </div>
          </div>
        </div>
      </div>

      {/* Score breakdown */}
      <div className="terminal-panel">
        <div className="px-3 py-2 border-b border-[#1A1A24] font-mono text-[11px] uppercase tracking-widest flex items-center gap-2">
          AI Score Breakdown · Grade {s?.grade}
          <span className="ml-auto text-[#5C5C6E]">{s?.score}/100</span>
        </div>
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 divide-x divide-y divide-[#1A1A24]">
          {Object.entries(s?.breakdown || {}).map(([k, v]) => (
            <div key={k} className="p-3" data-testid={`breakdown-${k}`}>
              <div className="font-mono text-[10px] uppercase tracking-widest text-[#5C5C6E] mb-1">
                {k.replace(/_/g, " ")}
              </div>
              <div className="flex items-baseline gap-2">
                <span className="font-mono text-lg text-white">{v.score}</span>
                <span className="font-mono text-[10px] text-[#5C5C6E]">/ {v.max}</span>
              </div>
              <div className="font-mono text-[10px] text-neon-cyan mt-0.5">
                {typeof v.value === "number" ? v.value : String(v.value)}
              </div>
              <div className="h-1 bg-[#1A1A24] mt-2">
                <div
                  className="h-full bg-neon-violet"
                  style={{ width: `${(v.score / v.max) * 100}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Pair stats / activity */}
      <div className="grid md:grid-cols-2 gap-3">
        <div className="terminal-panel">
          <div className="px-3 py-2 border-b border-[#1A1A24] font-mono text-[11px] uppercase tracking-widest">
            Activity
          </div>
          <div className="grid grid-cols-2 divide-x divide-[#1A1A24]">
            <ActivityCell
              label="Buys 24h"
              value={t.txns_24h_buys}
              icon={TrendingUp}
              color="text-neon-green"
            />
            <ActivityCell
              label="Sells 24h"
              value={t.txns_24h_sells}
              icon={TrendingDown}
              color="text-neon-red"
            />
          </div>
          <div className="grid grid-cols-3 divide-x divide-y divide-[#1A1A24]">
            <Metric label="5m Buys" value={t.txns_5m_buys || 0} color="text-neon-green" />
            <Metric label="5m Sells" value={t.txns_5m_sells || 0} color="text-neon-red" />
            <Metric label="5m Vol" value={fmtUsd(t.volume_5m)} />
            <Metric label="DEX" value={(t.dex || "—").toUpperCase()} />
            <Metric label="FDV" value={fmtUsd(t.fdv)} />
            <Metric
              label="Pair"
              value={shorten(t.pair_address, 4) || "—"}
              color="text-neon-cyan"
            />
          </div>
        </div>

        <div className="terminal-panel">
          <div className="px-3 py-2 border-b border-[#1A1A24] font-mono text-[11px] uppercase tracking-widest">
            Socials & Links
          </div>
          <div className="p-3 flex flex-wrap gap-2">
            {(t.socials || []).map((s, i) => (
              <a
                key={i}
                href={s.url}
                target="_blank"
                rel="noreferrer"
                className="px-3 py-1.5 border border-[#1A1A24] hover:border-neon-cyan font-mono text-[10px] uppercase tracking-widest text-[#8A8A9E] hover:text-neon-cyan flex items-center gap-1.5"
                data-testid={`social-${s.type}`}
              >
                {s.type} <ExternalLink className="w-3 h-3" />
              </a>
            ))}
            {(t.websites || []).map((w, i) => (
              <a
                key={i}
                href={w.url}
                target="_blank"
                rel="noreferrer"
                className="px-3 py-1.5 border border-[#1A1A24] hover:border-neon-cyan font-mono text-[10px] uppercase tracking-widest text-[#8A8A9E] hover:text-neon-cyan flex items-center gap-1.5"
              >
                {w.label || "Website"} <ExternalLink className="w-3 h-3" />
              </a>
            ))}
            {(t.socials || []).length === 0 && (t.websites || []).length === 0 && (
              <div className="font-mono text-[10px] uppercase text-[#5C5C6E]">
                No socials reported · ⚠ DYOR
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function Metric({ label, value, color = "text-white" }) {
  return (
    <div className="px-4 py-3">
      <div className="font-mono text-[10px] uppercase tracking-widest text-[#5C5C6E]">
        {label}
      </div>
      <div className={`font-mono text-base ${color}`}>{value}</div>
    </div>
  );
}

function ActivityCell({ label, value, icon: Icon, color }) {
  return (
    <div className="p-4">
      <div className="font-mono text-[10px] uppercase tracking-widest text-[#5C5C6E] flex items-center gap-1">
        <Icon className="w-3 h-3" />
        {label}
      </div>
      <div className={`font-mono text-2xl ${color}`}>{value || 0}</div>
    </div>
  );
}
