import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Plus, Trash2, Twitter, Trophy, Target, Activity } from "lucide-react";
import { toast } from "sonner";
import RiskBadge from "@/components/RiskBadge";
import ScoreRing from "@/components/ScoreRing";
import { Link } from "react-router-dom";

const TIER_COLOR = {
  S: "text-neon-violet border-neon-violet/40",
  A: "text-neon-cyan border-neon-cyan/40",
  B: "text-neon-yellow border-neon-yellow/40",
  C: "text-[#8A8A9E] border-[#1A1A24]",
};

export default function KOLWatchlist() {
  const [kols, setKols] = useState([]);
  const [calls, setCalls] = useState({ calls: [], cross_calls: [] });
  const [handle, setHandle] = useState("");
  const [tier, setTier] = useState("B");
  const [loading, setLoading] = useState(true);

  const load = async () => {
    try {
      const [a, b] = await Promise.all([api.kols(), api.kolCalls()]);
      setKols(a.kols || []);
      setCalls(b);
    } catch (e) {}
    setLoading(false);
  };

  useEffect(() => {
    load();
    const t = setInterval(load, 45000);
    return () => clearInterval(t);
  }, []);

  const addKol = async (e) => {
    e.preventDefault();
    if (!handle) return;
    try {
      await api.addKol({ handle, tier });
      toast.success(`Tracking ${handle}`);
      setHandle("");
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed to add KOL");
    }
  };

  const remove = async (id) => {
    await api.removeKol(id);
    toast.message("KOL removed");
    load();
  };

  return (
    <div className="px-4 py-4 grid lg:grid-cols-3 gap-3">
      {/* Left: KOL list */}
      <div className="lg:col-span-2 space-y-3">
        <div className="terminal-panel">
          <div className="px-3 py-2 border-b border-[#1A1A24] flex items-center gap-2">
            <Twitter className="w-3.5 h-3.5 text-neon-cyan" />
            <span className="font-mono text-[11px] uppercase tracking-widest text-white">
              KOL Surveillance · {kols.length}
            </span>
          </div>
          <form onSubmit={addKol} className="flex gap-2 px-3 py-2 border-b border-[#1A1A24]">
            <input
              data-testid="kol-handle-input"
              value={handle}
              onChange={(e) => setHandle(e.target.value)}
              placeholder="@HANDLE"
              className="flex-1 bg-black border border-[#1A1A24] px-3 py-1.5 font-mono text-xs uppercase outline-none focus:border-neon-cyan"
            />
            <select
              data-testid="kol-tier-select"
              value={tier}
              onChange={(e) => setTier(e.target.value)}
              className="bg-black border border-[#1A1A24] px-2 py-1.5 font-mono text-xs uppercase outline-none"
            >
              <option value="S">Tier S</option>
              <option value="A">Tier A</option>
              <option value="B">Tier B</option>
              <option value="C">Tier C</option>
            </select>
            <button
              data-testid="add-kol-button"
              type="submit"
              className="btn-neon-green flex items-center gap-1"
            >
              <Plus className="w-3 h-3" /> ADD
            </button>
          </form>
          <div className="grid sm:grid-cols-2 divide-x divide-y divide-[#1A1A24]">
            {loading && (
              <div className="col-span-2 py-8 text-center font-mono text-xs text-[#5C5C6E] uppercase">
                Loading…
              </div>
            )}
            {kols.map((k) => (
              <div
                key={k.id}
                className="p-3 hover:bg-[#14141A] group relative"
                data-testid={`kol-card-${k.handle}`}
              >
                <div className="flex items-start gap-3">
                  <div className="w-10 h-10 bg-[#1A1A24] border border-[#1A1A24] flex items-center justify-center font-mono text-sm text-white">
                    {k.name?.[0] || k.handle?.[1] || "?"}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-display font-bold text-white">{k.name}</span>
                      <span
                        className={`px-1.5 py-0 border ${TIER_COLOR[k.tier] || TIER_COLOR.C} font-mono text-[10px] uppercase`}
                      >
                        T{k.tier}
                      </span>
                    </div>
                    <div className="font-mono text-[10px] text-[#5C5C6E] truncate">
                      {k.handle} · {k.followers?.toLocaleString()} followers
                    </div>
                    <div className="grid grid-cols-3 gap-2 mt-2">
                      <Stat icon={Trophy} label="Win %" value={`${k.win_rate?.toFixed(0)}%`} color="text-neon-green" />
                      <Stat icon={Target} label="ROI" value={`${k.avg_roi?.toFixed(0)}%`} color="text-neon-violet" />
                      <Stat icon={Activity} label="Calls" value={k.total_calls} color="text-neon-cyan" />
                    </div>
                  </div>
                  <button
                    onClick={() => remove(k.id)}
                    data-testid={`remove-kol-${k.handle}`}
                    className="opacity-0 group-hover:opacity-100 p-1 text-[#5C5C6E] hover:text-neon-red"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Right: Cross calls */}
      <div className="space-y-3">
        <div className="terminal-panel">
          <div className="px-3 py-2 border-b border-[#1A1A24] flex items-center gap-2">
            <span className="w-2 h-2 bg-neon-violet rounded-full animate-pulse-dot" />
            <span className="font-mono text-[11px] uppercase tracking-widest text-neon-violet glow-violet">
              CROSS-CALL RADAR
            </span>
          </div>
          <div className="divide-y divide-[#1A1A24] max-h-[480px] overflow-y-auto">
            {(calls.cross_calls || []).length === 0 && (
              <div className="p-4 text-center font-mono text-[10px] uppercase tracking-widest text-[#5C5C6E]">
                No convergence detected. Stay sharp.
              </div>
            )}
            {(calls.cross_calls || []).map((c) => (
              <Link
                key={c.token_address}
                to={`/app/token/${c.token_address}`}
                className="block p-3 hover:bg-[#14141A]"
                data-testid={`cross-call-${c.token_symbol}`}
              >
                <div className="flex items-center gap-2 mb-2">
                  {c.token_image ? (
                    <img
                      src={c.token_image}
                      alt=""
                      className="w-8 h-8 border border-[#1A1A24]"
                      onError={(e) => (e.target.style.display = "none")}
                    />
                  ) : (
                    <div className="w-8 h-8 bg-[#1A1A24] border border-[#1A1A24] flex items-center justify-center font-mono text-[10px] text-neon-cyan">
                      {c.token_symbol?.[0]}
                    </div>
                  )}
                  <div className="flex-1 min-w-0">
                    <div className="font-mono text-sm text-white">${c.token_symbol}</div>
                    <div className="font-mono text-[10px] text-[#5C5C6E] truncate">
                      {c.token_name}
                    </div>
                  </div>
                  <ScoreRing score={c.token_score || 0} size={30} stroke={3} />
                </div>
                <div className="flex items-center gap-2 mb-2">
                  <span className="px-1.5 py-0.5 border border-neon-violet text-neon-violet font-mono text-[10px] uppercase">
                    {c.callers_count} CALLERS
                  </span>
                  <RiskBadge risk={c.token_risk} />
                  <span className="ml-auto font-mono text-[10px] text-[#5C5C6E]">
                    CONF {Math.round(c.confidence)}
                  </span>
                </div>
                <div className="flex flex-wrap gap-1">
                  {c.callers.slice(0, 4).map((cc) => (
                    <span
                      key={cc.id}
                      className="px-1.5 py-0.5 bg-black border border-[#1A1A24] font-mono text-[9px] text-[#8A8A9E]"
                    >
                      {cc.kol_handle}
                    </span>
                  ))}
                </div>
              </Link>
            ))}
          </div>
        </div>

        <div className="terminal-panel">
          <div className="px-3 py-2 border-b border-[#1A1A24] font-mono text-[11px] uppercase tracking-widest">
            Latest Mentions
          </div>
          <div className="divide-y divide-[#1A1A24] max-h-[400px] overflow-y-auto">
            {(calls.calls || []).slice(0, 30).map((c) => (
              <div key={c.id} className="p-2.5 hover:bg-[#14141A]" data-testid={`call-${c.id}`}>
                <div className="flex items-center justify-between mb-1">
                  <span className="font-mono text-[11px] text-white">{c.kol_handle}</span>
                  <span className="font-mono text-[10px] text-[#5C5C6E]">{c.minutes_ago}m</span>
                </div>
                <div className="font-mono text-[11px] text-[#8A8A9E] mb-1 italic">
                  "{c.tweet_excerpt}"
                </div>
                <div className="flex items-center gap-2">
                  <Link
                    to={`/app/token/${c.token_address}`}
                    className="font-mono text-[10px] text-neon-cyan hover:underline"
                  >
                    ${c.token_symbol}
                  </Link>
                  <RiskBadge risk={c.token_risk} />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function Stat({ icon: Icon, label, value, color = "text-white" }) {
  return (
    <div className="border border-[#1A1A24] bg-black/40 p-1.5">
      <div className="flex items-center gap-1 font-mono text-[9px] uppercase tracking-widest text-[#5C5C6E]">
        <Icon className="w-2.5 h-2.5" />
        {label}
      </div>
      <div className={`font-mono text-sm ${color}`}>{value}</div>
    </div>
  );
}
