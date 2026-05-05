"""
Anti-rug filters for New Pairs.
All checks must pass for a token to be eligible.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional
import httpx
import logging
import os

RUGCHECK_BASE = "https://api.rugcheck.xyz"
DEBUG_FILTERS = os.environ.get("DEBUG_FILTERS", "false").lower() in {"1", "true", "yes", "on"}
logger = logging.getLogger("sniping.new_pairs.filters")


@dataclass
class FilterResult:
    ok: bool
    reason: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


async def fetch_rugcheck_report(token_address: str) -> Dict[str, Any]:
    url = f"{RUGCHECK_BASE}/v1/tokens/{token_address}/report"
    async with httpx.AsyncClient(timeout=15.0) as h:
        r = await h.get(url, headers={"Accept": "application/json"})
        r.raise_for_status()
        return r.json()


def check_security(report: Dict[str, Any]) -> FilterResult:
    """
    Security checks based on RugCheck report.
    Expected keys may vary; treat missing fields as failure.
    """
    token = report.get("token") or {}
    mint_auth = report.get("mintAuthority") or token.get("mintAuthority")
    freeze_auth = report.get("freezeAuthority") or token.get("freezeAuthority")
    mint_revoked = report.get("mintAuthorityRevoked")
    freeze_revoked = report.get("freezeAuthorityRevoked")
    if mint_revoked is None:
        mint_revoked = mint_auth is None
    if freeze_revoked is None:
        freeze_revoked = freeze_auth is None

    liq_locked = (
        report.get("liquidityLocked")
        or report.get("liquidityBurned")
        or report.get("lpLocked")
        or (report.get("lpLockedPct") or 0) > 0
    )

    honeypot = report.get("honeypot")
    if honeypot is None:
        risks = report.get("risks") or []
        for r in risks:
            name = (r.get("name") or "").lower()
            desc = (r.get("description") or "").lower()
            if "honeypot" in name or "honeypot" in desc:
                honeypot = True
                break

    if DEBUG_FILTERS:
        logger.warning(f"[DEBUG_FILTERS] mint_revoked={mint_revoked} freeze_revoked={freeze_revoked} liq_locked={liq_locked} honeypot={honeypot}")

    if mint_revoked is not True:
        reason = "mint authority not revoked"
        if DEBUG_FILTERS:
            logger.warning(f"[DEBUG_FILTERS] WARN: {reason}")
            return FilterResult(True)
        return FilterResult(False, reason)
    if freeze_revoked is not True:
        reason = "freeze authority not revoked"
        if DEBUG_FILTERS:
            logger.warning(f"[DEBUG_FILTERS] WARN: {reason}")
            return FilterResult(True)
        return FilterResult(False, reason)
    if liq_locked is not True:
        reason = "liquidity not locked/burned"
        if DEBUG_FILTERS:
            logger.warning(f"[DEBUG_FILTERS] WARN: {reason}")
            return FilterResult(True)
        return FilterResult(False, reason)
    if honeypot is True:
        reason = "honeypot detected"
        if DEBUG_FILTERS:
            logger.warning(f"[DEBUG_FILTERS] WARN: {reason}")
            return FilterResult(True)
        return FilterResult(False, reason)

    return FilterResult(True)


def check_distribution(report: Dict[str, Any]) -> FilterResult:
    """
    Distribution checks using RugCheck report fields.
    Expected (best-effort): topHolders, devWalletPct, holdersCount.
    """
    top10_pct = report.get("topHoldersPct")
    holders = report.get("holdersCount") or report.get("holderCount") or report.get("totalHolders")
    dev_pct = report.get("devWalletPct")

    top_holders = report.get("topHolders") or []
    if top10_pct is None and isinstance(top_holders, list) and top_holders:
        top10_pct = sum((h.get("percentage") or h.get("pct") or 0) for h in top_holders[:10])

    if dev_pct is None and isinstance(top_holders, list):
        dev_pct = sum(
            (h.get("percentage") or h.get("pct") or 0)
            for h in top_holders
            if (h.get("isInsider") is True)
            or ("dev" in (h.get("label") or "").lower())
            or ("creator" in (h.get("label") or "").lower())
        )

    if holders is None:
        holders_list = report.get("holders")
        if isinstance(holders_list, list):
            holders = len(holders_list)
    if isinstance(holders, list):
        holders = len(holders)

    if DEBUG_FILTERS:
        logger.warning(f"[DEBUG_FILTERS] top10_pct={top10_pct} dev_pct={dev_pct} holders={holders}")

    if top10_pct is None or top10_pct >= 70:
        reason = "top 10 holders >= 70%"
        if DEBUG_FILTERS:
            logger.warning(f"[DEBUG_FILTERS] WARN: {reason} (value={top10_pct})")
            return FilterResult(True)
        return FilterResult(False, reason)
    if dev_pct is None or dev_pct >= 15:
        reason = "dev wallet >= 15%"
        if DEBUG_FILTERS:
            logger.warning(f"[DEBUG_FILTERS] WARN: {reason} (value={dev_pct})")
            return FilterResult(True)
        return FilterResult(False, reason)
    if holders is None or holders < 25:
        reason = "holders < 25"
        if DEBUG_FILTERS:
            logger.warning(f"[DEBUG_FILTERS] WARN: {reason} (value={holders})")
            return FilterResult(True)
        return FilterResult(False, reason)

    return FilterResult(True)


def check_liquidity_volume(metrics: Dict[str, Any]) -> FilterResult:
    """
    Liquidity & volume checks from market data.
    Requires: liquidity_sol, volume_5m_sol, txns_5m, buy_sell_ratio.
    """
    liq = metrics.get("liquidity_sol")
    vol5 = metrics.get("volume_5m_sol")
    tx5 = metrics.get("txns_5m")
    bs = metrics.get("buy_sell_ratio")

    if DEBUG_FILTERS:
        logger.warning(f"[DEBUG_FILTERS] liq={liq} vol5={vol5} tx5={tx5} bs={bs}")

    if liq is None or liq < 5:
        reason = "liquidity < 5 SOL"
        if DEBUG_FILTERS:
            logger.warning(f"[DEBUG_FILTERS] WARN: {reason} (value={liq})")
            return FilterResult(True)
        return FilterResult(False, reason)
    if vol5 is None or vol5 < 2:
        reason = "5m volume < 2 SOL"
        if DEBUG_FILTERS:
            logger.warning(f"[DEBUG_FILTERS] WARN: {reason} (value={vol5})")
            return FilterResult(True)
        return FilterResult(False, reason)
    if tx5 is None or tx5 < 15:
        reason = "< 15 txns in 5m"
        if DEBUG_FILTERS:
            logger.warning(f"[DEBUG_FILTERS] WARN: {reason} (value={tx5})")
            return FilterResult(True)
        return FilterResult(False, reason)
    if bs is None or bs <= 1.2:
        reason = "buy/sell ratio <= 1.2"
        if DEBUG_FILTERS:
            logger.warning(f"[DEBUG_FILTERS] WARN: {reason} (value={bs})")
            return FilterResult(True)
        return FilterResult(False, reason)

    return FilterResult(True)


def run_all_filters(report: Dict[str, Any], metrics: Dict[str, Any]) -> FilterResult:
    failures = []
    s = check_security(report)
    if not s.ok:
        failures.append(s.reason)
    d = check_distribution(report)
    if not d.ok:
        failures.append(d.reason)
    l = check_liquidity_volume(metrics)
    if not l.ok:
        failures.append(l.reason)

    if failures:
        if DEBUG_FILTERS:
            for reason in failures:
                logger.warning(f"[DEBUG_FILTERS] {reason}")
            return FilterResult(True, details={"failed": failures})
        return FilterResult(False, failures[0], details={"failed": failures})

    return FilterResult(True, details={})
