import React, { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { fmtAge, fmtUsd } from "@/lib/format";
import ScoreRing from "@/components/ScoreRing";
import RiskBadge from "@/components/RiskBadge";
import { ArrowUpDown, RefreshCw, Search, Filter, Zap, ExternalLink, Power } from "lucide-react";
import { toast } from "sonner";

const SORTS = [
  { key: "score", label: "Score" },
  { key: "age", label: "Age" },
];

const AGE_FILTERS = [
  { key: "5", label: "< 5m" },
  { key: "15", label: "< 15m" },
  { key: "60", label: "< 1h" },
];

export default function NewPairs() {
  const navigate = useNavigate();
  const [tokens, setTokens] = useState([]);
  const [holdings, setHoldings] = useState(new Set());
  const [loading, setLoading] = useState(true);
  const [sort, setSort] = useState("score");
  const [ageFilter, setAgeFilter] = useState("60");
  const [q, setQ] = useState("");
  const [lastRefresh, setLastRefresh] = useState(Date.now());
  const [npEngine, setNpEngine] = useState(null);
  const [settings, setSettings] = useState(null);
  const [error, setError] = useState(null);
  const [scanStats, setScanStats] = useState({ scanned: 0, filtered: 0 });
  const errorRef = useRef(false);

  const load = async () => {
    try {
      logger_info("NewPairs load: Starting fetch with timeout 15s...");
      const results = await Promise.allSettled([
        api.newPairs({ max_age_min: Number(ageFilter), limit: 80 }, { timeout: 15000 }),
        api.positions({ status: "open" }),
        api.newPairsEngine(),
        api.settings(),
      ]);

      const [rRes, pRes, eRes, sRes] = results;

      if (rRes.status === "fulfilled") {
        const r = rRes.value;
        logger_info(`NewPairs load: Got ${r.tokens?.length || 0} tokens`);
        setTokens(r.tokens || []);
        setScanStats({
          scanned: r?.meta?.scanned ?? r?.scanned ?? 0,
          filtered: r?.meta?.filtered ?? r?.filtered ?? 0,
        });
      } else {
        const error = rRes.reason;
        console.error("NewPairs GET /tokens/new-pairs failed", error);
        logger_error(`NewPairs fetch failed: ${error?.message || error}`);
        // More specific error handling
        if (error?.code === "ECONNABORTED") {
          setError("Backend timeout (15s) - check server logs");
        } else if (error?.response?.status === 0) {
          setError("Cannot reach backend - connection refused");
        } else {
          setError(`Backend error: ${error?.message || "unknown"}`);
        }
      }

      if (pRes.status === "fulfilled") {
        const p = pRes.value;
        setHoldings(new Set((p.positions || []).map((x) => x.token_address)));
      } else {
        console.error("NewPairs GET /portfolio/positions failed", pRes.reason);
      }

      if (eRes.status === "fulfilled") {
        setNpEngine(eRes.value);
      } else {
        console.error("NewPairs GET /engine/new-pairs/status failed", eRes.reason);
      }

      if (sRes.status === "fulfilled") {
        setSettings(sRes.value);
      } else {
        console.error("NewPairs GET /settings failed", sRes.reason);
      }

      setLastRefresh(Date.now());
      if (rRes.status === "fulfilled") {
        setError(null);
        errorRef.current = false;
      }
    } catch (e) {
      console.error("NewPairs load failed", e);
      logger_error(`NewPairs load() exception: ${e?.message || e}`);
      setError(`Exception: ${e?.message || "Stream interrupted"}`);
      if (!errorRef.current) {
        toast.error("NewPairs load failed - see console");
        errorRef.current = true;
      }
    } finally {
      setLoading(false);
    }
  };

  // Helper logging
  const logger_info = (msg) => {
    console.log(`[NewPairs] ${msg}`);
  };
  const logger_error = (msg) => {
    console.error(`[NewPairs] ${msg}`);
  };

  useEffect(() => {
    load();
    const interval = error ? 5000 : 20000;
    const t = setInterval(load, interval);
    return () => clearInterval(t);
    // eslint-disable-next-line
  }, [sort, ageFilter, error]);

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

  const toggleNewPairs = async () => {
    if (!settings) return;
    try {
      const next = !settings.new_pairs_enabled;
      const payload = { ...settings, new_pairs_enabled: next };
      await api.saveSettings(payload);
      setSettings(payload);
      toast.success(next ? "NEW PAIRS AUTO-SNIPE ARMED" : "New pairs disarmed");
      load();
    } catch (e) {
      toast.error("Toggle failed");
    }
  };

  const quickSnipe = async (e, t) => {
    if (e) {
      e.stopPropagation();
      e.preventDefault();
    }
    try {
      await api.buy({
        token_address: t.address,
        symbol: t.symbol,
        name: t.name,
        image: t.image,
        price_usd: t.price_usd || 0.000001,
        market_cap: t.market_cap,
        amount_sol: 0.1,
      });
      toast.success(`Sniped 0.1 SOL of $${t.symbol}`, {
        description: "Position opened",
      });
    } catch (e) {
      toast.error("Snipe failed");
    }
  };

  const isSnipeOn = npEngine?.new_pairs_enabled;

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
            <span className="text-[#5C5C6E] mr-2">AGE</span>
            {AGE_FILTERS.map((a) => (
              <button
                key={a.key}
                data-testid={`age-filter-${a.key}`}
                onClick={() => setAgeFilter(a.key)}
                className={`px-2 py-1 border ${
                  ageFilter === a.key
                    ? "border-neon-green text-neon-green"
                    : "border-[#1A1A24] text-[#8A8A9E] hover:text-white"
                }`}
              >
                {a.label}
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
            onClick={toggleNewPairs}
            data-testid="new-pairs-auto-toggle"
            className={`flex items-center gap-1.5 px-3 py-2 border font-mono text-[10px] uppercase tracking-widest transition-colors ${
              isSnipeOn
                ? "border-neon-green text-neon-green bg-neon-green/10 glow-green"
                : "border-[#1A1A24] text-[#8A8A9E] hover:border-neon-green hover:text-neon-green"
            }`}
          >
            <Power className={`w-3 h-3 ${isSnipeOn ? "animate-pulse-dot" : ""}`} />
            AUTO-SNIPE NEW PAIRS {isSnipeOn ? "ARMED" : "OFF"}
          </button>

          {error && (
            <button
              onClick={load}
              data-testid="new-pairs-reconnect"
              className="flex items-center gap-1.5 px-2.5 py-1 border border-neon-red text-neon-red font-mono text-[10px] uppercase tracking-widest hover:bg-neon-red hover:text-black"
            >
              RECONNECT
            </button>
          )}

          <button
            onClick={load}
            data-testid="refresh-feed-button"
            className="ml-auto flex items-center gap-1.5 px-2.5 py-1 border border-[#1A1A24] hover:border-neon-cyan font-mono text-[10px] uppercase text-[#8A8A9E] hover:text-neon-cyan"
          >
            <RefreshCw className={`w-3 h-3 ${loading ? "animate-spin" : ""}`} /> Sync
          </button>
        </div>
        <div className="flex flex-wrap items-center gap-4 px-3 py-2 font-mono text-[10px] uppercase tracking-widest">
          <span className="text-[#5C5C6E]">
            <span className="text-neon-green">{filtered.length}</span> RESULTS · LAST{" "}
            {Math.floor((Date.now() - lastRefresh) / 1000)}s
          </span>
          <span className="text-[#5C5C6E]">
            <span className="text-neon-cyan">{scanStats.scanned}</span> TOKENS SCANNED /{" "}
            <span className="text-neon-red">{scanStats.filtered}</span> FILTERED
          </span>
          {error && <span className="text-neon-red">{error}</span>}
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
              <th className="text-right px-2">MC</th>
              <th className="text-right px-2">Liq</th>
              <th className="text-right px-2">Vol 5m</th>
              <th className="text-right px-2">Buys/Sells</th>
              <th className="text-center px-2">Risk</th>
              <th className="text-center px-2">Score</th>
              <th className="text-right px-3 w-24">Action</th>
            </tr>
          </thead>
          <tbody>
            {loading && tokens.length === 0 && (
              <tr>
                <td colSpan={11} className="text-center py-12 text-[#5C5C6E] uppercase">
                  Booting stream…
                </td>
              </tr>
            )}
            {!loading && filtered.length === 0 && (
              <tr>
                <td colSpan={11} className="text-center py-12 text-[#5C5C6E] uppercase">
                  No tokens match the current filters
                </td>
              </tr>
            )}
            {filtered.map((t, i) => (
              <tr
                key={t.address}
                className="border-b border-[#1A1A24]/60 hover:bg-[#14141A] group cursor-pointer"
                data-testid={`token-row-${i}`}
                onClick={() => navigate(`/app/token/${t.address}`)}
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
                      <div className="text-white flex items-center gap-1.5">
                        ${t.symbol}
                        {holdings.has(t.address) && (
                          <span
                            className="px-1 py-0 border border-neon-green text-neon-green font-mono text-[8px] uppercase tracking-widest glow-green"
                            data-testid={`holding-badge-${t.symbol}`}
                            title="You hold an open position"
                          >
                            ● HOLDING
                          </span>
                        )}
                      </div>
                      <div className="text-[#5C5C6E] text-[10px] truncate max-w-[140px]">{t.name}</div>
                    </div>
                  </Link>
                </td>
                <td className="px-2 text-right text-[#8A8A9E]">{fmtAge(t.age_minutes)}</td>
                <td className="px-2 text-right text-white">{fmtUsd(t.price_usd)}</td>
                <td className="px-2 text-right text-white">{fmtUsd(t.market_cap)}</td>
                <td className="px-2 text-right text-[#8A8A9E]">{fmtUsd(t.liquidity_usd)}</td>
                <td className="px-2 text-right text-[#8A8A9E]">{fmtUsd(t.volume_5m)}</td>
                <td className="px-2 text-right text-[10px]">
                  <span className="text-neon-green">{t.txns_5m_buys || 0}</span>
                  <span className="text-[#5C5C6E]"> / </span>
                  <span className="text-neon-red">{t.txns_5m_sells || 0}</span>
                </td>
                <td className="px-2 text-center">
                  <RiskBadge risk={t.risk} />
                </td>
                <td className="px-2 text-center">
                  <ScoreRing score={t.score || 0} size={32} stroke={3} />
                </td>
                <td className="px-3 text-right">
                  <button
                    onClick={(e) => quickSnipe(e, t)}
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
        <span>⚠ HIGH-RISK MEMECOINS · DYOR BEFORE EVERY SNIPE</span>
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
