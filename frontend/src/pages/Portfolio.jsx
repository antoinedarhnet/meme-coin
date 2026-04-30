import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { fmtPct, fmtUsd } from "@/lib/format";
import { LineChart, Line, XAxis, YAxis, ResponsiveContainer, Tooltip } from "recharts";
import { Wallet, Activity, RotateCcw, AlertTriangle } from "lucide-react";
import { toast } from "sonner";

export default function Portfolio() {
  const [positions, setPositions] = useState([]);
  const [stats, setStats] = useState({});
  const [bankroll, setBankroll] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    const [a, b, c] = await Promise.all([api.positions(), api.stats(), api.bankroll()]);
    setPositions(a.positions || []);
    setStats(b || {});
    setBankroll(c);
    setLoading(false);
  };

  useEffect(() => {
    load();
    const t = setInterval(load, 10000);
    return () => clearInterval(t);
  }, []);

  const closePos = async (p) => {
    try {
      // Fetch live price from DexScreener via token detail
      let priceUsd = p.entry_price;
      try {
        const d = await api.tokenDetail(p.token_address);
        priceUsd = d?.token?.price_usd || p.entry_price;
      } catch {}
      await api.close({ position_id: p.id, exit_price_usd: priceUsd });
      toast.success(`Sold $${p.symbol} @ ${priceUsd.toFixed(8)}`);
      load();
    } catch (e) {
      toast.error("Sell failed");
    }
  };

  const resetBankroll = async () => {
    if (!window.confirm("Reset bankroll & close all open positions?")) return;
    try {
      await api.resetBankroll();
      toast.success("Bankroll reset");
      load();
    } catch (e) {
      toast.error("Reset failed");
    }
  };

  // Build cumulative pnl curve from closed positions
  const closed = positions.filter((p) => p.status === "closed").reverse();
  let cum = 0;
  const series = closed.map((p, i) => {
    cum += p.pnl_sol || 0;
    return { idx: i + 1, pnl: parseFloat(cum.toFixed(4)) };
  });
  if (series.length === 0) series.push({ idx: 0, pnl: 0 });

  return (
    <div className="px-4 py-4 space-y-3">
      {/* Bankroll panel */}
      <div className="terminal-panel">
        <div className="px-3 py-2 border-b border-[#1A1A24] flex items-center gap-2 font-mono text-[11px] uppercase tracking-widest">
          <Wallet className="w-3.5 h-3.5 text-neon-cyan" /> VIRTUAL BANKROLL
          {stats.auto_snipe_locked && (
            <span className="ml-2 px-1.5 py-0.5 border border-neon-red text-neon-red font-mono text-[9px] flex items-center gap-1">
              <AlertTriangle className="w-3 h-3" /> LOCKED
            </span>
          )}
          <button
            onClick={resetBankroll}
            data-testid="reset-bankroll-button"
            className="ml-auto flex items-center gap-1 px-2 py-1 border border-[#1A1A24] hover:border-neon-red text-[10px] uppercase tracking-widest text-[#5C5C6E] hover:text-neon-red"
          >
            <RotateCcw className="w-3 h-3" /> RESET
          </button>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-5 divide-x divide-y divide-[#1A1A24]">
          <BigStat
            label="Balance"
            value={`${(bankroll?.balance_sol ?? 0).toFixed(3)} SOL`}
            sub={`Initial ${bankroll?.initial_sol ?? 10} SOL`}
          />
          <BigStat
            label="Realized P&L"
            value={`${(bankroll?.realized_pnl_sol ?? 0) >= 0 ? "+" : ""}${(bankroll?.realized_pnl_sol ?? 0).toFixed(3)} SOL`}
            accent={(bankroll?.realized_pnl_sol ?? 0) >= 0 ? "text-neon-green glow-green" : "text-neon-red"}
          />
          <BigStat
            label="Daily P&L"
            value={`${(stats?.daily_pnl_pct ?? 0) >= 0 ? "+" : ""}${(stats?.daily_pnl_pct ?? 0).toFixed(2)}%`}
            sub={`${(stats?.daily_pnl_sol ?? 0).toFixed(3)} SOL today`}
            accent={(stats?.daily_pnl_pct ?? 0) >= 0 ? "text-neon-green" : "text-neon-red"}
          />
          <BigStat label="Win Rate" value={`${stats.win_rate ?? 0}%`} accent="text-neon-violet" sub={`${stats.closed_positions ?? 0} closed`} />
          <BigStat label="Open" value={stats.open_positions ?? 0} accent="text-neon-cyan" sub={`${stats.trades_total ?? 0} total`} />
        </div>
      </div>

      {/* By source breakdown */}
      {stats?.by_source && Object.keys(stats.by_source).length > 0 && (
        <div className="terminal-panel">
          <div className="px-3 py-2 border-b border-[#1A1A24] font-mono text-[11px] uppercase tracking-widest">
            P&L Breakdown by Source
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 divide-x divide-y divide-[#1A1A24]">
            {Object.entries(stats.by_source).map(([src, v]) => (
              <div key={src} className="p-3" data-testid={`source-${src}`}>
                <div className="font-mono text-[10px] uppercase tracking-widest text-[#5C5C6E]">
                  {src.replace(/_/g, " ")}
                </div>
                <div
                  className={`font-mono text-lg ${
                    (v.pnl_sol || 0) >= 0 ? "text-neon-green" : "text-neon-red"
                  }`}
                >
                  {(v.pnl_sol || 0) >= 0 ? "+" : ""}
                  {v.pnl_sol.toFixed(3)} SOL
                </div>
                <div className="font-mono text-[10px] text-[#5C5C6E]">
                  {v.count} trades · {v.count ? ((v.wins / v.count) * 100).toFixed(0) : 0}% wins
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="terminal-panel">
        <div className="px-3 py-2 border-b border-[#1A1A24] font-mono text-[11px] uppercase tracking-widest flex items-center gap-2">
          <Activity className="w-3.5 h-3.5 text-neon-green" /> Equity Curve · SOL
        </div>
        <div className="h-56 p-2">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={series}>
              <XAxis dataKey="idx" stroke="#5C5C6E" tick={{ fontFamily: "JetBrains Mono", fontSize: 10 }} />
              <YAxis stroke="#5C5C6E" tick={{ fontFamily: "JetBrains Mono", fontSize: 10 }} />
              <Tooltip
                contentStyle={{ background: "#0A0A0D", border: "1px solid #1A1A24", fontFamily: "JetBrains Mono", fontSize: 12 }}
                labelStyle={{ color: "#8A8A9E" }}
              />
              <Line type="monotone" dataKey="pnl" stroke="#00FF66" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="terminal-panel overflow-x-auto">
        <div className="px-3 py-2 border-b border-[#1A1A24] font-mono text-[11px] uppercase tracking-widest flex items-center gap-2">
          <Wallet className="w-3.5 h-3.5 text-neon-cyan" /> Positions
        </div>
        <table className="w-full font-mono text-xs">
          <thead className="bg-black text-[#5C5C6E] uppercase">
            <tr className="border-b border-[#1A1A24]">
              <th className="text-left px-3 py-2">Token</th>
              <th className="text-center px-2">Source</th>
              <th className="text-right px-2">Entry</th>
              <th className="text-right px-2">Amount</th>
              <th className="text-right px-2">Tokens</th>
              <th className="text-center px-2">TP Hits</th>
              <th className="text-center px-2">Status</th>
              <th className="text-right px-2">P&L SOL</th>
              <th className="text-right px-2">P&L %</th>
              <th className="text-right px-3">Action</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={10} className="text-center py-12 text-[#5C5C6E] uppercase">
                  Loading positions…
                </td>
              </tr>
            )}
            {!loading && positions.length === 0 && (
              <tr>
                <td colSpan={10} className="text-center py-12 text-[#5C5C6E] uppercase">
                  No trades yet · Hit the live feed and snipe one
                </td>
              </tr>
            )}
            {positions.map((p) => (
              <tr key={p.id} className="border-b border-[#1A1A24]/60 hover:bg-[#14141A]" data-testid={`position-row-${p.id}`}>
                <td className="px-3 py-2.5">
                  <Link to={`/app/token/${p.token_address}`} className="flex items-center gap-2">
                    {p.image ? (
                      <img src={p.image} alt="" className="w-6 h-6 border border-[#1A1A24]" onError={(e) => (e.target.style.display = "none")} />
                    ) : (
                      <div className="w-6 h-6 bg-[#1A1A24] border border-[#1A1A24] flex items-center justify-center text-neon-cyan text-[10px]">
                        {p.symbol?.[0]}
                      </div>
                    )}
                    <span className="text-white">${p.symbol}</span>
                  </Link>
                </td>
                <td className="px-2 text-center">
                  <span
                    className={`px-1.5 py-0.5 border font-mono text-[9px] uppercase tracking-widest ${
                      p.source === "auto_snipe"
                        ? "border-neon-green text-neon-green"
                        : p.source === "copy_trade"
                        ? "border-neon-violet text-neon-violet"
                        : p.source === "kol_call"
                        ? "border-neon-cyan text-neon-cyan"
                        : "border-[#1A1A24] text-[#8A8A9E]"
                    }`}
                  >
                    {(p.source || "manual").replace("_", " ")}
                  </span>
                </td>
                <td className="px-2 text-right text-white">{fmtUsd(p.entry_price, { compact: false })}</td>
                <td className="px-2 text-right text-[#8A8A9E]">{p.amount_sol} SOL</td>
                <td className="px-2 text-right text-[#8A8A9E]">{p.tokens?.toLocaleString(undefined, { maximumFractionDigits: 0 })}</td>
                <td className="px-2 text-center">
                  <div className="flex items-center justify-center gap-0.5">
                    {["tp1", "tp2", "tp3"].map((tp) => (
                      <span
                        key={tp}
                        className={`font-mono text-[8px] uppercase px-1 py-0 border ${
                          (p.tp_hits || []).includes(tp)
                            ? "border-neon-green text-neon-green bg-neon-green/10"
                            : "border-[#1A1A24] text-[#5C5C6E]"
                        }`}
                      >
                        {tp}
                      </span>
                    ))}
                  </div>
                </td>
                <td className="px-2 text-center">
                  <span
                    className={`px-1.5 py-0.5 border font-mono text-[10px] uppercase ${
                      p.status === "open"
                        ? "border-neon-cyan text-neon-cyan"
                        : "border-[#1A1A24] text-[#8A8A9E]"
                    }`}
                  >
                    {p.status}
                  </span>
                </td>
                <td className={`px-2 text-right ${(p.pnl_sol || 0) >= 0 ? "text-neon-green" : "text-neon-red"}`}>
                  {p.pnl_sol !== undefined && p.pnl_sol !== null ? p.pnl_sol.toFixed(3) : p.realized_pnl_sol ? p.realized_pnl_sol.toFixed(3) : "—"}
                </td>
                <td className={`px-2 text-right ${(p.pnl_pct || 0) >= 0 ? "text-neon-green" : "text-neon-red"}`}>
                  {p.pnl_pct !== undefined && p.pnl_pct !== null ? fmtPct(p.pnl_pct) : "—"}
                </td>
                <td className="px-3 text-right">
                  {p.status === "open" ? (
                    <button
                      onClick={() => closePos(p)}
                      data-testid={`close-position-${p.id}`}
                      className="px-2 py-1 border border-neon-red text-neon-red hover:bg-neon-red hover:text-black font-mono text-[10px] uppercase tracking-widest"
                    >
                      SELL
                    </button>
                  ) : (
                    <span className="font-mono text-[10px] text-[#5C5C6E]">DONE</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function BigStat({ label, value, sub, accent = "text-white" }) {
  return (
    <div className="bg-[#0A0A0D] p-4">
      <div className="font-mono text-[10px] uppercase tracking-widest text-[#5C5C6E]">{label}</div>
      <div className={`font-mono text-2xl mt-1 ${accent}`}>{value}</div>
      {sub && <div className="font-mono text-[10px] text-[#5C5C6E] mt-1">{sub}</div>}
    </div>
  );
}

function StatCard({ label, value, accent = "text-white" }) {
  return (
    <div className="bg-[#0A0A0D] p-4">
      <div className="font-mono text-[10px] uppercase tracking-widest text-[#5C5C6E]">{label}</div>
      <div className={`font-mono text-2xl mt-1 ${accent}`}>{value}</div>
    </div>
  );
}
