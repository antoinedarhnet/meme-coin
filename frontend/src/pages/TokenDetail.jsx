import React, { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { api } from "@/lib/api";
import { fmtPct, fmtUsd, fmtAge, shorten } from "@/lib/format";
import ScoreRing from "@/components/ScoreRing";
import RiskBadge from "@/components/RiskBadge";
import { ArrowLeft, Copy, ExternalLink, Zap, TrendingUp, TrendingDown } from "lucide-react";
import { toast } from "sonner";

export default function TokenDetail() {
  const { addr } = useParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [amount, setAmount] = useState(0.5);
  const [slippage, setSlippage] = useState(30);

  const load = async () => {
    try {
      const d = await api.tokenDetail(addr);
      setData(d);
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
    } catch (e) {
      toast.error("Snipe failed");
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

      <div className="grid lg:grid-cols-3 gap-3">
        {/* Chart */}
        <div className="lg:col-span-2 terminal-panel">
          <div className="px-3 py-2 border-b border-[#1A1A24] font-mono text-[11px] uppercase tracking-widest flex items-center gap-2">
            <span>Live Chart</span>
            <span className="ml-auto text-[#5C5C6E]">DexScreener Embed</span>
          </div>
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
              <Zap className="w-4 h-4" /> SNIPE NOW (PAPER)
            </button>
            <div className="font-mono text-[10px] uppercase tracking-widest text-[#5C5C6E] text-center">
              Paper trade · No real funds
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
