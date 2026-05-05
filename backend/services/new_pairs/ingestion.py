"""
New Pairs ingestion pipeline.
- Aggregates multiple sources in parallel.
- Normalizes output into a common schema.
- No filtering/scoring here (handled later).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional
import asyncio
import httpx
import logging
import os

DEXSCREENER_BASE = "https://api.dexscreener.com"
BIRDEYE_PUBLIC_NEW_LISTING = "https://public-api.birdeye.so/defi/v2/tokens/new_listing"
PUMPFUN_FRONTEND_NEW = "https://frontend-api.pump.fun/coins?offset=0&limit=50&sort=created_timestamp"

FALLBACK_MAX_AGE_HOURS = int(os.environ.get("NEW_PAIRS_FALLBACK_MAX_HOURS", "24"))
FALLBACK_MAX_AGE_MS = FALLBACK_MAX_AGE_HOURS * 60 * 60 * 1000

logger = logging.getLogger("sniping.new_pairs")


@dataclass
class NewPairCandidate:
    source: str
    token_address: str
    pair_address: Optional[str]
    symbol: Optional[str]
    name: Optional[str]
    created_at_ms: Optional[int]
    dex: Optional[str]
    price_usd: Optional[float]
    liquidity_usd: Optional[float]
    volume_5m: Optional[float]
    buys_5m: Optional[int]
    sells_5m: Optional[int]
    raw: Dict[str, Any]

    @property
    def age_minutes(self) -> Optional[float]:
        if not self.created_at_ms:
            return None
        return max(0.0, (now_ms() - self.created_at_ms) / 60000.0)


class NewPairsIngestor:
    def __init__(self, http_client: Optional[httpx.AsyncClient] = None):
        self._http = http_client or httpx.AsyncClient(timeout=15.0)
        # Unified buffer (token_address -> candidate)
        self._buffer: Dict[str, NewPairCandidate] = {}
        # Stats
        self._last_webhook_ms: Optional[int] = None
        self._webhook_received: int = 0
        self._last_fallback_poll_ms: Optional[int] = None
        self._fallback_received: int = 0
        self._fallback_last_response_count: int = 0
        self._fallback_last_after_age: int = 0
        self._fallback_last_pushed: int = 0

    async def close(self) -> None:
        await self._http.aclose()

    # ---------- Public API ----------
    async def fetch_all(self, sources: Dict[str, bool]) -> List[NewPairCandidate]:
        logger.info(f"[FETCH_ALL] Starting with sources={sources}, buffer_size={len(self._buffer)}")
        tasks = []
        if sources.get("dexscreener"):
            logger.debug("[FETCH_ALL] Adding dexscreener latest profiles task")
            tasks.append(self._from_dexscreener_latest_profiles())
        if sources.get("raydium"):
            logger.debug("[FETCH_ALL] Adding raydium task")
            tasks.append(self._from_raydium())
        if sources.get("pumpfun"):
            logger.debug("[FETCH_ALL] Adding pumpfun buffer task")
            tasks.append(self._from_buffer())
        # Always include buffer (fallback/webhook)
        logger.debug("[FETCH_ALL] Adding buffer task")
        tasks.append(self._from_buffer())

        if not tasks:
            logger.warning("[FETCH_ALL] No tasks to execute!")
            return []

        results = await asyncio.gather(*tasks, return_exceptions=True)
        candidates: List[NewPairCandidate] = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                logger.error(f"[FETCH_ALL] Task {i} failed: {r}")
                continue
            logger.debug(f"[FETCH_ALL] Task {i} returned {len(r) if isinstance(r, list) else 'error'} candidates")
            candidates.extend(r)
        
        deduped = dedupe_by_token(candidates)
        logger.info(f"[FETCH_ALL] Collected {len(candidates)} candidates, {len(deduped)} after dedup")
        return deduped

    def ingest_pumpfun_webhook(self, payload: Dict[str, Any]) -> None:
        """
        Accept Pump.fun detection via Helius webhook.
        Expected payload varies by Helius config; we only extract mint/token address.
        """
        addr = extract_mint_from_helius(payload)
        if not addr:
            return
        ts = now_ms()
        cand = NewPairCandidate(
            source="pumpfun",
            token_address=addr,
            pair_address=None,
            symbol=None,
            name=None,
            created_at_ms=ts,
            dex=None,
            price_usd=None,
            liquidity_usd=None,
            volume_5m=None,
            buys_5m=None,
            sells_5m=None,
            raw={"mint": addr, "ts": ts},
        )
        self._buffer[addr] = cand
        self._last_webhook_ms = ts
        self._webhook_received += 1

    def get_stats(self) -> Dict[str, Any]:
        return {
            "webhook_received": self._webhook_received,
            "last_webhook_ms": self._last_webhook_ms,
            "buffer_size": len(self._buffer),
            "fallback_received": self._fallback_received,
            "last_fallback_poll_ms": self._last_fallback_poll_ms,
            "fallback_last_response_count": self._fallback_last_response_count,
            "fallback_last_after_age": self._fallback_last_after_age,
            "fallback_last_pushed": self._fallback_last_pushed,
        }

    def get_buffer_sample(self, n: int = 5) -> List[Dict[str, Any]]:
        items = list(self._buffer.values())[:n]
        return [
            {
                "source": i.source,
                "token_address": i.token_address,
                "created_at_ms": i.created_at_ms,
                "raw": i.raw,
            }
            for i in items
        ]

    def webhook_stale(self, threshold_ms: int) -> bool:
        if not self._last_webhook_ms:
            return True
        return (now_ms() - self._last_webhook_ms) > threshold_ms

    async def fallback_poll_loop(self) -> None:
        """
        Every 10s, if no webhook in 30s, poll DexScreener search and buffer fresh pairs.
        """
        logger.info("[FALLBACK LOOP] Starting fallback_poll_loop")
        await asyncio.sleep(2)  # Let the app boot
        while True:
            try:
                webhook_ok = not self.webhook_stale(30_000)
                if webhook_ok:
                    logger.debug("[FALLBACK LOOP] Webhook is fresh, skipping fallback")
                else:
                    logger.info("[FALLBACK LOOP] No webhook in 30s, polling sources...")
                    await self._poll_dexscreener_search()
                    await self._poll_birdeye_new_listing()
                    await self._poll_pumpfun_frontend()
                    logger.info(f"[FALLBACK LOOP] Buffer now has {len(self._buffer)} candidates")
            except Exception as e:
                logger.error(f"[FALLBACK LOOP] error: {e}", exc_info=True)
            await asyncio.sleep(10)

    # ---------- Sources ----------
    async def _from_buffer(self) -> List[NewPairCandidate]:
        cutoff_ms = now_ms() - FALLBACK_MAX_AGE_MS
        before = len(self._buffer)
        fresh = {k: v for k, v in self._buffer.items() if (v.created_at_ms or 0) >= cutoff_ms}
        self._buffer = fresh
        after = len(fresh)
        logger.debug(f"[FROM_BUFFER] Before cleanup: {before}, After (fresh): {after}, Cutoff: {FALLBACK_MAX_AGE_HOURS}h")
        return list(fresh.values())

    async def _from_raydium(self) -> List[NewPairCandidate]:
        """
        Placeholder for Raydium new pools ingestion.
        We'll wire this once we confirm the preferred Raydium endpoint.
        """
        return []

    async def _from_dexscreener_latest_profiles(self) -> List[NewPairCandidate]:
        """
        DexScreener latest token profiles -> tokens/v1/solana batch.
        This gives us very fresh pairs and price/liquidity/txns metrics.
        """
        try:
            profiles = await http_get(self._http, f"{DEXSCREENER_BASE}/token-profiles/latest/v1")
        except Exception:
            return []
        addresses: List[str] = []
        if isinstance(profiles, list):
            for it in profiles:
                if it.get("chainId") == "solana" and it.get("tokenAddress"):
                    addresses.append(it["tokenAddress"])
        addresses = dedupe(addresses)[:60]
        if not addresses:
            return []

        out: List[NewPairCandidate] = []
        for i in range(0, len(addresses), 30):
            batch = addresses[i : i + 30]
            try:
                data = await http_get(self._http, f"{DEXSCREENER_BASE}/tokens/v1/solana/{','.join(batch)}")
            except Exception:
                continue
            if not isinstance(data, list):
                continue
            for p in data:
                base = p.get("baseToken") or {}
                created = p.get("pairCreatedAt") or None
                tx5 = (p.get("txns") or {}).get("m5") or {}
                out.append(NewPairCandidate(
                    source="dexscreener",
                    token_address=base.get("address") or "",
                    pair_address=p.get("pairAddress"),
                    symbol=base.get("symbol"),
                    name=base.get("name"),
                    created_at_ms=created,
                    dex=p.get("dexId"),
                    price_usd=float(p["priceUsd"]) if p.get("priceUsd") else None,
                    liquidity_usd=(p.get("liquidity") or {}).get("usd"),
                    volume_5m=(p.get("volume") or {}).get("m5"),
                    buys_5m=tx5.get("buys"),
                    sells_5m=tx5.get("sells"),
                    raw=p,
                ))
        return out

    async def _poll_dexscreener_search(self) -> None:
        """
        Poll DexScreener search endpoint and buffer pairs created < 24h (debug).
        """
        logger.info("[FALLBACK] === Polling DexScreener search ===")
        try:
            url = f"{DEXSCREENER_BASE}/latest/dex/search"
            params = {"q": "SOL"}
            logger.debug(f"[FALLBACK] GET {url} params={params}")
            data = await http_get(self._http, url, params=params)
            logger.debug(f"[FALLBACK] Response type: {type(data)}, keys: {data.keys() if isinstance(data, dict) else 'N/A'}")
        except Exception as e:
            logger.error(f"[FALLBACK] DexScreener fetch failed: {e}", exc_info=True)
            return
        
        pairs = (data or {}).get("pairs") or []
        logger.info(f"[FALLBACK] Got {len(pairs)} pairs from API")
        
        if not pairs:
            logger.warning("[FALLBACK] No pairs returned from DexScreener!")
            return
            
        cutoff_ms = now_ms() - FALLBACK_MAX_AGE_MS
        added = 0
        after_age = 0
        rejected_reasons = {}
        
        for i, p in enumerate(pairs):
            if p.get("chainId") != "solana":
                rejected_reasons["not_solana"] = rejected_reasons.get("not_solana", 0) + 1
                continue
            created = p.get("pairCreatedAt")
            if not created:
                rejected_reasons["no_creation_time"] = rejected_reasons.get("no_creation_time", 0) + 1
                continue
            if created < cutoff_ms:
                rejected_reasons["too_old"] = rejected_reasons.get("too_old", 0) + 1
                continue
            
            after_age += 1
            base = p.get("baseToken") or {}
            tx5 = (p.get("txns") or {}).get("m5") or {}
            token_addr = base.get("address") or ""
            
            if not token_addr:
                logger.debug(f"[FALLBACK] Pair {i} has no base token address, skipping")
                continue
                
            cand = NewPairCandidate(
                source="dexscreener_search",
                token_address=token_addr,
                pair_address=p.get("pairAddress"),
                symbol=base.get("symbol"),
                name=base.get("name"),
                created_at_ms=created,
                dex=p.get("dexId"),
                price_usd=float(p["priceUsd"]) if p.get("priceUsd") else None,
                liquidity_usd=(p.get("liquidity") or {}).get("usd"),
                volume_5m=(p.get("volume") or {}).get("m5"),
                buys_5m=tx5.get("buys"),
                sells_5m=tx5.get("sells"),
                raw=p,
            )
            self._buffer[token_addr] = cand
            added += 1
            logger.debug(f"[FALLBACK] Buffered {cand.symbol}/{token_addr} age={cand.age_minutes:.1f}min liq={cand.liquidity_usd}")
        
        logger.info(f"[FALLBACK] After age filter: {after_age} pairs pass age check")
        logger.info(f"[FALLBACK] Rejection reasons: {rejected_reasons}")
        logger.info(f"[FALLBACK] Pushed {added} to buffer")
        self._fallback_last_response_count = len(pairs)
        self._fallback_last_after_age = after_age
        self._fallback_last_pushed = added
        self._fallback_received += added
        self._last_fallback_poll_ms = now_ms()

    async def _poll_birdeye_new_listing(self) -> None:
        logger.info("[FALLBACK] === Polling Birdeye new listing ===")
        try:
            url = BIRDEYE_PUBLIC_NEW_LISTING
            logger.debug(f"[FALLBACK] GET {url}")
            data = await http_get(self._http, url)
            logger.debug(f"[FALLBACK] Response type: {type(data)}, keys: {data.keys() if isinstance(data, dict) else 'N/A'}")
        except Exception as e:
            logger.warning(f"[FALLBACK] Birdeye fetch failed: {e}", exc_info=True)
            return
        
        items = (data or {}).get("data") or (data or {}).get("items") or []
        if isinstance(items, dict):
            items = items.get("items") or []
        logger.info(f"[FALLBACK] Got {len(items) if isinstance(items, list) else 0} items from Birdeye")
        
        if not isinstance(items, list):
            logger.warning(f"[FALLBACK] Items is not a list: {type(items)}")
            return
            
        pushed = 0
        for i, it in enumerate(items):
            addr = it.get("address") or it.get("mint") or it.get("tokenAddress")
            if not addr:
                logger.debug(f"[FALLBACK] Birdeye item {i} has no address, skipping")
                continue
            created = it.get("createdAt") or it.get("created_at") or it.get("createdTime")
            created_ms = None
            if isinstance(created, (int, float)):
                created_ms = int(created if created > 1e12 else created * 1000)
            cand = NewPairCandidate(
                source="birdeye",
                token_address=addr,
                pair_address=None,
                symbol=it.get("symbol"),
                name=it.get("name"),
                created_at_ms=created_ms,
                dex=None,
                price_usd=it.get("price"),
                liquidity_usd=None,
                volume_5m=None,
                buys_5m=None,
                sells_5m=None,
                raw=it,
            )
            self._buffer[addr] = cand
            pushed += 1
            logger.debug(f"[FALLBACK] Buffered Birdeye {cand.symbol}/{addr}")
        logger.info(f"[FALLBACK] Birdeye pushed {pushed} to buffer")

    async def _poll_pumpfun_frontend(self) -> None:
        logger.info("[FALLBACK] === Polling Pump.fun frontend ===")
        try:
            url = PUMPFUN_FRONTEND_NEW
            logger.debug(f"[FALLBACK] GET {url}")
            data = await http_get(self._http, url)
            logger.debug(f"[FALLBACK] Response type: {type(data)}, keys: {data.keys() if isinstance(data, dict) else 'N/A'}")
        except Exception as e:
            logger.warning(f"[FALLBACK] Pump.fun fetch failed: {e}", exc_info=True)
            return
            
        items = data.get("coins") if isinstance(data, dict) else data
        if not isinstance(items, list):
            logger.warning(f"[FALLBACK] Items is not a list: {type(items)}")
            return
        logger.info(f"[FALLBACK] Got {len(items)} coins from Pump.fun")
        
        pushed = 0
        for i, it in enumerate(items):
            addr = it.get("mint") or it.get("address")
            if not addr:
                logger.debug(f"[FALLBACK] Pump.fun item {i} has no mint, skipping")
                continue
            created = it.get("created_timestamp") or it.get("createdAt")
            created_ms = None
            if isinstance(created, (int, float)):
                created_ms = int(created if created > 1e12 else created * 1000)
            cand = NewPairCandidate(
                source="pumpfun_frontend",
                token_address=addr,
                pair_address=None,
                symbol=it.get("symbol"),
                name=it.get("name"),
                created_at_ms=created_ms,
                dex="pumpfun",
                price_usd=None,
                liquidity_usd=None,
                volume_5m=None,
                buys_5m=None,
                sells_5m=None,
                raw=it,
            )
            self._buffer[addr] = cand
            pushed += 1
            logger.debug(f"[FALLBACK] Buffered Pump.fun {cand.symbol}/{addr}")
        logger.info(f"[FALLBACK] Pump.fun pushed {pushed} to buffer")


# ---------- Helpers ----------
async def http_get(client: httpx.AsyncClient, url: str, params: Optional[Dict[str, Any]] = None) -> Any:
    r = await client.get(url, params=params, headers={"Accept": "application/json"})
    r.raise_for_status()
    return r.json()


def now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def dedupe(items: Iterable[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for x in items:
        if x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out


def dedupe_by_token(items: Iterable[NewPairCandidate]) -> List[NewPairCandidate]:
    seen = set()
    out: List[NewPairCandidate] = []
    for it in items:
        key = it.token_address
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out


def extract_mint_from_helius(payload: Dict[str, Any]) -> Optional[str]:
    """
    Best-effort extraction for Helius webhook payloads.
    We look for common fields like 'mint', 'tokenMint', or tokenTransfers.mint.
    """
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                addr = extract_mint_from_helius(item)
                if addr:
                    return addr
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("mint"):
        return payload.get("mint")
    if payload.get("tokenMint"):
        return payload.get("tokenMint")
    meta = payload.get("meta") or {}
    if isinstance(meta, dict) and meta.get("mint"):
        return meta.get("mint")
    transfers = payload.get("tokenTransfers") or []
    for t in transfers:
        if isinstance(t, dict) and t.get("mint"):
            return t.get("mint")
    return None
