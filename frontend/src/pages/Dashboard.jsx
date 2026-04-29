import React, { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { fmtAge, fmtPct, fmtUsd, shorten } from "@/lib/format";
import ScoreRing from "@/components/ScoreRing";
import RiskBadge from "@/components/RiskBadge";
import { ArrowUpDown, RefreshCw, Search, Filter, Zap, ExternalLink } from "lucide-react";
import { toast } from "sonner";

const SORTS = [
  { key: "score", label: "Score" },
  { key: "age", label: "Age" },
  { key: "volume", label: "Volume" },
  { key: "mc", label: "Market Cap" },
  { key: "change_24h", label: "24h %" },
];

const RISK_FILTERS = [
  { key: "", label: "All" },
  { key: "safe", label: "Safe" },
  { key: "risky", label: "Risky" },
  { key: "danger", label: "Danger" },
];

export default function Dashboard() {
  const [tokens, setTokens] = useState([]);
  const [loading, setLoading] = useState(true);
  const [sort, setSort] = useState("score");
  const [riskFilter, setRiskFilter] = useState("");
  const [minLiq, setMinLiq] = useState(0);
  const [minScore, setMinScore] = useState(0);
  const [q, setQ] = useState("");
  const [lastRefresh, setLastRefresh] = useState(Date.now());

  const load = async () => {
    try {
      const r = await api.liveTokens({
        sort,
        risk: riskFilter || undefined,
        min_liq: minLiq,
        min_score: minScore,
        limit: 80,
      });
      setTokens(r.tokens || []);
      setLastRefresh(Date.now());
    } catch (e) {
      toast.error("Stream interrupted");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    const t = setInterval(load, 25000);
    return () => clearInterval(t);
    // eslint-disable-next-line
  }, [sort, riskFilter, minLiq, minScore]);

  const filtered = useMemo(() => {
    if (!q) return tokens;
    const ql = q.toLowerCase();
    return tokens.filter(
      (t) =>
        t.symbol?.toLowerCase().includes(ql) ||
        t.name?.toLowerCase().includes(ql) ||
        t.address?.toLowerCase().includes(ql)
    );
  }, [tokens, q]);

  const quickSnipe = async (t) => {
    try {
      await api.buy({
        token_address: t.address,
        symbol: t.symbol,
        name: t.name,
        image: t.image,
        price_usd: t.price_usd || 0.000001,
        market_cap: t.market_cap,
        amount_sol: 0.5,
      });
      toast.success(`Sniped 0.5 SOL of $${t.symbol}`, {
        description: "Paper trade opened",
      });
    } catch (e) {
      toast.error("Snipe failed");
    }
  };

  return (
    <div className="px-4 py-4">
      {/* Filter bar */}
      <div className="terminal-panel mb-3">
        <div className="flex flex-wrap items-center gap-3 px-3 py-2.5 border-b border-[#1A1A24]">
          <div className="flex items-center gap-2 px-2 py-1 border border-[#1A1A24] bg-black flex-1 min-w-[200px] max-w-md">
            <Search className="w-3.5 h-3.5 text-[#5C5C6E]" />
            <input
              data-testid="search-token-input"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="SEARCH SYMBOL / NAME / CA…"
              className="bg-transparent border-0 outline-none flex-1 font-mono text-xs uppercase placeholder:text-[#5C5C6E]"
            />
          </div>

          <div className="flex items-center gap-1 font-mono text-[10px] uppercase">
            <Filter className="w-3 h-3 text-[#5C5C6E] mr-1" />
            <span className="text-[#5C5C6E] mr-2">RISK</span>
            {RISK_FILTERS.map((r) => (
              <button
                key={r.key || "all"}
                data-testid={`risk-filter-${r.key || "all"}`}
                onClick={() => setRiskFilter(r.key)}
                className={`px-2 py-1 border ${
                  riskFilter === r.key
                    ? "border-neon-green text-neon-green"
                    : "border-[#1A1A24] text-[#8A8A9E] hover:text-white"
                }`}
              >
                {r.label}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-1 font-mono text-[10px] uppercase">
            <ArrowUpDown className="w-3 h-3 text-[#5C5C6E] mr-1" />
            <span className="text-[#5C5C6E] mr-2">SORT</span>
            {SORTS.map((s) => (
              <button
                key={s.key}
                data-testid={`sort-${s.key}`}
                onClick={() => setSort(s.key)}
                className={`px-2 py-1 border ${
                  sort === s.key
                    ? "border-neon-cyan text-neon-cyan"
                    : "border-[#1A1A24] text-[#8A8A9E] hover:text-white"
                }`}
              >
                {s.label}
              </button>
            ))}
          </div>

          <button
            onClick={load}
            data-testid="refresh-feed-button"
            className="ml-auto flex items-center gap-1.5 px-2.5 py-1 border border-[#1A1A24] hover:border-neon-cyan font-mono text-[10px] uppercase text-[#8A8A9E] hover:text-neon-cyan"
          >
            <RefreshCw className={`w-3 h-3 ${loading ? "animate-spin" : ""}`} /> Sync
          </button>
        </div>
        <div className="flex flex-wrap items-center gap-4 px-3 py-2 font-mono text-[10px] uppercase tracking-widest">
          <label className="flex items-center gap-2 text-[#5C5C6E]">
            MIN LIQ
            <input
              data-testid="min-liq-input"
              type="number"
              value={minLiq}
              onChange={(e) => setMinLiq(Number(e.target.value || 0))}
              className="w-24 bg-black border border-[#1A1A24] px-2 py-0.5 text-white"
            />
          </label>
          <label className="flex items-center gap-2 text-[#5C5C6E]">
            MIN SCORE
            <input
              data-testid="min-score-input"
              type="number"
              value={minScore}
              max={100}
              min={0}
              onChange={(e) => setMinScore(Number(e.target.value || 0))}
              className="w-16 bg-black border border-[#1A1A24] px-2 py-0.5 text-white"
            />
          </label>
          <span className="text-[#5C5C6E]">
            <span className="text-neon-green">{filtered.length}</span> RESULTS · LAST{" "}
            {Math.floor((Date.now() - lastRefresh) / 1000)}s
          </span>
        </div>
      </div>

      {/* Table */}
      <div className="terminal-panel overflow-x-auto">
        <table className="w-full font-mono text-xs">
          <thead className="sticky top-0 bg-black text-[#5C5C6E] uppercase">
            <tr className="border-b border-[#1A1A24]">
              <th className="text-left py-2.5 px-3 w-10">#</th>
              <th className="text-left px-2">Token</th>
              <th className="text-right px-2">Age</th>
              <th className="text-right px-2">Price</th>
              <th className="text-right px-2">5m</th>
              <th className="text-right px-2">1h</th>
              <th className="text-right px-2">24h</th>
              <th className="text-right px-2">MC</th>
              <th className="text-right px-2">Liq</th>
              <th className="text-right px-2">Vol 24h</th>
              <th className="text-right px-2">Buys/Sells</th>
              <th className="text-center px-2">Risk</th>
              <th className="text-center px-2">Score</th>
              <th className="text-right px-3 w-24">Action</th>
            </tr>
          </thead>
          <tbody>
            {loading && tokens.length === 0 && (
              <tr>
                <td colSpan={14} className="text-center py-12 text-[#5C5C6E] uppercase">
                  Booting stream…
                </td>
              </tr>
            )}
            {!loading && filtered.length === 0 && (
              <tr>
                <td colSpan={14} className="text-center py-12 text-[#5C5C6E] uppercase">
                  No tokens match the current filters
                </td>
              </tr>
            )}
            {filtered.map((t, i) => (
              <tr
                key={t.address}
                className="border-b border-[#1A1A24]/60 hover:bg-[#14141A] group"
                data-testid={`token-row-${i}`}
              >
                <td className="px-3 py-2 text-[#5C5C6E]">{i + 1}</td>
                <td className="px-2">
                  <Link
                    to={`/app/token/${t.address}`}
                    className="flex items-center gap-2"
                    data-testid={`token-link-${t.symbol}`}
                  >
                    {t.image ? (
                      <img
                        src={t.image}
                        alt=""
                        className="w-7 h-7 border border-[#1A1A24] object-cover"
                        onError={(e) => (e.target.style.display = "none")}
                      />
                    ) : (
                      <div className="w-7 h-7 bg-[#1A1A24] flex items-center justify-center text-neon-cyan text-[10px] border border-[#1A1A24]">
                        {t.symbol?.[0] || "?"}
                      </div>
                    )}
                    <div className="leading-tight">
                      <div className="text-white">${t.symbol}</div>
                      <div className="text-[#5C5C6E] text-[10px] truncate max-w-[140px]">{t.name}</div>
                    </div>
                  </Link>
                </td>
                <td className="px-2 text-right text-[#8A8A9E]">{fmtAge(t.age_minutes)}</td>
                <td className="px-2 text-right text-white">{fmtUsd(t.price_usd)}</td>
                {[t.price_change_5m, t.price_change_1h, t.price_change_24h].map((c, k) => (
                  <td
                    key={k}
                    className={`px-2 text-right ${
                      (c || 0) >= 0 ? "text-neon-green" : "text-neon-red"
                    }`}
                  >
                    {fmtPct(c)}
                  </td>
                ))}
                <td className="px-2 text-right text-white">{fmtUsd(t.market_cap)}</td>
                <td className="px-2 text-right text-[#8A8A9E]">{fmtUsd(t.liquidity_usd)}</td>
                <td className="px-2 text-right text-[#8A8A9E]">{fmtUsd(t.volume_24h)}</td>
                <td className="px-2 text-right text-[10px]">
                  <span className="text-neon-green">{t.txns_24h_buys || 0}</span>
                  <span className="text-[#5C5C6E]"> / </span>
                  <span className="text-neon-red">{t.txns_24h_sells || 0}</span>
                </td>
                <td className="px-2 text-center">
                  <RiskBadge risk={t.risk} />
                </td>
                <td className="px-2 text-center">
                  <ScoreRing score={t.score || 0} size={32} stroke={3} />
                </td>
                <td className="px-3 text-right">
                  <button
                    onClick={() => quickSnipe(t)}
                    data-testid={`quick-snipe-${t.symbol}`}
                    className="opacity-60 group-hover:opacity-100 px-2 py-1 border border-neon-green text-neon-green hover:bg-neon-green hover:text-black text-[10px] uppercase tracking-widest flex items-center gap-1 ml-auto"
                  >
                    <Zap className="w-3 h-3" /> SNIPE
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Disclaimer */}
      <div className="mt-3 px-3 py-2 border border-[#1A1A24] bg-[#0A0A0D] font-mono text-[10px] uppercase tracking-widest text-[#5C5C6E] flex items-center justify-between flex-wrap gap-2">
        <span>⚠ PAPER TRADING — NO REAL FUNDS · HIGH-RISK ASSETS</span>
        <a
          href="https://dexscreener.com/solana"
          target="_blank"
          rel="noreferrer"
          className="text-[#5C5C6E] hover:text-neon-cyan flex items-center gap-1"
          data-testid="dexscreener-link"
        >
          DexScreener <ExternalLink className="w-3 h-3" />
        </a>
      </div>
    </div>
  );
}
