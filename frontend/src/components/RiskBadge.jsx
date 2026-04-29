import React from "react";
import { riskColor } from "@/lib/format";

const LABELS = {
  safe: "SAFE",
  risky: "RISKY",
  danger: "DANGER",
  rug: "RUG",
};

const ICONS = {
  safe: "●",
  risky: "▲",
  danger: "■",
  rug: "✕",
};

export default function RiskBadge({ risk = "safe", className = "" }) {
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 border rounded-sm font-mono text-[10px] uppercase tracking-widest ${riskColor(
        risk
      )} ${className}`}
      data-testid={`risk-badge-${risk}`}
    >
      <span aria-hidden>{ICONS[risk] || "●"}</span>
      {LABELS[risk] || risk}
    </span>
  );
}
