import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { fmtPct, fmtUsd } from "@/lib/format";
import { LineChart, Line, XAxis, YAxis, ResponsiveContainer, Tooltip } from "recharts";
import { Wallet, Activity } from "lucide-react";
import { toast } from "sonner";

export default function Portfolio() {
  const [positions, setPositions] = useState([]);
  const [stats, setStats] = useState({});
  const [loading, setLoading] = useState(true);

  const load = async () => {
    const [a, b] = await Promise.all([api.positions(), api.stats()]);
    setPositions(a.positions || []);
    setStats(b || {});
    setLoading(false);
  };

  useEffect(() => {
    load();
  }, []);

  const closePos = async (p) => {
    try {
      const exit = p.entry_price * (1 + (Math.random() - 0.4));
      await api.close({ position_id: p.id, exit_price_usd: exit });
      toast.success(`Closed $${p.symbol}`);
      load();
    } catch (e) {
      toast.error("Close failed");
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
      <div className="grid grid-cols-2 md:grid-cols-5 gap-px bg-[#1A1A24] border border-[#1A1A24]">
        <StatCard label="Realized P&L" value={`${stats.realized_pnl_sol ?? 0} SOL`}
          accent={stats.realized_pnl_sol >= 0 ? "text-neon-green glow-green" : "text-neon-red"} />
        <StatCard label="Total Invested" value={`${stats.total_invested_sol ?? 0} SOL`} />
        <StatCard label="Win Rate" value={`${stats.win_rate ?? 0}%`} accent="text-neon-violet" />
        <StatCard label="Open" value={stats.open_positions ?? 0} accent="text-neon-cyan" />
        <StatCard label="Closed" value={stats.closed_positions ?? 0} />
      </div>

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
              <th className="text-right px-2">Entry</th>
              <th className="text-right px-2">Amount</th>
              <th className="text-right px-2">Tokens</th>
              <th className="text-center px-2">Status</th>
              <th className="text-right px-2">P&L SOL</th>
              <th className="text-right px-2">P&L %</th>
              <th className="text-right px-3">Action</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={8} className="text-center py-12 text-[#5C5C6E] uppercase">
                  Loading positions…
                </td>
              </tr>
            )}
            {!loading && positions.length === 0 && (
              <tr>
                <td colSpan={8} className="text-center py-12 text-[#5C5C6E] uppercase">
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
                <td className="px-2 text-right text-white">{fmtUsd(p.entry_price, { compact: false })}</td>
                <td className="px-2 text-right text-[#8A8A9E]">{p.amount_sol} SOL</td>
                <td className="px-2 text-right text-[#8A8A9E]">{p.tokens?.toLocaleString(undefined, { maximumFractionDigits: 0 })}</td>
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
                  {p.pnl_sol !== undefined && p.pnl_sol !== null ? p.pnl_sol.toFixed(3) : "—"}
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
                      CLOSE
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

function StatCard({ label, value, accent = "text-white" }) {
  return (
    <div className="bg-[#0A0A0D] p-4">
      <div className="font-mono text-[10px] uppercase tracking-widest text-[#5C5C6E]">{label}</div>
      <div className={`font-mono text-2xl mt-1 ${accent}`}>{value}</div>
    </div>
  );
}
