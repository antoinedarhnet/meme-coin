import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Bell, Save, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";

export default function SettingsPage() {
  const [settings, setSettings] = useState({
    default_slippage: 30,
    priority_fee: 0.001,
    tp_pct: 30,
    sl_pct: 15,
    sound_alerts: true,
    rpc_endpoint: "https://api.mainnet-beta.solana.com",
  });
  const [alerts, setAlerts] = useState([]);
  const [name, setName] = useState("");
  const [score, setScore] = useState(70);

  const load = async () => {
    const [s, a] = await Promise.all([api.settings(), api.alerts()]);
    setSettings(s);
    setAlerts(a.alerts || []);
  };

  useEffect(() => {
    load();
  }, []);

  const save = async () => {
    try {
      await api.saveSettings(settings);
      toast.success("Settings saved");
    } catch (e) {
      toast.error("Save failed");
    }
  };

  const addAlert = async (e) => {
    e.preventDefault();
    if (!name) return;
    try {
      await api.addAlert({ name, type: "score", score_threshold: Number(score), channels: ["browser"] });
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

  return (
    <div className="px-4 py-4 grid lg:grid-cols-2 gap-3">
      <div className="terminal-panel">
        <div className="px-3 py-2 border-b border-[#1A1A24] font-mono text-[11px] uppercase tracking-widest">
          Trading Defaults
        </div>
        <div className="p-4 space-y-4">
          <Field
            label="Default Slippage %"
            value={settings.default_slippage}
            onChange={(v) => setSettings({ ...settings, default_slippage: Number(v) })}
            type="number"
            testid="setting-slippage"
          />
          <Field
            label="Priority Fee (SOL)"
            value={settings.priority_fee}
            onChange={(v) => setSettings({ ...settings, priority_fee: Number(v) })}
            type="number"
            step="0.0001"
            testid="setting-priority-fee"
          />
          <div className="grid grid-cols-2 gap-3">
            <Field
              label="Take Profit %"
              value={settings.tp_pct}
              onChange={(v) => setSettings({ ...settings, tp_pct: Number(v) })}
              type="number"
              testid="setting-tp"
            />
            <Field
              label="Stop Loss %"
              value={settings.sl_pct}
              onChange={(v) => setSettings({ ...settings, sl_pct: Number(v) })}
              type="number"
              testid="setting-sl"
            />
          </div>
          <Field
            label="RPC Endpoint"
            value={settings.rpc_endpoint}
            onChange={(v) => setSettings({ ...settings, rpc_endpoint: v })}
            testid="setting-rpc"
          />
          <label className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-widest text-[#8A8A9E] cursor-pointer">
            <input
              type="checkbox"
              checked={settings.sound_alerts}
              onChange={(e) => setSettings({ ...settings, sound_alerts: e.target.checked })}
              data-testid="setting-sound"
              className="accent-neon-green"
            />
            Sound Alerts
          </label>
          <button
            onClick={save}
            data-testid="save-settings-button"
            className="btn-neon-green flex items-center gap-2"
          >
            <Save className="w-3.5 h-3.5" /> SAVE
          </button>
        </div>
      </div>

      <div className="terminal-panel">
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
          <input
            type="number"
            value={score}
            onChange={(e) => setScore(e.target.value)}
            data-testid="alert-score-input"
            className="w-20 bg-black border border-[#1A1A24] px-2 py-1.5 font-mono text-xs"
            min={0}
            max={100}
          />
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
            <div
              key={a.id}
              className="p-3 flex items-center gap-3 hover:bg-[#14141A]"
              data-testid={`alert-row-${a.id}`}
            >
              <div className="flex-1">
                <div className="font-mono text-sm text-white">{a.name}</div>
                <div className="font-mono text-[10px] uppercase tracking-widest text-[#5C5C6E]">
                  {a.type} ≥ {a.score_threshold} · {(a.channels || []).join(" · ")}
                </div>
              </div>
              <span className="px-1.5 py-0.5 border border-neon-green text-neon-green font-mono text-[10px] uppercase">
                {a.enabled ? "ON" : "OFF"}
              </span>
              <button
                onClick={() => removeAlert(a.id)}
                className="text-[#5C5C6E] hover:text-neon-red"
                data-testid={`remove-alert-${a.id}`}
              >
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
      <span className="font-mono text-[10px] uppercase tracking-widest text-[#5C5C6E]">
        {label}
      </span>
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
