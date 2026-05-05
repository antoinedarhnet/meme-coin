"""
Scoring for New Pairs (0-100).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class ScoreResult:
    score: int
    breakdown: Dict[str, Any]


def compute_new_pairs_score(metrics: Dict[str, Any]) -> ScoreResult:
    """
    Metrics expected (best-effort):
    - buy_velocity (tx/min first 30s)
    - holders_diversity (0-1)
    - vol_liq_ratio (ratio)
    - bonding_curve_progress (0-1)
    - smart_money_hits (int)
    - social_buzz (int, mentions)
    """
    breakdown: Dict[str, Any] = {}
    total = 0

    # +30 velocity
    velocity = metrics.get("buy_velocity") or 0
    vel_score = 0
    if velocity >= 60:
        vel_score = 30
    elif velocity >= 40:
        vel_score = 24
    elif velocity >= 25:
        vel_score = 18
    elif velocity >= 15:
        vel_score = 12
    elif velocity >= 8:
        vel_score = 6
    breakdown["velocity"] = {"value": velocity, "score": vel_score, "max": 30}
    total += vel_score

    # +20 holders diversity
    diversity = metrics.get("holders_diversity") or 0
    div_score = 0
    if diversity >= 0.8:
        div_score = 20
    elif diversity >= 0.6:
        div_score = 16
    elif diversity >= 0.45:
        div_score = 12
    elif diversity >= 0.3:
        div_score = 7
    breakdown["holders_diversity"] = {"value": diversity, "score": div_score, "max": 20}
    total += div_score

    # +15 volume / liquidity ratio
    ratio = metrics.get("vol_liq_ratio") or 0
    ratio_score = 0
    if 0.5 <= ratio <= 3:
        ratio_score = 15
    elif 0.3 <= ratio < 0.5 or 3 < ratio <= 5:
        ratio_score = 8
    elif ratio > 0:
        ratio_score = 4
    breakdown["vol_liq_ratio"] = {"value": ratio, "score": ratio_score, "max": 15}
    total += ratio_score

    # +15 bonding curve progress
    curve = metrics.get("bonding_curve_progress") or 0
    curve_score = 0
    if curve >= 0.8:
        curve_score = 15
    elif curve >= 0.6:
        curve_score = 12
    elif curve >= 0.5:
        curve_score = 8
    elif curve >= 0.35:
        curve_score = 4
    breakdown["bonding_curve_progress"] = {"value": curve, "score": curve_score, "max": 15}
    total += curve_score

    # +10 smart money
    smart = metrics.get("smart_money_hits") or 0
    smart_score = 0
    if smart >= 3:
        smart_score = 10
    elif smart >= 1:
        smart_score = 6
    breakdown["smart_money"] = {"value": smart, "score": smart_score, "max": 10}
    total += smart_score

    # +10 social buzz
    buzz = metrics.get("social_buzz") or 0
    buzz_score = 0
    if buzz >= 20:
        buzz_score = 10
    elif buzz >= 8:
        buzz_score = 6
    elif buzz >= 3:
        buzz_score = 3
    breakdown["social_buzz"] = {"value": buzz, "score": buzz_score, "max": 10}
    total += buzz_score

    total = max(0, min(100, int(total)))
    return ScoreResult(score=total, breakdown=breakdown)
