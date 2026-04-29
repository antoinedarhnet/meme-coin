export const fmtUsd = (n, opts = {}) => {
  if (n === null || n === undefined || isNaN(n)) return "—";
  const abs = Math.abs(n);
  const { compact = true } = opts;
  if (compact) {
    if (abs >= 1e9) return `$${(n / 1e9).toFixed(2)}B`;
    if (abs >= 1e6) return `$${(n / 1e6).toFixed(2)}M`;
    if (abs >= 1e3) return `$${(n / 1e3).toFixed(1)}K`;
    if (abs >= 1) return `$${n.toFixed(2)}`;
    if (abs >= 0.01) return `$${n.toFixed(4)}`;
    return `$${n.toExponential(2)}`;
  }
  return `$${n.toLocaleString(undefined, { maximumFractionDigits: 6 })}`;
};

export const fmtNum = (n) => {
  if (n === null || n === undefined || isNaN(n)) return "—";
  const abs = Math.abs(n);
  if (abs >= 1e9) return `${(n / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `${(n / 1e6).toFixed(2)}M`;
  if (abs >= 1e3) return `${(n / 1e3).toFixed(1)}K`;
  return `${n.toLocaleString()}`;
};

export const fmtPct = (n) => {
  if (n === null || n === undefined || isNaN(n)) return "—";
  const sign = n >= 0 ? "+" : "";
  return `${sign}${n.toFixed(2)}%`;
};

export const fmtAge = (minutes) => {
  if (minutes === null || minutes === undefined || isNaN(minutes)) return "—";
  if (minutes < 1) return "<1m";
  if (minutes < 60) return `${Math.round(minutes)}m`;
  const h = minutes / 60;
  if (h < 24) return `${h.toFixed(1)}h`;
  const d = h / 24;
  return `${d.toFixed(1)}d`;
};

export const shorten = (addr, n = 4) => {
  if (!addr) return "";
  return `${addr.slice(0, n)}…${addr.slice(-n)}`;
};

export const riskColor = (risk) => {
  switch (risk) {
    case "safe":
      return "text-neon-green border-neon-green/40 bg-neon-green/5";
    case "risky":
      return "text-neon-yellow border-neon-yellow/40 bg-neon-yellow/5";
    case "danger":
      return "text-neon-red border-neon-red/40 bg-neon-red/5";
    case "rug":
      return "text-neon-red border-neon-red bg-black";
    default:
      return "text-white/60 border-white/20";
  }
};

export const scoreColor = (score) => {
  if (score >= 75) return "text-neon-violet";
  if (score >= 55) return "text-neon-cyan";
  if (score >= 35) return "text-neon-yellow";
  return "text-neon-red";
};
