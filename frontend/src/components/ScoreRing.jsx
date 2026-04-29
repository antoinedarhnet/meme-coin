import React from "react";

export default function ScoreRing({ score = 0, size = 56, stroke = 4, label }) {
  const radius = (size - stroke) / 2;
  const circ = 2 * Math.PI * radius;
  const offset = circ - (score / 100) * circ;
  let color = "#FF3366";
  if (score >= 75) color = "#B026FF";
  else if (score >= 55) color = "#00E5FF";
  else if (score >= 35) color = "#FFD600";

  return (
    <div className="relative inline-flex items-center justify-center" data-testid={label || "score-ring"}>
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke="#1A1A24"
          strokeWidth={stroke}
          fill="transparent"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke={color}
          strokeWidth={stroke}
          fill="transparent"
          strokeDasharray={circ}
          strokeDashoffset={offset}
          strokeLinecap="round"
          style={{ transition: "stroke-dashoffset 600ms ease, stroke 300ms" }}
          filter={`drop-shadow(0 0 4px ${color})`}
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center font-mono text-xs font-bold" style={{ color }}>
        {Math.round(score)}
      </div>
    </div>
  );
}
