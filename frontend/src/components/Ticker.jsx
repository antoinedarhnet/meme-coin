import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { fmtPct, fmtUsd } from "@/lib/format";
import { Link } from "react-router-dom";

export default function Ticker() {
  const [items, setItems] = useState([]);

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      try {
        const r = await api.ticker();
        if (mounted) setItems(r.items || []);
      } catch (e) {
        // ignore
      }
    };
    load();
    const t = setInterval(load, 30000);
    return () => {
      mounted = false;
      clearInterval(t);
    };
  }, []);

  if (!items.length) {
    return (
      <div className="border-y border-[#1A1A24] bg-surface h-9 flex items-center px-4 font-mono text-xs text-[#5C5C6E]">
        SYNCING SOLANA STREAM…
      </div>
    );
  }

  const doubled = [...items, ...items];

  return (
    <div className="relative overflow-hidden border-y border-[#1A1A24] bg-surface h-9 flex items-center" data-testid="ticker-strip">
      <div data-testid="ticker-marquee" className="contents"></div>
      <div className="absolute left-0 top-0 bottom-0 z-10 px-3 flex items-center bg-black border-r border-[#1A1A24]">
        <span className="font-mono text-[10px] uppercase tracking-widest text-neon-green flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 bg-neon-green rounded-full animate-pulse-dot inline-block" />
          LIVE / SOL
        </span>
      </div>
      <div className="flex animate-marquee whitespace-nowrap pl-32">
        {doubled.map((it, i) => (
          <Link
            key={`${it.address}-${i}`}
            to={`/app/token/${it.address}`}
            className="px-5 font-mono text-xs flex items-center gap-2 hover:bg-[#14141A] py-2 border-r border-[#1A1A24]/40"
          >
            <span className="text-white font-semibold">${it.symbol}</span>
            <span className="text-[#5C5C6E]">{fmtUsd(it.price_usd)}</span>
            <span
              className={
                (it.change_24h || 0) >= 0 ? "text-neon-green glow-green" : "text-neon-red glow-red"
              }
            >
              {fmtPct(it.change_24h)}
            </span>
            <span className="text-neon-violet">[{it.score ?? "—"}]</span>
          </Link>
        ))}
      </div>
    </div>
  );
}
