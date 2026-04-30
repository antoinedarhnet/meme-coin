import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Bell, Save, Plus, Trash2, Zap, TrendingDown, Shield } from "lucide-react";
import { toast } from "sonner";

export default function SettingsPage() {
  const [settings, setSettings] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [name, setName] = useState("");
  const [scoreThr, setScoreThr] = useState(70);

  const load = async () => {
    const [s, a] = await Promise.all([api.settings(), api.alerts()]);
    setSettings(s);
    setAlerts(a.alerts || []);
  };

  useEffect(() => {
    load();
  }, []);

  const save = async (patch = {}) => {
    try {
      const next = { ...settings, ...patch };
      setSettings(next);
      await api.saveSettings(next);
      toast.success("Settings saved");
    } catch (e) {
      toast.error("Save failed");
    }
  };

  const addAlert = async (e) => {
    e.preventDefault();
    if (!name) return;
    try {
      await api.addAlert({ name, type: "score", score_threshold: Number(scoreThr), channels: ["browser"] });
      setName("");
      load();
      toast.success("Alert created");
    } catch (e) {
      toast.error("Create failed");
    }
  };

  const removeAlert = async (id) => {
    await api.removeAlert(id);
    load();
  };

  if (!settings) {
    return <div className="px-4 py-8 font-mono text-xs uppercase text-[#5C5C6E]">Loading…</div>;
  }

  const set = (k) => (v) => setSettings({ ...settings, [k]: typeof v === "string" ? v : Number(v) });

  return (
    <div className="px-4 py-4 grid lg:grid-cols-2 gap-3">
      {/* Auto-Snipe Engine */}
      <div className="terminal-panel lg:col-span-2">
        <div className="px-3 py-2 border-b border-[#1A1A24] font-mono text-[11px] uppercase tracking-widest flex items-center gap-2">
          <Zap className="w-3.5 h-3.5 text-neon-green" />
          <span className="text-neon-green glow-green">AUTO-SNIPE ENGINE</span>
          <label className="ml-auto flex items-center gap-2 cursor-pointer" data-testid="auto-snipe-enabled-toggle">
            <input
              type="checkbox"
              checked={settings.auto_snipe_enabled}
              onChange={(e) => save({ auto_snipe_enabled: e.target.checked })}
              className="accent-neon-green"
            />
            <span className="font-mono text-[11px] uppercase tracking-widest">
              {settings.auto_snipe_enabled ? "ARMED" : "DISARMED"}
            </span>
          </label>
        </div>
        <div className="p-4 grid grid-cols-2 md:grid-cols-4 gap-3">
          <Field label="Amount per snipe (SOL)" type="number" step="0.1" value={settings.auto_snipe_amount_sol} onChange={set("auto_snipe_amount_sol")} testid="setting-snipe-amount" />
          <Field label="Min AI Score" type="number" value={settings.auto_snipe_min_score} onChange={set("auto_snipe_min_score")} testid="setting-min-score" />
          <Field label="Min Liquidity USD" type="number" value={settings.auto_snipe_min_liq_usd} onChange={set("auto_snipe_min_liq_usd")} testid="setting-min-liq" />
          <Field label="Max age (min)" type="number" value={settings.auto_snipe_max_age_min} onChange={set("auto_snipe_max_age_min")} testid="setting-max-age" />
        </div>
        <div className="px-4 pb-4">
          <button onClick={() => save()} data-testid="save-snipe-rules" className="btn-neon-green flex items-center gap-2">
            <Save className="w-3.5 h-3.5" /> SAVE RULES
          </button>
        </div>
      </div>

      {/* Auto-Sell ladder */}
      <div className="terminal-panel lg:col-span-2">
        <div className="px-3 py-2 border-b border-[#1A1A24] font-mono text-[11px] uppercase tracking-widest flex items-center gap-2">
          <TrendingDown className="w-3.5 h-3.5 text-neon-cyan" />
          <span className="text-neon-cyan glow-cyan">AUTO-SELL LADDER (TP / SL / TRAILING)</span>
          <label className="ml-auto flex items-center gap-2 cursor-pointer" data-testid="auto-sell-enabled-toggle">
            <input
              type="checkbox"
              checked={settings.auto_sell_enabled}
              onChange={(e) => save({ auto_sell_enabled: e.target.checked })}
              className="accent-neon-cyan"
            />
            <span className="font-mono text-[11px] uppercase tracking-widest">
              {settings.auto_sell_enabled ? "ACTIVE" : "OFF"}
            </span>
          </label>
        </div>
        <div className="p-4 grid grid-cols-2 md:grid-cols-4 gap-3">
          <Field label="TP1 %" value={settings.tp1_pct} onChange={set("tp1_pct")} type="number" testid="setting-tp1" />
          <Field label="TP1 sell %" value={settings.tp1_sell_pct} onChange={set("tp1_sell_pct")} type="number" testid="setting-tp1-sell" />
          <Field label="TP2 %" value={settings.tp2_pct} onChange={set("tp2_pct")} type="number" testid="setting-tp2" />
          <Field label="TP2 sell %" value={settings.tp2_sell_pct} onChange={set("tp2_sell_pct")} type="number" testid="setting-tp2-sell" />
          <Field label="TP3 %" value={settings.tp3_pct} onChange={set("tp3_pct")} type="number" testid="setting-tp3" />
          <Field label="TP3 sell %" value={settings.tp3_sell_pct} onChange={set("tp3_sell_pct")} type="number" testid="setting-tp3-sell" />
          <Field label="Trailing (moonbag) %" value={settings.moonbag_trailing_pct} onChange={set("moonbag_trailing_pct")} type="number" testid="setting-trailing" />
          <Field label="Stop Loss %" value={settings.stop_loss_pct} onChange={set("stop_loss_pct")} type="number" testid="setting-sl" />
        </div>
        <div className="px-4 pb-4">
          <button onClick={() => save()} data-testid="save-sell-rules" className="btn-neon-green flex items-center gap-2">
            <Save className="w-3.5 h-3.5" /> SAVE LADDER
          </button>
        </div>
      </div>

      {/* Risk limits */}
      <div className="terminal-panel">
        <div className="px-3 py-2 border-b border-[#1A1A24] font-mono text-[11px] uppercase tracking-widest flex items-center gap-2">
          <Shield className="w-3.5 h-3.5 text-neon-yellow" />
          <span className="text-neon-yellow">RISK LIMITS</span>
        </div>
        <div className="p-4 grid grid-cols-2 gap-3">
          <Field label="Max position % of bankroll" value={settings.max_position_pct} onChange={set("max_position_pct")} type="number" testid="setting-max-pos-pct" />
          <Field label="Max open positions" value={settings.max_open_positions} onChange={set("max_open_positions")} type="number" testid="setting-max-open" />
          <Field label="Daily loss limit %" value={settings.daily_loss_limit_pct} onChange={set("daily_loss_limit_pct")} type="number" testid="setting-daily-loss" />
          <Field label="Daily profit lock %" value={settings.daily_profit_lock_pct} onChange={set("daily_profit_lock_pct")} type="number" testid="setting-daily-profit" />
        </div>
        <div className="px-4 pb-4">
          <button onClick={() => save()} data-testid="save-risk-limits" className="btn-neon-green flex items-center gap-2">
            <Save className="w-3.5 h-3.5" /> SAVE LIMITS
          </button>
        </div>
      </div>

      {/* Trading defaults */}
      <div className="terminal-panel">
        <div className="px-3 py-2 border-b border-[#1A1A24] font-mono text-[11px] uppercase tracking-widest">
          Trading Defaults
        </div>
        <div className="p-4 space-y-4">
          <Field label="Default Slippage %" value={settings.default_slippage} onChange={set("default_slippage")} type="number" testid="setting-slippage" />
          <Field label="Priority Fee (SOL)" value={settings.priority_fee} onChange={set("priority_fee")} type="number" step="0.0001" testid="setting-priority-fee" />
          <Field label="RPC Endpoint" value={settings.rpc_endpoint} onChange={(v) => setSettings({ ...settings, rpc_endpoint: v })} testid="setting-rpc" />
          <label className="flex items-start justify-between gap-3 p-3 border border-[#1A1A24] bg-black/40 cursor-pointer">
            <div>
              <div className="font-mono text-[11px] uppercase tracking-widest text-white">Paper Trading Mode</div>
              <div className="font-mono text-[10px] text-[#5C5C6E] mt-0.5 max-w-sm">
                When ON, trades are simulated against a virtual bankroll. When OFF, requires a connected Phantom wallet for real on-chain execution.
              </div>
            </div>
            <input
              type="checkbox"
              checked={settings.paper_mode ?? true}
              onChange={(e) => save({ paper_mode: e.target.checked })}
              data-testid="setting-paper-mode"
              className="accent-neon-cyan mt-1"
            />
          </label>
          <button onClick={() => save()} data-testid="save-settings-button" className="btn-neon-green flex items-center gap-2">
            <Save className="w-3.5 h-3.5" /> SAVE
          </button>
        </div>
      </div>

      {/* Alert rules */}
      <div className="terminal-panel lg:col-span-2">
        <div className="px-3 py-2 border-b border-[#1A1A24] font-mono text-[11px] uppercase tracking-widest flex items-center gap-2">
          <Bell className="w-3.5 h-3.5 text-neon-yellow" /> Alert Rules
        </div>
        <form onSubmit={addAlert} className="p-3 flex gap-2 border-b border-[#1A1A24]">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="ALERT NAME"
            data-testid="alert-name-input"
            className="flex-1 bg-black border border-[#1A1A24] px-3 py-1.5 font-mono text-xs uppercase outline-none focus:border-neon-cyan"
          />
          <input type="number" value={scoreThr} onChange={(e) => setScoreThr(e.target.value)} data-testid="alert-score-input" className="w-20 bg-black border border-[#1A1A24] px-2 py-1.5 font-mono text-xs" min={0} max={100} />
          <button data-testid="create-alert-button" className="btn-neon-green flex items-center gap-1">
            <Plus className="w-3 h-3" />
          </button>
        </form>
        <div className="divide-y divide-[#1A1A24]">
          {alerts.length === 0 && (
            <div className="p-4 text-center font-mono text-[10px] uppercase tracking-widest text-[#5C5C6E]">
              No alerts configured
            </div>
          )}
          {alerts.map((a) => (
            <div key={a.id} className="p-3 flex items-center gap-3 hover:bg-[#14141A]" data-testid={`alert-row-${a.id}`}>
              <div className="flex-1">
                <div className="font-mono text-sm text-white">{a.name}</div>
                <div className="font-mono text-[10px] uppercase tracking-widest text-[#5C5C6E]">
                  {a.type} ≥ {a.score_threshold} · {(a.channels || []).join(" · ")}
                </div>
              </div>
              <span className="px-1.5 py-0.5 border border-neon-green text-neon-green font-mono text-[10px] uppercase">
                {a.enabled ? "ON" : "OFF"}
              </span>
              <button onClick={() => removeAlert(a.id)} className="text-[#5C5C6E] hover:text-neon-red" data-testid={`remove-alert-${a.id}`}>
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function Field({ label, value, onChange, type = "text", step, testid }) {
  return (
    <label className="block">
      <span className="font-mono text-[10px] uppercase tracking-widest text-[#5C5C6E]">{label}</span>
      <input
        type={type}
        step={step}
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value)}
        data-testid={testid}
        className="w-full bg-black border border-[#1A1A24] px-3 py-2 font-mono text-sm mt-1 outline-none focus:border-neon-cyan"
      />
    </label>
  );
}
