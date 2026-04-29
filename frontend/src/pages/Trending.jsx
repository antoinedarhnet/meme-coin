import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Link } from "react-router-dom";
import { Flame } from "lucide-react";
import { fmtPct, fmtUsd } from "@/lib/format";
import RiskBadge from "@/components/RiskBadge";
import ScoreRing from "@/components/ScoreRing";

export default function Trending() {
  const [narratives, setNarratives] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .narratives()
      .then((d) => setNarratives(d.narratives || []))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="px-4 py-4 space-y-3">
      <div className="terminal-panel">
        <div className="px-3 py-2.5 border-b border-[#1A1A24] flex items-center gap-2">
          <Flame className="w-3.5 h-3.5 text-neon-yellow" />
          <span className="font-mono text-[11px] uppercase tracking-widest text-white">
            Narrative Heatmap
          </span>
          <span className="ml-auto font-mono text-[10px] text-[#5C5C6E] uppercase">
            Heat 0-100 · 24h Volume
          </span>
        </div>
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 divide-x divide-y divide-[#1A1A24]">
          {loading && Array(8).fill(0).map((_, i) => (
            <div key={i} className="p-4 h-28 animate-pulse bg-[#0A0A0D]" />
          ))}
          {narratives.map((n) => (
            <div
              key={n.key}
              className="p-4 hover:bg-[#14141A] relative overflow-hidden"
              data-testid={`narrative-${n.key}`}
            >
              <div
                className="absolute inset-0 pointer-events-none"
                style={{
                  background: `linear-gradient(135deg, rgba(176,38,255,${(n.heat / 100) * 0.18}) 0%, transparent 60%)`,
                }}
              />
              <div className="relative flex items-start justify-between mb-2">
                <div>
                  <div className="font-display font-bold text-lg text-white">{n.name}</div>
                  <div className="font-mono text-[10px] uppercase tracking-widest text-[#5C5C6E]">
                    {n.tokens_count} tokens · {fmtUsd(n.vol_24h)}
                  </div>
                </div>
                <div className="flex items-baseline gap-1">
                  <span
                    className="font-mono text-2xl font-bold"
                    style={{
                      color: n.heat >= 70 ? "#FF3366" : n.heat >= 50 ? "#FFD600" : "#00E5FF",
                    }}
                  >
                    {n.heat}
                  </span>
                </div>
              </div>
              <div className="relative h-1 bg-[#1A1A24] overflow-hidden mb-2">
                <div
                  className="h-full"
                  style={{
                    width: `${n.heat}%`,
                    background:
                      n.heat >= 70 ? "#FF3366" : n.heat >= 50 ? "#FFD600" : "#00E5FF",
                    boxShadow: `0 0 8px ${
                      n.heat >= 70 ? "#FF3366" : n.heat >= 50 ? "#FFD600" : "#00E5FF"
                    }`,
                  }}
                />
              </div>
              <div className="relative font-mono text-[10px] text-neon-cyan/80 uppercase tracking-widest">
                {(n.tags || []).slice(0, 4).join(" · ")}
              </div>
            </div>
          ))}
        </div>
      </div>

      {narratives.map((n) => (
        n.matched_tokens?.length > 0 && (
          <div key={n.key} className="terminal-panel">
            <div className="px-3 py-2 border-b border-[#1A1A24] flex items-center gap-2">
              <span className="font-mono text-[11px] uppercase tracking-widest text-white">
                {n.name}
              </span>
              <span
                className="px-1.5 py-0 border font-mono text-[9px] uppercase"
                style={{
                  color: n.heat >= 70 ? "#FF3366" : n.heat >= 50 ? "#FFD600" : "#00E5FF",
                  borderColor: n.heat >= 70 ? "#FF3366" : n.heat >= 50 ? "#FFD600" : "#00E5FF",
                }}
              >
                HEAT {n.heat}
              </span>
              <span className="ml-auto font-mono text-[10px] text-[#5C5C6E]">
                Matched: {n.matched_tokens.length}
              </span>
            </div>
            <div className="grid md:grid-cols-2 lg:grid-cols-3 divide-x divide-y divide-[#1A1A24]">
              {n.matched_tokens.map((t) => (
                <Link
                  key={t.address}
                  to={`/app/token/${t.address}`}
                  className="p-3 hover:bg-[#14141A] flex items-center gap-3"
                  data-testid={`narrative-token-${t.symbol}`}
                >
                  {t.image ? (
                    <img src={t.image} alt="" className="w-9 h-9 border border-[#1A1A24]" onError={(e) => (e.target.style.display = "none")} />
                  ) : (
                    <div className="w-9 h-9 bg-[#1A1A24] border border-[#1A1A24] flex items-center justify-center font-mono text-xs text-neon-cyan">
                      {t.symbol?.[0]}
                    </div>
                  )}
                  <div className="flex-1 min-w-0">
                    <div className="font-mono text-sm text-white">${t.symbol}</div>
                    <div className="font-mono text-[10px] text-[#5C5C6E] truncate">{t.name}</div>
                    <div className="font-mono text-[10px] mt-1">
                      <span className={(t.price_change_24h || 0) >= 0 ? "text-neon-green" : "text-neon-red"}>
                        {fmtPct(t.price_change_24h)}
                      </span>
                      <span className="text-[#5C5C6E] mx-1">·</span>
                      <span className="text-[#8A8A9E]">{fmtUsd(t.market_cap)}</span>
                    </div>
                  </div>
                  <div className="flex flex-col items-end gap-1">
                    <ScoreRing score={t.score || 0} size={32} stroke={3} />
                    <RiskBadge risk={t.risk} />
                  </div>
                </Link>
              ))}
            </div>
          </div>
        )
      ))}
    </div>
  );
}
