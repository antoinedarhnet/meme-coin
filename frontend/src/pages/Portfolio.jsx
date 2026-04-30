import React, { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, API } from "@/lib/api";
import { fmtPct, fmtUsd } from "@/lib/format";
import {
  AreaChart,
  Area,
  LineChart,
  Line,
  XAxis,
  YAxis,
  ResponsiveContainer,
  Tooltip,
  CartesianGrid,
} from "recharts";
import {
  Wallet,
  Activity,
  RotateCcw,
  AlertTriangle,
  Download,
  TrendingUp,
  TrendingDown,
  Clock,
  Trophy,
  Target,
} from "lucide-react";
import { toast } from "sonner";

const TIMEFRAMES = [
  { key: "24h", label: "24H" },
  { key: "7d", label: "7D" },
  { key: "all", label: "ALL TIME" },
];

const FILTERS = [
  { key: "all", label: "All" },
  { key: "open", label: "Open" },
  { key: "closed", label: "Closed" },
  { key: "profit", label: "Profit" },
  { key: "loss", label: "Loss" },
];

export default function Portfolio() {
  const [positions, setPositions] = useState([]);
  const [stats, setStats] = useState({});
  const [bankroll, setBankroll] = useState(null);
  const [history, setHistory] = useState([]);
  const [timeframe, setTimeframe] = useState("all");
  const [filter, setFilter] = useState("all");
  const [livePrices, setLivePrices] = useState({});
  const [loading, setLoading] = useState(true);

  const load = async () => {
    try {
      const [p, s, b, h] = await Promise.all([
        api.positions(),
        api.stats({ timeframe }),
        api.bankroll(),
        api.equityHistory({ timeframe }),
      ]);
      setPositions(p.positions || []);
      setStats(s || {});
      setBankroll(b);
      setHistory(h.points || []);
    } catch (e) {}
    setLoading(false);
  };

  // Fetch live prices for open positions
  const refreshLivePrices = async (items) => {
    const open = items.filter((x) => x.status === "open");
    const addrs = [...new Set(open.map((p) => p.token_address))];
    if (!addrs.length) return;
    try {
      const out = {};
      await Promise.all(
        addrs.map(async (a) => {
          try {
            const d = await api.tokenDetail(a);
            if (d?.token?.price_usd) out[a] = d.token.price_usd;
          } catch {}
        })
      );
      setLivePrices((prev) => ({ ...prev, ...out }));
    } catch {}
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line
  }, [timeframe]);

  useEffect(() => {
    const t = setInterval(load, 12000);
    return () => clearInterval(t);
    // eslint-disable-next-line
  }, [timeframe]);

  useEffect(() => {
    if (positions.length) refreshLivePrices(positions);
    // eslint-disable-next-line
  }, [positions.length]);

  const enrichedPositions = useMemo(() => {
    return positions.map((p) => {
      if (p.status === "closed") return { ...p, current_price: p.exit_price, live_pnl_sol: p.pnl_sol, live_pnl_pct: p.pnl_pct };
      const cur = livePrices[p.token_address] || p.entry_price;
      const remaining = p.tokens_remaining ?? p.tokens;
      const costBasis = p.amount_sol * (remaining / (p.tokens || 1));
      const curValueSol = (remaining * cur) / 180;
      const livePnlSol = (p.realized_pnl_sol || 0) + (curValueSol - costBasis);
      const livePnlPct = p.amount_sol ? (livePnlSol / p.amount_sol) * 100 : 0;
      return { ...p, current_price: cur, live_pnl_sol: livePnlSol, live_pnl_pct: livePnlPct };
    });
  }, [positions, livePrices]);

  const filtered = useMemo(() => {
    switch (filter) {
      case "open":
        return enrichedPositions.filter((p) => p.status === "open");
      case "closed":
        return enrichedPositions.filter((p) => p.status === "closed");
      case "profit":
        return enrichedPositions.filter((p) => (p.live_pnl_sol || 0) > 0);
      case "loss":
        return enrichedPositions.filter((p) => (p.live_pnl_sol || 0) < 0);
      default:
        return enrichedPositions;
    }
  }, [enrichedPositions, filter]);

  const closePos = async (p) => {
    try {
      const price = livePrices[p.token_address] || p.entry_price;
      await api.close({ position_id: p.id, exit_price_usd: price });
      toast.success(`Sold $${p.symbol} @ ${price.toFixed(8)}`);
      load();
    } catch (e) {
      toast.error("Sell failed");
    }
  };

  const resetBankroll = async () => {
    if (!window.confirm("Reset bankroll & close all open positions?")) return;
    await api.resetBankroll();
    toast.success("Bankroll reset");
    load();
  };

  const downloadCsv = () => {
    window.open(api.exportCsv(), "_blank");
  };

  const totalPnl = stats.total_pnl_sol ?? 0;
  const pnlPositive = totalPnl >= 0;
  const pnlColor = pnlPositive ? "text-neon-green glow-green" : "text-neon-red glow-red";
  const pnlUsd = totalPnl * 180;
  const pnlPctVsInitial = stats.initial_sol ? (totalPnl / stats.initial_sol) * 100 : 0;

  return (
    <div className="px-4 py-4 space-y-3">
      {/* Hero PNL + timeframe */}
      <div className="terminal-panel relative overflow-hidden">
        <div className="absolute inset-0 pointer-events-none opacity-30 bg-grid" />
        <div className="relative px-5 py-5 flex items-start justify-between flex-wrap gap-4">
          <div>
            <div className="font-mono text-[10px] uppercase tracking-widest text-[#5C5C6E] flex items-center gap-2">
              <Activity className="w-3 h-3" /> TOTAL P&L · {timeframe.toUpperCase()}
            </div>
            <div className={`font-display text-5xl sm:text-6xl font-bold mt-1 ${pnlColor}`} data-testid="hero-pnl-value">
              {pnlPositive ? "+" : ""}
              {totalPnl.toFixed(3)} <span className="text-3xl">SOL</span>
            </div>
            <div className="flex flex-wrap items-center gap-3 mt-2 font-mono text-xs">
              <span className={pnlColor}>
                {pnlPositive ? "+" : ""}
                {pnlPctVsInitial.toFixed(2)}%
              </span>
              <span className="text-[#5C5C6E]">·</span>
              <span className="text-[#8A8A9E]">
                {pnlPositive ? "+" : ""}
                ${pnlUsd.toFixed(2)} USD
              </span>
              <span className="text-[#5C5C6E]">·</span>
              <span className="text-[#8A8A9E]">Balance {(bankroll?.balance_sol ?? 0).toFixed(3)} SOL</span>
            </div>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            {TIMEFRAMES.map((tf) => (
              <button
                key={tf.key}
                onClick={() => setTimeframe(tf.key)}
                data-testid={`timeframe-${tf.key}`}
                className={`px-3 py-2 border font-mono text-[10px] uppercase tracking-widest ${
                  timeframe === tf.key
                    ? "border-neon-cyan text-neon-cyan bg-neon-cyan/5"
                    : "border-[#1A1A24] text-[#8A8A9E] hover:text-white"
                }`}
              >
                {tf.label}
              </button>
            ))}
            <button
              onClick={downloadCsv}
              data-testid="export-csv-button"
              className="flex items-center gap-1.5 px-3 py-2 border border-[#1A1A24] hover:border-neon-green font-mono text-[10px] uppercase tracking-widest text-[#8A8A9E] hover:text-neon-green"
            >
              <Download className="w-3 h-3" /> CSV
            </button>
            <button
              onClick={resetBankroll}
              data-testid="reset-bankroll-button"
              className="flex items-center gap-1.5 px-3 py-2 border border-[#1A1A24] hover:border-neon-red font-mono text-[10px] uppercase tracking-widest text-[#8A8A9E] hover:text-neon-red"
            >
              <RotateCcw className="w-3 h-3" /> RESET
            </button>
          </div>
        </div>
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-px bg-[#1A1A24] border border-[#1A1A24]" data-testid="kpi-grid">
        <Kpi
          label="Realized"
          value={`${(stats.realized_pnl_sol ?? 0) >= 0 ? "+" : ""}${(stats.realized_pnl_sol ?? 0).toFixed(3)}`}
          unit="SOL"
          accent={(stats.realized_pnl_sol ?? 0) >= 0 ? "text-neon-green" : "text-neon-red"}
          icon={TrendingUp}
        />
        <Kpi
          label="Unrealized"
          value={`${(stats.unrealized_pnl_sol ?? 0) >= 0 ? "+" : ""}${(stats.unrealized_pnl_sol ?? 0).toFixed(3)}`}
          unit="SOL"
          accent={(stats.unrealized_pnl_sol ?? 0) >= 0 ? "text-neon-cyan" : "text-neon-red"}
          icon={Activity}
        />
        <Kpi
          label="Win Rate"
          value={`${stats.win_rate ?? 0}%`}
          unit={`${stats.wins ?? 0}W / ${stats.losses ?? 0}L`}
          accent="text-neon-violet"
          icon={Trophy}
        />
        <Kpi
          label="Invested"
          value={`${(stats.total_invested_sol ?? 0).toFixed(2)}`}
          unit="SOL"
          icon={Wallet}
        />
        <Kpi
          label="Recovered"
          value={`${(stats.total_recovered_sol ?? 0).toFixed(2)}`}
          unit="SOL"
          accent="text-neon-cyan"
          icon={Target}
        />
        <Kpi
          label="Avg Hold"
          value={`${Math.round(stats.avg_hold_min || 0)}m`}
          unit={`${stats.trades_total ?? 0} trades`}
          accent="text-white"
          icon={Clock}
        />
      </div>

      {/* Equity curve */}
      <div className="terminal-panel">
        <div className="px-3 py-2 border-b border-[#1A1A24] font-mono text-[11px] uppercase tracking-widest flex items-center gap-2">
          <Activity className="w-3.5 h-3.5 text-neon-green" />
          EQUITY CURVE · {timeframe.toUpperCase()}
          {stats.best_trade && (
            <span className="ml-auto flex items-center gap-2 font-mono text-[10px] text-[#5C5C6E]">
              BEST <span className="text-neon-green">${stats.best_trade.symbol} {fmtPct(stats.best_trade.pnl_pct)}</span>
              {stats.worst_trade && stats.worst_trade.symbol !== stats.best_trade.symbol && (
                <>
                  · WORST <span className="text-neon-red">${stats.worst_trade.symbol} {fmtPct(stats.worst_trade.pnl_pct)}</span>
                </>
              )}
            </span>
          )}
        </div>
        <div className="h-64 p-2">
          <ResponsiveContainer width="100%" height="100%" minHeight={200}>
            <AreaChart data={history.length ? history : [{ ts: new Date().toISOString(), equity: bankroll?.initial_sol ?? 10 }]}>
              <defs>
                <linearGradient id="equityGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#00FF66" stopOpacity={0.4} />
                  <stop offset="100%" stopColor="#00FF66" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="#1A1A24" vertical={false} />
              <XAxis
                dataKey="ts"
                stroke="#5C5C6E"
                tick={{ fontFamily: "JetBrains Mono", fontSize: 9 }}
                tickFormatter={(v) => {
                  try {
                    const d = new Date(v);
                    return d.toLocaleDateString(undefined, { month: "short", day: "2-digit" });
                  } catch {
                    return "";
                  }
                }}
              />
              <YAxis stroke="#5C5C6E" tick={{ fontFamily: "JetBrains Mono", fontSize: 9 }} />
              <Tooltip
                contentStyle={{
                  background: "#0A0A0D",
                  border: "1px solid #1A1A24",
                  fontFamily: "JetBrains Mono",
                  fontSize: 11,
                  borderRadius: 2,
                }}
                labelFormatter={(v) => new Date(v).toLocaleString()}
                formatter={(v) => [`${v} SOL`, "Equity"]}
              />
              <Area type="monotone" dataKey="equity" stroke="#00FF66" strokeWidth={2} fill="url(#equityGrad)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Filters + trade table */}
      <div className="terminal-panel">
        <div className="flex items-center gap-2 px-3 py-2 border-b border-[#1A1A24] font-mono text-[11px] uppercase tracking-widest flex-wrap">
          <Wallet className="w-3.5 h-3.5 text-neon-cyan" />
          <span>TRADES</span>
          <div className="flex items-center gap-1 ml-4">
            {FILTERS.map((f) => (
              <button
                key={f.key}
                onClick={() => setFilter(f.key)}
                data-testid={`filter-${f.key}`}
                className={`px-2 py-1 border ${
                  filter === f.key
                    ? "border-neon-cyan text-neon-cyan"
                    : "border-[#1A1A24] text-[#8A8A9E] hover:text-white"
                } font-mono text-[10px] uppercase`}
              >
                {f.label}
              </button>
            ))}
          </div>
          <span className="ml-auto text-[#5C5C6E]">
            {filtered.length} / {enrichedPositions.length}
          </span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full font-mono text-xs">
            <thead className="bg-black text-[#5C5C6E] uppercase">
              <tr className="border-b border-[#1A1A24]">
                <th className="text-left px-3 py-2">Token</th>
                <th className="text-center px-2">Source</th>
                <th className="text-right px-2">Buy Price</th>
                <th className="text-right px-2">Current / Sell</th>
                <th className="text-right px-2">Amount</th>
                <th className="text-right px-2">PNL SOL</th>
                <th className="text-right px-2">PNL $</th>
                <th className="text-right px-2">PNL %</th>
                <th className="text-right px-2">Hold</th>
                <th className="text-center px-2">Status</th>
                <th className="text-right px-3">Action</th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr>
                  <td colSpan={11} className="text-center py-12 text-[#5C5C6E] uppercase">
                    Loading…
                  </td>
                </tr>
              )}
              {!loading && filtered.length === 0 && (
                <tr>
                  <td colSpan={11} className="text-center py-12 text-[#5C5C6E] uppercase">
                    No trades match this filter
                  </td>
                </tr>
              )}
              {filtered.map((p) => {
                const pnlSol = p.live_pnl_sol ?? 0;
                const pnlUsd = pnlSol * 180;
                const pnlPct = p.live_pnl_pct ?? 0;
                const holdMin = (() => {
                  try {
                    const o = new Date(p.opened_at).getTime();
                    const c = p.closed_at ? new Date(p.closed_at).getTime() : Date.now();
                    return Math.round((c - o) / 60000);
                  } catch {
                    return 0;
                  }
                })();
                const pnlClass = pnlSol >= 0 ? "text-neon-green" : "text-neon-red";
                return (
                  <tr key={p.id} className="border-b border-[#1A1A24]/60 hover:bg-[#14141A]" data-testid={`trade-row-${p.id}`}>
                    <td className="px-3 py-2">
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
                    <td className="px-2 text-right text-white">{fmtUsd(p.current_price, { compact: false })}</td>
                    <td className="px-2 text-right text-[#8A8A9E]">{p.amount_sol} SOL</td>
                    <td className={`px-2 text-right ${pnlClass}`}>
                      {pnlSol >= 0 ? "+" : ""}
                      {pnlSol.toFixed(3)}
                    </td>
                    <td className={`px-2 text-right ${pnlClass}`}>
                      {pnlUsd >= 0 ? "+" : ""}
                      ${pnlUsd.toFixed(2)}
                    </td>
                    <td className={`px-2 text-right ${pnlClass}`}>{fmtPct(pnlPct)}</td>
                    <td className="px-2 text-right text-[#8A8A9E]">
                      {holdMin < 60 ? `${holdMin}m` : `${(holdMin / 60).toFixed(1)}h`}
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
                    <td className="px-3 text-right">
                      {p.status === "open" ? (
                        <button
                          onClick={() => closePos(p)}
                          data-testid={`sell-button-${p.id}`}
                          className="px-2 py-1 border border-neon-red text-neon-red hover:bg-neon-red hover:text-black font-mono text-[10px] uppercase tracking-widest"
                        >
                          SELL
                        </button>
                      ) : (
                        <span className="font-mono text-[10px] text-[#5C5C6E]">DONE</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function Kpi({ label, value, unit, accent = "text-white", icon: Icon }) {
  return (
    <div className="bg-[#0A0A0D] p-4">
      <div className="font-mono text-[10px] uppercase tracking-widest text-[#5C5C6E] flex items-center gap-1">
        {Icon && <Icon className="w-3 h-3" />}
        {label}
      </div>
      <div className={`font-mono text-xl lg:text-2xl mt-1 ${accent}`}>{value}</div>
      {unit && <div className="font-mono text-[10px] text-[#5C5C6E] mt-0.5">{unit}</div>}
    </div>
  );
}
