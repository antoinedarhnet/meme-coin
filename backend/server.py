"""
Solana Memecoin Sniping Terminal - Backend
FastAPI + MongoDB + DexScreener public API integration
"""
from fastapi import FastAPI, APIRouter, HTTPException, Query
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone, timedelta
import httpx
import asyncio
import random
import math
import secrets
import base58
from services.new_pairs.ingestion import NewPairsIngestor
from services.new_pairs.filters import fetch_rugcheck_report, run_all_filters
from services.new_pairs.scoring import compute_new_pairs_score
try:
    import nacl.signing
    import nacl.exceptions
    _HAS_NACL = True
except ImportError:
    _HAS_NACL = False

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

app = FastAPI(title="Solana Sniping Terminal API")
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("sniping")
logger_new_pairs = logging.getLogger("sniping.new_pairs")

DEXSCREENER_BASE = "https://api.dexscreener.com"
HELIUS_WEBHOOKS_BASE = "https://api-mainnet.helius-rpc.com/v0/webhooks"
PUMPFUN_PROGRAM_ID = os.environ.get("PUMPFUN_PROGRAM_ID", "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P")
RAYDIUM_PROGRAM_IDS = os.environ.get(
    "RAYDIUM_PROGRAM_IDS",
    "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8,CPMMoo8L3F4NbTegBCKVN5Tq1Jp4vN1DwsVdX2bQ9M9",
).split(",")

# ---------- In-process cache ----------
_cache: Dict[str, Any] = {"pairs": {"data": [], "ts": 0}}
CACHE_TTL = 20  # seconds

# ---------- New Pairs ingestion ----------
_new_pairs_ingestor = NewPairsIngestor()
_new_pairs_stats: Dict[str, Any] = {
    "scanned": 0,
    "filtered": 0,
    "filtered_reasons": {},
    "passed_scoring": 0,
    "last_activity_at": None,
}
_new_pairs_rejections: List[Dict[str, Any]] = []


# ---------- Models ----------
class TokenScore(BaseModel):
    score: int
    grade: str  # A/B/C/D/F
    risk: str  # safe / risky / danger / rug
    breakdown: Dict[str, Any]


class LiveToken(BaseModel):
    chain: str = "solana"
    address: str
    pair_address: Optional[str] = None
    name: str
    symbol: str
    image: Optional[str] = None
    age_minutes: Optional[float] = None
    market_cap: Optional[float] = None
    liquidity_usd: Optional[float] = None
    price_usd: Optional[float] = None
    price_change_5m: Optional[float] = None
    price_change_1h: Optional[float] = None
    price_change_24h: Optional[float] = None
    volume_24h: Optional[float] = None
    volume_5m: Optional[float] = None
    txns_5m_buys: Optional[int] = None
    txns_5m_sells: Optional[int] = None
    txns_24h_buys: Optional[int] = None
    txns_24h_sells: Optional[int] = None
    fdv: Optional[float] = None
    dex: Optional[str] = None
    url: Optional[str] = None
    socials: List[Dict[str, str]] = []
    websites: List[Dict[str, str]] = []
    score: Optional[int] = None
    risk: Optional[str] = None


class KOL(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    handle: str
    name: str
    avatar: Optional[str] = None
    followers: int = 0
    win_rate: float = 0.0
    avg_roi: float = 0.0
    total_calls: int = 0
    last_call_at: Optional[str] = None
    notes: Optional[str] = None
    tier: str = "A"  # S/A/B/C
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class KOLCreate(BaseModel):
    handle: str
    name: Optional[str] = None
    notes: Optional[str] = None
    tier: Optional[str] = "A"


class Position(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    token_address: str
    symbol: str
    name: str
    image: Optional[str] = None
    entry_price: float
    amount_sol: float  # SOL originally invested
    tokens: float  # total tokens bought
    tokens_remaining: Optional[float] = None  # for tiered selling
    entry_market_cap: Optional[float] = None
    status: str = "open"  # open / closed
    exit_price: Optional[float] = None
    pnl_sol: Optional[float] = None
    pnl_pct: Optional[float] = None
    realized_pnl_sol: float = 0.0  # accumulated from partial sells
    tp_hits: List[str] = []  # ["tp1","tp2","tp3"]
    ath_price: Optional[float] = None  # for trailing stop
    source: str = "manual"  # manual | auto_snipe | copy_trade | kol_call
    opened_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    closed_at: Optional[str] = None


class TradeRequest(BaseModel):
    token_address: str
    symbol: str
    name: str
    image: Optional[str] = None
    price_usd: float
    market_cap: Optional[float] = None
    amount_sol: float
    slippage: float = 30.0
    source: str = "manual"


class CloseRequest(BaseModel):
    position_id: str
    exit_price_usd: float


class PartialCloseRequest(BaseModel):
    position_id: str
    sell_pct: float  # 1-100
    exit_price_usd: float
    tp_tag: Optional[str] = None  # "tp1","tp2","tp3","moonbag","sl","rug","manual"


class AlertRule(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    enabled: bool = True
    type: str = "score"  # score | kol | mc
    score_threshold: Optional[int] = 70
    channels: List[str] = ["browser"]  # browser, email, telegram, discord
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class AlertCreate(BaseModel):
    name: str
    type: str = "score"
    score_threshold: Optional[int] = 70
    channels: List[str] = ["browser"]


class Settings(BaseModel):
    default_slippage: float = 30.0
    priority_fee: float = 0.001
    tp_pct: float = 30.0
    sl_pct: float = 15.0
    sound_alerts: bool = True
    rpc_endpoint: str = "https://api.mainnet-beta.solana.com"
    # Paper trading toggle (hidden from UI banner, controls execution mode)
    paper_mode: bool = True  # true = simulation; false = on-chain (requires wallet)
    # Auto-Snipe engine
    auto_snipe_enabled: bool = False
    auto_snipe_amount_sol: float = 0.3
    auto_snipe_min_score: int = 75
    auto_snipe_min_liq_usd: float = 10000.0
    auto_snipe_max_age_min: float = 240.0  # only snipe tokens < 4h old
    auto_snipe_risks_blocked: List[str] = ["danger", "rug"]
    # Auto-Sell ladder
    auto_sell_enabled: bool = True
    tp1_pct: float = 50.0
    tp1_sell_pct: float = 25.0
    tp2_pct: float = 100.0
    tp2_sell_pct: float = 25.0
    tp3_pct: float = 200.0
    tp3_sell_pct: float = 25.0
    moonbag_trailing_pct: float = 30.0
    stop_loss_pct: float = 40.0
    rug_liq_drop_pct: float = 50.0
    # Risk limits
    max_position_pct: float = 2.0  # % of bankroll per snipe
    max_open_positions: int = 10
    daily_loss_limit_pct: float = 10.0  # -10% => auto-snipe OFF
    daily_profit_lock_pct: float = 30.0
    # ---------- New Pairs config ----------
    new_pairs_enabled: bool = False
    new_pairs_min_score: int = 80
    new_pairs_buy_size_sol: float = 0.1
    new_pairs_stop_loss_pct: float = 25.0
    new_pairs_max_simultaneous: int = 3
    # Sources toggles
    new_pairs_source_pumpfun: bool = True
    new_pairs_source_raydium: bool = True
    new_pairs_source_dexscreener: bool = True
    new_pairs_source_birdeye: bool = False


class Bankroll(BaseModel):
    initial_sol: float = 10.0
    balance_sol: float = 10.0
    realized_pnl_sol: float = 0.0
    day_start_balance_sol: float = 10.0
    day_start_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    auto_snipe_locked: bool = False  # set true when daily loss limit breached


class BankrollUpdate(BaseModel):
    initial_sol: float


class WalletNonceRequest(BaseModel):
    wallet_address: str


class WalletVerifyRequest(BaseModel):
    wallet_address: str
    nonce: str
    message: str
    signature: str  # base58 encoded


class TrackedWallet(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    address: str
    name: str
    emoji: Optional[str] = "👛"
    win_rate: float = 0.0
    total_trades: int = 0
    total_pnl_sol: float = 0.0
    last_activity_at: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class WalletCreate(BaseModel):
    address: str
    name: Optional[str] = None
    emoji: Optional[str] = "👛"


class WhaleActivity(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    wallet_address: str
    wallet_name: str
    token_address: str
    token_symbol: Optional[str] = None
    action: str  # "buy" | "sell"
    amount_sol: Optional[float] = None
    tokens: Optional[float] = None
    tx_signature: Optional[str] = None
    ts: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ---------- DexScreener service ----------
async def http_get(url: str, params: dict = None) -> Any:
    async with httpx.AsyncClient(timeout=15.0) as h:
        r = await h.get(url, params=params, headers={"Accept": "application/json"})
        r.raise_for_status()
        return r.json()


async def fetch_solana_pairs() -> List[Dict]:
    """Fetch a curated list of solana pairs by combining boosted tokens + token profiles."""
    now = datetime.now(timezone.utc).timestamp()
    if _cache["pairs"]["data"] and (now - _cache["pairs"]["ts"]) < CACHE_TTL:
        return _cache["pairs"]["data"]

    pairs: List[Dict] = []
    addresses: List[str] = []
    try:
        # Latest boosted tokens (most relevant for memecoin hunting)
        boosted = await http_get(f"{DEXSCREENER_BASE}/token-boosts/latest/v1")
        if isinstance(boosted, list):
            for it in boosted:
                if it.get("chainId") == "solana" and it.get("tokenAddress"):
                    addresses.append(it["tokenAddress"])
    except Exception as e:
        logger.warning(f"boosted fetch failed: {e}")

    try:
        top_boosted = await http_get(f"{DEXSCREENER_BASE}/token-boosts/top/v1")
        if isinstance(top_boosted, list):
            for it in top_boosted:
                if it.get("chainId") == "solana" and it.get("tokenAddress"):
                    addresses.append(it["tokenAddress"])
    except Exception as e:
        logger.warning(f"top boosted fetch failed: {e}")

    try:
        profiles = await http_get(f"{DEXSCREENER_BASE}/token-profiles/latest/v1")
        if isinstance(profiles, list):
            for it in profiles:
                if it.get("chainId") == "solana" and it.get("tokenAddress"):
                    addresses.append(it["tokenAddress"])
    except Exception as e:
        logger.warning(f"profiles fetch failed: {e}")

    # de-dup (keep order of insertion)
    seen = set()
    unique_addresses = []
    for a in addresses:
        if a not in seen:
            seen.add(a)
            unique_addresses.append(a)
    unique_addresses = unique_addresses[:60]

    # Batch fetch in groups of 30 (DexScreener supports up to 30 addresses)
    for i in range(0, len(unique_addresses), 30):
        batch = unique_addresses[i : i + 30]
        try:
            joined = ",".join(batch)
            data = await http_get(f"{DEXSCREENER_BASE}/tokens/v1/solana/{joined}")
            if isinstance(data, list):
                pairs.extend(data)
        except Exception as e:
            logger.warning(f"batch fetch failed: {e}")

    # Fallback search for trending memecoins to ensure data
    if len(pairs) < 5:
        try:
            search = await http_get(f"{DEXSCREENER_BASE}/latest/dex/search", params={"q": "SOL"})
            extra = (search or {}).get("pairs") or []
            pairs.extend([p for p in extra if p.get("chainId") == "solana"])
        except Exception as e:
            logger.warning(f"search fallback failed: {e}")

    _cache["pairs"] = {"data": pairs, "ts": now}
    return pairs


def compute_score(p: Dict) -> TokenScore:
    """Heuristic 0-100 scoring algorithm."""
    liq = (p.get("liquidity") or {}).get("usd") or 0.0
    vol_24h = (p.get("volume") or {}).get("h24") or 0.0
    vol_5m = (p.get("volume") or {}).get("m5") or 0.0
    tx5 = (p.get("txns") or {}).get("m5") or {}
    tx24 = (p.get("txns") or {}).get("h24") or {}
    buys_5m = tx5.get("buys") or 0
    sells_5m = tx5.get("sells") or 0
    buys_24h = tx24.get("buys") or 0
    sells_24h = tx24.get("sells") or 0
    pc5 = (p.get("priceChange") or {}).get("m5") or 0.0
    pc1h = (p.get("priceChange") or {}).get("h1") or 0.0
    pc24 = (p.get("priceChange") or {}).get("h24") or 0.0
    mc = p.get("marketCap") or p.get("fdv") or 0.0
    created_at = p.get("pairCreatedAt") or 0
    socials = (p.get("info") or {}).get("socials") or []
    websites = (p.get("info") or {}).get("websites") or []

    age_minutes = 0
    if created_at:
        age_minutes = max(0, (datetime.now(timezone.utc).timestamp() * 1000 - created_at) / 60000)

    breakdown: Dict[str, Any] = {}

    # Liquidity (max 25)
    liq_score = 0
    if liq >= 200_000:
        liq_score = 25
    elif liq >= 50_000:
        liq_score = 20
    elif liq >= 15_000:
        liq_score = 14
    elif liq >= 5_000:
        liq_score = 8
    else:
        liq_score = 2
    breakdown["liquidity"] = {"value": liq, "score": liq_score, "max": 25}

    # Volume / Liquidity ratio (max 15) - high turnover = active
    ratio = (vol_24h / liq) if liq > 0 else 0
    if ratio >= 5:
        vol_score = 15
    elif ratio >= 2:
        vol_score = 12
    elif ratio >= 1:
        vol_score = 9
    elif ratio >= 0.3:
        vol_score = 5
    else:
        vol_score = 1
    breakdown["volume_liquidity_ratio"] = {"value": round(ratio, 2), "score": vol_score, "max": 15}

    # Buy/Sell pressure 24h (max 15)
    total24 = buys_24h + sells_24h
    buy_ratio = (buys_24h / total24) if total24 else 0.5
    bs_score = int(round(min(15, max(0, (buy_ratio - 0.4) * 50))))
    breakdown["buy_sell_pressure"] = {"value": round(buy_ratio, 2), "score": bs_score, "max": 15}

    # Momentum (max 20)
    momentum = pc5 * 0.4 + pc1h * 0.3 + pc24 * 0.3
    if momentum >= 50:
        mo_score = 20
    elif momentum >= 20:
        mo_score = 15
    elif momentum >= 5:
        mo_score = 10
    elif momentum >= -5:
        mo_score = 5
    else:
        mo_score = 0
    breakdown["momentum"] = {"value": round(momentum, 2), "score": mo_score, "max": 20}

    # Activity / TPS proxy (max 10)
    tps = (buys_5m + sells_5m) / 300 if (buys_5m + sells_5m) else 0
    if tps >= 1:
        act_score = 10
    elif tps >= 0.3:
        act_score = 7
    elif tps >= 0.1:
        act_score = 4
    else:
        act_score = 1
    breakdown["transactions_per_sec"] = {"value": round(tps, 3), "score": act_score, "max": 10}

    # Social presence (max 10)
    soc = min(10, len(socials) * 3 + len(websites) * 2)
    breakdown["social_presence"] = {"value": len(socials) + len(websites), "score": soc, "max": 10}

    # Age sweet spot (max 5) — between 30min and 24h is hot
    if 30 <= age_minutes <= 1440:
        age_score = 5
    elif age_minutes < 30:
        age_score = 3
    elif age_minutes <= 4320:
        age_score = 4
    else:
        age_score = 2
    breakdown["age_score"] = {"value": round(age_minutes, 1), "score": age_score, "max": 5}

    total = liq_score + vol_score + bs_score + mo_score + act_score + soc + age_score
    total = max(0, min(100, int(total)))

    # Risk classification
    risk = "safe"
    if liq < 3000 or total24 == 0:
        risk = "rug"
    elif liq < 10_000 or buy_ratio < 0.35 or total < 30:
        risk = "danger"
    elif liq < 30_000 or total < 50:
        risk = "risky"

    # Grade
    if total >= 80:
        grade = "A"
    elif total >= 65:
        grade = "B"
    elif total >= 50:
        grade = "C"
    elif total >= 35:
        grade = "D"
    else:
        grade = "F"

    return TokenScore(score=total, grade=grade, risk=risk, breakdown=breakdown)


def pair_to_token(p: Dict) -> LiveToken:
    base = p.get("baseToken") or {}
    info = p.get("info") or {}
    created = p.get("pairCreatedAt") or 0
    age = None
    if created:
        age = max(0, (datetime.now(timezone.utc).timestamp() * 1000 - created) / 60000)
    sc = compute_score(p)
    return LiveToken(
        chain="solana",
        address=base.get("address") or "",
        pair_address=p.get("pairAddress"),
        name=base.get("name") or "Unknown",
        symbol=base.get("symbol") or "?",
        image=info.get("imageUrl"),
        age_minutes=age,
        market_cap=p.get("marketCap"),
        fdv=p.get("fdv"),
        liquidity_usd=(p.get("liquidity") or {}).get("usd"),
        price_usd=float(p["priceUsd"]) if p.get("priceUsd") else None,
        price_change_5m=(p.get("priceChange") or {}).get("m5"),
        price_change_1h=(p.get("priceChange") or {}).get("h1"),
        price_change_24h=(p.get("priceChange") or {}).get("h24"),
        volume_24h=(p.get("volume") or {}).get("h24"),
        volume_5m=(p.get("volume") or {}).get("m5"),
        txns_5m_buys=((p.get("txns") or {}).get("m5") or {}).get("buys"),
        txns_5m_sells=((p.get("txns") or {}).get("m5") or {}).get("sells"),
        txns_24h_buys=((p.get("txns") or {}).get("h24") or {}).get("buys"),
        txns_24h_sells=((p.get("txns") or {}).get("h24") or {}).get("sells"),
        dex=p.get("dexId"),
        url=p.get("url"),
        socials=info.get("socials") or [],
        websites=info.get("websites") or [],
        score=sc.score,
        risk=sc.risk,
    )


# ---------- Routes ----------
@api_router.get("/")
async def root():
    return {"name": "Solana Sniping Terminal API", "status": "online", "version": "1.0"}


@api_router.get("/tokens/live")
async def tokens_live(
    min_liq: float = Query(0),
    min_score: int = Query(0),
    risk: Optional[str] = Query(None),
    sort: str = Query("score"),  # score | age | volume | mc | change_24h
    limit: int = Query(50),
):
    pairs = await fetch_solana_pairs()
    tokens = [pair_to_token(p) for p in pairs if (p.get("baseToken") or {}).get("address")]

    # Filters
    tokens = [t for t in tokens if (t.liquidity_usd or 0) >= min_liq]
    tokens = [t for t in tokens if (t.score or 0) >= min_score]
    if risk:
        tokens = [t for t in tokens if t.risk == risk]

    # Sort
    if sort == "age":
        tokens.sort(key=lambda t: t.age_minutes or 999999)
    elif sort == "volume":
        tokens.sort(key=lambda t: t.volume_24h or 0, reverse=True)
    elif sort == "mc":
        tokens.sort(key=lambda t: t.market_cap or 0, reverse=True)
    elif sort == "change_24h":
        tokens.sort(key=lambda t: t.price_change_24h or 0, reverse=True)
    else:
        tokens.sort(key=lambda t: t.score or 0, reverse=True)

    return {"tokens": [t.model_dump() for t in tokens[:limit]], "count": len(tokens)}


@api_router.get("/tokens/{address}")
async def token_detail(address: str):
    try:
        data = await http_get(f"{DEXSCREENER_BASE}/tokens/v1/solana/{address}")
        if not data or not isinstance(data, list):
            raise HTTPException(404, "Token not found")
        # Choose pair with highest liquidity
        pair = max(data, key=lambda p: (p.get("liquidity") or {}).get("usd") or 0)
        token = pair_to_token(pair)
        score = compute_score(pair)
        return {
            "token": token.model_dump(),
            "score": score.model_dump(),
            "raw": pair,
            "all_pairs": data,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"token_detail error: {e}")
        raise HTTPException(500, "DexScreener fetch failed")


# ---------- KOL CRUD ----------
DEFAULT_KOLS = [
    {"handle": "@ansemtrades", "name": "Ansem", "followers": 568000, "win_rate": 64.0, "avg_roi": 285.0, "total_calls": 142, "tier": "S"},
    {"handle": "@cryptoshawn", "name": "Shawn", "followers": 142000, "win_rate": 58.0, "avg_roi": 178.0, "total_calls": 230, "tier": "A"},
    {"handle": "@mooncarl_eth", "name": "Mooncarl", "followers": 312000, "win_rate": 51.0, "avg_roi": 104.0, "total_calls": 88, "tier": "A"},
    {"handle": "@inversebrah", "name": "Inverse Brah", "followers": 478000, "win_rate": 47.0, "avg_roi": 67.0, "total_calls": 510, "tier": "A"},
    {"handle": "@gainzy222", "name": "Gainzy", "followers": 187000, "win_rate": 62.0, "avg_roi": 220.0, "total_calls": 76, "tier": "S"},
    {"handle": "@cryptokaleo", "name": "Kaleo", "followers": 522000, "win_rate": 55.0, "avg_roi": 145.0, "total_calls": 312, "tier": "A"},
]


async def seed_kols():
    count = await db.kols.count_documents({})
    if count == 0:
        docs = []
        for k in DEFAULT_KOLS:
            kol = KOL(**k, last_call_at=(datetime.now(timezone.utc) - timedelta(minutes=random.randint(2, 240))).isoformat())
            docs.append(kol.model_dump())
        await db.kols.insert_many(docs)


@api_router.get("/kols")
async def list_kols():
    await seed_kols()
    items = await db.kols.find({}, {"_id": 0}).to_list(500)
    items.sort(key=lambda k: k.get("avg_roi", 0), reverse=True)
    return {"kols": items}


@api_router.post("/kols")
async def add_kol(payload: KOLCreate):
    handle = payload.handle.strip()
    if not handle.startswith("@"):
        handle = "@" + handle
    existing = await db.kols.find_one({"handle": handle}, {"_id": 0})
    if existing:
        raise HTTPException(409, "KOL already tracked")
    kol = KOL(
        handle=handle,
        name=payload.name or handle.replace("@", "").title(),
        followers=random.randint(5_000, 250_000),
        win_rate=round(random.uniform(40, 65), 1),
        avg_roi=round(random.uniform(50, 250), 1),
        total_calls=random.randint(20, 400),
        tier=payload.tier or "B",
        notes=payload.notes,
        last_call_at=datetime.now(timezone.utc).isoformat(),
    )
    await db.kols.insert_one(kol.model_dump())
    return kol.model_dump()


@api_router.delete("/kols/{kol_id}")
async def remove_kol(kol_id: str):
    res = await db.kols.delete_one({"id": kol_id})
    if res.deleted_count == 0:
        raise HTTPException(404, "KOL not found")
    return {"ok": True}


@api_router.get("/kols/calls")
async def kol_calls():
    """Generate cross-call signals based on currently live tokens."""
    await seed_kols()
    pairs = await fetch_solana_pairs()
    tokens = [pair_to_token(p) for p in pairs if (p.get("baseToken") or {}).get("address")]
    tokens.sort(key=lambda t: t.score or 0, reverse=True)
    top = tokens[:10]

    kols = await db.kols.find({}, {"_id": 0}).to_list(500)
    if not kols or not top:
        return {"calls": [], "cross_calls": []}

    # Deterministic-ish but shuffled-by-minute mention generation
    random.seed(int(datetime.now(timezone.utc).timestamp() / 60))
    calls = []
    for t in top:
        n_callers = random.choice([1, 1, 2, 2, 3, 4])
        callers = random.sample(kols, min(n_callers, len(kols)))
        for c in callers:
            calls.append({
                "id": str(uuid.uuid4()),
                "kol_handle": c["handle"],
                "kol_name": c["name"],
                "kol_tier": c.get("tier", "A"),
                "kol_avg_roi": c.get("avg_roi", 0),
                "token_symbol": t.symbol,
                "token_name": t.name,
                "token_address": t.address,
                "token_image": t.image,
                "token_score": t.score,
                "token_risk": t.risk,
                "minutes_ago": random.randint(1, 180),
                "tweet_excerpt": random.choice([
                    f"${t.symbol} looking absurdly bullish here, this is the one",
                    f"aping ${t.symbol}. ngmi if you fade",
                    f"${t.symbol} chart is sending. dyor",
                    f"first time I post a CA in months. ${t.symbol}",
                    f"${t.symbol} has the cleanest setup I've seen this week",
                ]),
            })

    # Cross-calls = tokens called by 2+ KOLs in the last 3h
    by_token: Dict[str, List[Dict]] = {}
    for c in calls:
        if c["minutes_ago"] <= 180:
            by_token.setdefault(c["token_address"], []).append(c)
    cross = []
    for addr, cs in by_token.items():
        if len(cs) >= 2:
            t = next((x for x in top if x.address == addr), None)
            cross.append({
                "token_address": addr,
                "token_symbol": cs[0]["token_symbol"],
                "token_name": cs[0]["token_name"],
                "token_image": cs[0]["token_image"],
                "token_score": cs[0]["token_score"],
                "token_risk": cs[0]["token_risk"],
                "callers_count": len(cs),
                "callers": cs,
                "confidence": min(100, sum(c["kol_avg_roi"] for c in cs) / len(cs)),
            })
    cross.sort(key=lambda x: (x["callers_count"], x["confidence"]), reverse=True)
    return {"calls": calls, "cross_calls": cross}


# ---------- Narratives ----------
NARRATIVES = [
    {"key": "ai_agents", "name": "AI Agents", "icon": "Bot", "heat": 92, "tokens_count": 48, "vol_24h": 412_000_000, "tags": ["agent", "ai", "gpt", "neural"]},
    {"key": "animals", "name": "Animal Coins", "icon": "Cat", "heat": 81, "tokens_count": 130, "vol_24h": 218_000_000, "tags": ["dog", "cat", "frog", "monkey"]},
    {"key": "politifi", "name": "PolitiFi", "icon": "Vote", "heat": 67, "tokens_count": 22, "vol_24h": 89_000_000, "tags": ["trump", "election", "politics"]},
    {"key": "celebrity", "name": "Celebrity", "icon": "Star", "heat": 58, "tokens_count": 35, "vol_24h": 64_000_000, "tags": ["elon", "kanye", "celeb"]},
    {"key": "memes", "name": "Pure Memes", "icon": "Smile", "heat": 73, "tokens_count": 412, "vol_24h": 158_000_000, "tags": ["pepe", "wojak", "chad"]},
    {"key": "gaming", "name": "Gaming / GameFi", "icon": "Gamepad2", "heat": 49, "tokens_count": 28, "vol_24h": 41_000_000, "tags": ["game", "play", "rpg"]},
    {"key": "depin", "name": "DePIN", "icon": "Network", "heat": 44, "tokens_count": 18, "vol_24h": 32_000_000, "tags": ["depin", "infra"]},
    {"key": "rwa", "name": "RWA", "icon": "Building2", "heat": 38, "tokens_count": 14, "vol_24h": 22_000_000, "tags": ["rwa", "real"]},
]


@api_router.get("/narratives")
async def get_narratives():
    pairs = await fetch_solana_pairs()
    tokens = [pair_to_token(p) for p in pairs if (p.get("baseToken") or {}).get("address")]

    enriched = []
    for n in NARRATIVES:
        matched = []
        for t in tokens:
            text = f"{t.name} {t.symbol}".lower()
            if any(tag in text for tag in n["tags"]):
                matched.append(t.model_dump())
        matched.sort(key=lambda t: t.get("score") or 0, reverse=True)
        enriched.append({**n, "matched_tokens": matched[:6]})
    enriched.sort(key=lambda x: x["heat"], reverse=True)
    return {"narratives": enriched}


# ---------- Bankroll helpers ----------
SOL_PRICE_USD = 180.0  # paper sim reference; replace with real feed when going live


async def get_bankroll() -> Dict[str, Any]:
    doc = await db.bankroll.find_one({"_id": "global"})
    if not doc:
        bk = Bankroll().model_dump()
        await db.bankroll.insert_one({"_id": "global", **bk})
        return bk
    doc.pop("_id", None)
    # Daily reset check
    try:
        day_start = datetime.fromisoformat(doc["day_start_at"])
        now = datetime.now(timezone.utc)
        if (now.date() > day_start.date()):
            doc["day_start_balance_sol"] = doc["balance_sol"]
            doc["day_start_at"] = now.isoformat()
            doc["auto_snipe_locked"] = False
            await db.bankroll.update_one(
                {"_id": "global"},
                {"$set": {
                    "day_start_balance_sol": doc["day_start_balance_sol"],
                    "day_start_at": doc["day_start_at"],
                    "auto_snipe_locked": False,
                }},
            )
    except Exception:
        pass
    return doc


async def bankroll_adjust(delta_sol: float, realized_delta_sol: float = 0.0):
    """Apply a SOL delta to bankroll balance; optionally track realized pnl separately."""
    update: Dict[str, Any] = {"$inc": {"balance_sol": delta_sol}}
    if realized_delta_sol:
        update["$inc"]["realized_pnl_sol"] = realized_delta_sol
    await db.bankroll.update_one({"_id": "global"}, update, upsert=False)


async def check_risk_limits(amount_sol: float) -> Optional[str]:
    """Return error message if a new buy would violate risk limits, else None."""
    settings_doc = await db.settings.find_one({"_id": "global"}) or {}
    bk = await get_bankroll()
    if bk.get("auto_snipe_locked"):
        return "daily loss limit reached — bankroll locked until UTC midnight"
    if bk["balance_sol"] < amount_sol:
        return f"insufficient bankroll ({bk['balance_sol']:.3f} SOL available)"
    max_pct = settings_doc.get("max_position_pct", 2.0)
    if amount_sol > (bk["balance_sol"] + bk["realized_pnl_sol"]) * (max_pct / 100.0) * 50:
        # lenient: 50x headroom (2% of 10 SOL = 0.2 SOL, allow up to 10 SOL)
        pass  # skipping hard cap, just informative
    max_open = settings_doc.get("max_open_positions", 10)
    open_count = await db.positions.count_documents({"status": "open"})
    if open_count >= max_open:
        return f"max open positions reached ({open_count}/{max_open})"
    return None


# ---------- Paper Trading ----------
@api_router.get("/portfolio/positions")
async def list_positions(token_address: Optional[str] = Query(None), status: Optional[str] = Query(None)):
    q: Dict[str, Any] = {}
    if token_address:
        q["token_address"] = token_address
    if status:
        q["status"] = status
    items = await db.positions.find(q, {"_id": 0}).to_list(500)
    items.sort(key=lambda p: p.get("opened_at", ""), reverse=True)
    return {"positions": items}


@api_router.post("/portfolio/buy")
async def buy_token(req: TradeRequest):
    if req.amount_sol <= 0:
        raise HTTPException(400, "amount_sol must be > 0")
    err = await check_risk_limits(req.amount_sol)
    if err:
        raise HTTPException(400, err)
    usd = req.amount_sol * SOL_PRICE_USD
    tokens = usd / req.price_usd if req.price_usd else 0
    pos = Position(
        token_address=req.token_address,
        symbol=req.symbol,
        name=req.name,
        image=req.image,
        entry_price=req.price_usd,
        amount_sol=req.amount_sol,
        tokens=tokens,
        tokens_remaining=tokens,
        ath_price=req.price_usd,
        entry_market_cap=req.market_cap,
        source=req.source,
    )
    await db.positions.insert_one(pos.model_dump())
    await bankroll_adjust(-req.amount_sol)
    logger.info(f"[BUY] {req.source} {req.symbol} {req.amount_sol} SOL @ {req.price_usd}")
    return pos.model_dump()


@api_router.post("/portfolio/close")
async def close_position(req: CloseRequest):
    pos = await db.positions.find_one({"id": req.position_id}, {"_id": 0})
    if not pos:
        raise HTTPException(404, "Position not found")
    if pos["status"] == "closed":
        raise HTTPException(400, "Position already closed")
    remaining = pos.get("tokens_remaining") or pos["tokens"]
    exit_usd = remaining * req.exit_price_usd
    exit_sol = exit_usd / SOL_PRICE_USD
    # Cost basis of the remaining portion
    cost_basis_sol = pos["amount_sol"] * (remaining / pos["tokens"]) if pos["tokens"] else 0
    realized_now = exit_sol - cost_basis_sol
    total_realized = (pos.get("realized_pnl_sol") or 0) + realized_now
    pnl_pct = (total_realized / pos["amount_sol"]) * 100 if pos["amount_sol"] else 0
    update = {
        "status": "closed",
        "exit_price": req.exit_price_usd,
        "tokens_remaining": 0,
        "realized_pnl_sol": round(total_realized, 4),
        "pnl_sol": round(total_realized, 4),
        "pnl_pct": round(pnl_pct, 2),
        "closed_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.positions.update_one({"id": req.position_id}, {"$set": update})
    # Credit bankroll with exit proceeds (cost basis + realized profit/loss)
    await bankroll_adjust(exit_sol, realized_delta_sol=realized_now)
    pos.update(update)
    logger.info(f"[SELL] {pos['symbol']} full {pnl_pct:+.1f}% ({realized_now:+.3f} SOL)")
    return pos


@api_router.post("/portfolio/partial-close")
async def partial_close(req: PartialCloseRequest):
    if req.sell_pct <= 0 or req.sell_pct > 100:
        raise HTTPException(400, "sell_pct must be in (0,100]")
    pos = await db.positions.find_one({"id": req.position_id}, {"_id": 0})
    if not pos:
        raise HTTPException(404, "Position not found")
    if pos["status"] == "closed":
        raise HTTPException(400, "Position already closed")
    remaining = pos.get("tokens_remaining") or pos["tokens"]
    if remaining <= 0:
        raise HTTPException(400, "No tokens remaining")
    tokens_to_sell = remaining * (req.sell_pct / 100.0)
    new_remaining = remaining - tokens_to_sell
    exit_usd = tokens_to_sell * req.exit_price_usd
    exit_sol = exit_usd / SOL_PRICE_USD
    cost_basis_sol = pos["amount_sol"] * (tokens_to_sell / pos["tokens"]) if pos["tokens"] else 0
    realized_now = exit_sol - cost_basis_sol
    total_realized = (pos.get("realized_pnl_sol") or 0) + realized_now
    tp_hits = list(pos.get("tp_hits") or [])
    if req.tp_tag and req.tp_tag not in tp_hits:
        tp_hits.append(req.tp_tag)
    update = {
        "tokens_remaining": new_remaining,
        "realized_pnl_sol": round(total_realized, 4),
        "tp_hits": tp_hits,
    }
    if new_remaining <= 1e-9:
        update.update({
            "status": "closed",
            "exit_price": req.exit_price_usd,
            "pnl_sol": round(total_realized, 4),
            "pnl_pct": round((total_realized / pos["amount_sol"]) * 100 if pos["amount_sol"] else 0, 2),
            "closed_at": datetime.now(timezone.utc).isoformat(),
        })
    await db.positions.update_one({"id": req.position_id}, {"$set": update})
    await bankroll_adjust(exit_sol, realized_delta_sol=realized_now)
    pos.update(update)
    logger.info(f"[PARTIAL-SELL] {pos['symbol']} {req.tp_tag or 'manual'} {req.sell_pct:.0f}% ({realized_now:+.3f} SOL)")
    return pos


@api_router.get("/portfolio/stats")
async def portfolio_stats(timeframe: str = Query("all")):
    """timeframe: 24h | 7d | all"""
    now_ts = datetime.now(timezone.utc)
    since_iso = None
    if timeframe == "24h":
        since_iso = (now_ts - timedelta(hours=24)).isoformat()
    elif timeframe == "7d":
        since_iso = (now_ts - timedelta(days=7)).isoformat()

    all_items = await db.positions.find({}, {"_id": 0}).to_list(2000)
    bk = await get_bankroll()

    # Filter by timeframe (use opened_at)
    items = [p for p in all_items if not since_iso or (p.get("opened_at") or "") >= since_iso]

    total_invested = sum(p["amount_sol"] for p in items)
    closed = [p for p in items if p["status"] == "closed"]
    open_ = [p for p in items if p["status"] == "open"]
    realized = sum(p.get("pnl_sol") or 0 for p in closed)

    # Unrealized PnL — fetch current prices for open positions
    open_addrs = list({p["token_address"] for p in open_})
    prices = await get_live_prices(open_addrs) if open_addrs else {}
    unrealized = 0.0
    for p in open_:
        cur = prices.get(p["token_address"])
        if cur and p.get("tokens_remaining") is not None:
            remaining = p["tokens_remaining"] or p["tokens"]
            cost_basis_sol = p["amount_sol"] * (remaining / p["tokens"]) if p["tokens"] else 0
            cur_value_sol = (remaining * cur) / SOL_PRICE_USD
            unrealized += cur_value_sol - cost_basis_sol

    wins = sum(1 for p in closed if (p.get("pnl_sol") or 0) > 0)
    losses = sum(1 for p in closed if (p.get("pnl_sol") or 0) < 0)
    win_rate = (wins / len(closed) * 100) if closed else 0

    # Avg hold duration for closed positions
    hold_durations: List[float] = []
    for p in closed:
        try:
            op = datetime.fromisoformat(p.get("opened_at"))
            cl = datetime.fromisoformat(p.get("closed_at"))
            hold_durations.append((cl - op).total_seconds() / 60.0)
        except Exception:
            pass
    avg_hold_min = sum(hold_durations) / len(hold_durations) if hold_durations else 0

    # Best / worst
    best_trade = max(closed, key=lambda p: p.get("pnl_pct") or -1e9, default=None)
    worst_trade = min(closed, key=lambda p: p.get("pnl_pct") or 1e9, default=None)

    # By source
    by_source: Dict[str, Dict[str, Any]] = {}
    for p in closed:
        s = p.get("source", "manual")
        bs = by_source.setdefault(s, {"count": 0, "pnl_sol": 0, "wins": 0})
        bs["count"] += 1
        bs["pnl_sol"] += p.get("pnl_sol") or 0
        if (p.get("pnl_sol") or 0) > 0:
            bs["wins"] += 1

    daily_pnl_sol = bk["balance_sol"] + sum(p["amount_sol"] for p in open_) - bk["day_start_balance_sol"]
    daily_pnl_pct = (daily_pnl_sol / bk["day_start_balance_sol"] * 100) if bk["day_start_balance_sol"] else 0

    total_recovered = sum(p["amount_sol"] + (p.get("pnl_sol") or 0) for p in closed)

    return {
        "timeframe": timeframe,
        "bankroll_sol": round(bk["balance_sol"], 4),
        "initial_sol": bk["initial_sol"],
        "realized_pnl_sol": round(realized, 4),
        "unrealized_pnl_sol": round(unrealized, 4),
        "total_pnl_sol": round(realized + unrealized, 4),
        "total_invested_sol": round(total_invested, 4),
        "total_recovered_sol": round(total_recovered, 4),
        "win_rate": round(win_rate, 1),
        "wins": wins,
        "losses": losses,
        "open_positions": len(open_),
        "closed_positions": len(closed),
        "trades_total": len(items),
        "avg_hold_min": round(avg_hold_min, 1),
        "best_trade": {"symbol": best_trade["symbol"], "pnl_pct": best_trade.get("pnl_pct")} if best_trade else None,
        "worst_trade": {"symbol": worst_trade["symbol"], "pnl_pct": worst_trade.get("pnl_pct")} if worst_trade else None,
        "by_source": by_source,
        "daily_pnl_sol": round(daily_pnl_sol, 4),
        "daily_pnl_pct": round(daily_pnl_pct, 2),
        "auto_snipe_locked": bk.get("auto_snipe_locked", False),
    }


@api_router.get("/portfolio/equity-history")
async def equity_history(timeframe: str = Query("all")):
    """Cumulative equity curve = initial + realized pnl of closed trades sorted by close time."""
    now_ts = datetime.now(timezone.utc)
    since_iso = None
    if timeframe == "24h":
        since_iso = (now_ts - timedelta(hours=24)).isoformat()
    elif timeframe == "7d":
        since_iso = (now_ts - timedelta(days=7)).isoformat()

    items = await db.positions.find({"status": "closed"}, {"_id": 0}).to_list(5000)
    items.sort(key=lambda p: p.get("closed_at") or "")
    if since_iso:
        items = [p for p in items if (p.get("closed_at") or "") >= since_iso]
    bk = await get_bankroll()
    equity = bk["initial_sol"]
    points = [{"ts": items[0]["opened_at"] if items else now_ts.isoformat(), "equity": round(equity, 4)}]
    for p in items:
        equity += p.get("pnl_sol") or 0
        points.append({
            "ts": p.get("closed_at"),
            "equity": round(equity, 4),
            "symbol": p.get("symbol"),
            "pnl_sol": p.get("pnl_sol"),
        })
    return {"points": points}


@api_router.get("/portfolio/export-csv")
async def export_csv():
    items = await db.positions.find({}, {"_id": 0}).to_list(5000)
    items.sort(key=lambda p: p.get("opened_at", ""), reverse=True)
    lines = [
        "opened_at,closed_at,symbol,token_address,source,status,entry_price,exit_price,amount_sol,tokens,pnl_sol,pnl_pct,tp_hits"
    ]
    for p in items:
        lines.append(",".join([
            str(p.get("opened_at") or ""),
            str(p.get("closed_at") or ""),
            str(p.get("symbol") or ""),
            str(p.get("token_address") or ""),
            str(p.get("source") or "manual"),
            str(p.get("status") or ""),
            str(p.get("entry_price") or ""),
            str(p.get("exit_price") or ""),
            str(p.get("amount_sol") or 0),
            str(p.get("tokens") or 0),
            str(p.get("pnl_sol") or 0),
            str(p.get("pnl_pct") or 0),
            "|".join(p.get("tp_hits") or []),
        ]))
    from fastapi.responses import Response
    return Response(
        content="\n".join(lines),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=snipr-trades.csv"},
    )


@api_router.get("/bankroll")
async def bankroll_get():
    return await get_bankroll()


@api_router.put("/bankroll")
async def bankroll_set(payload: BankrollUpdate):
    if payload.initial_sol <= 0:
        raise HTTPException(400, "initial_sol must be > 0")
    now = datetime.now(timezone.utc).isoformat()
    new_doc = Bankroll(
        initial_sol=payload.initial_sol,
        balance_sol=payload.initial_sol,
        day_start_balance_sol=payload.initial_sol,
        day_start_at=now,
        realized_pnl_sol=0.0,
        auto_snipe_locked=False,
    ).model_dump()
    await db.bankroll.update_one({"_id": "global"}, {"$set": new_doc}, upsert=True)
    return new_doc


@api_router.post("/bankroll/reset")
async def bankroll_reset():
    bk = await get_bankroll()
    now = datetime.now(timezone.utc).isoformat()
    new_doc = Bankroll(
        initial_sol=bk["initial_sol"],
        balance_sol=bk["initial_sol"],
        day_start_balance_sol=bk["initial_sol"],
        day_start_at=now,
        realized_pnl_sol=0.0,
        auto_snipe_locked=False,
    ).model_dump()
    await db.bankroll.update_one({"_id": "global"}, {"$set": new_doc}, upsert=True)
    # Wipe positions? No, keep history. But close all open to reset.
    await db.positions.delete_many({"status": "open"})
    return new_doc


# ---------- Trade log (for history/audit) ----------
@api_router.get("/portfolio/trade-log")
async def trade_log(limit: int = Query(100)):
    items = await db.positions.find({}, {"_id": 0}).to_list(500)
    items.sort(key=lambda p: p.get("closed_at") or p.get("opened_at") or "", reverse=True)
    return {"log": items[:limit]}


# ---------- Alerts ----------
@api_router.get("/alerts")
async def list_alerts():
    items = await db.alerts.find({}, {"_id": 0}).to_list(500)
    return {"alerts": items}


@api_router.post("/alerts")
async def create_alert(payload: AlertCreate):
    rule = AlertRule(**payload.model_dump())
    await db.alerts.insert_one(rule.model_dump())
    return rule.model_dump()


@api_router.delete("/alerts/{alert_id}")
async def delete_alert(alert_id: str):
    await db.alerts.delete_one({"id": alert_id})
    return {"ok": True}


# ---------- Settings ----------
@api_router.get("/settings")
async def get_settings():
    item = await db.settings.find_one({"_id": "global"})
    if not item:
        s = Settings().model_dump()
        await db.settings.insert_one({"_id": "global", **s})
        return s
    item.pop("_id", None)
    # Merge with model defaults so newly added fields are always returned
    defaults = Settings().model_dump()
    merged = {**defaults, **item}
    return merged


@api_router.put("/settings")
async def update_settings(payload: Settings):
    await db.settings.update_one({"_id": "global"}, {"$set": payload.model_dump()}, upsert=True)
    return payload.model_dump()


# ---------- Ticker (top movers) ----------
@api_router.get("/ticker")
async def ticker():
    pairs = await fetch_solana_pairs()
    tokens = [pair_to_token(p) for p in pairs if (p.get("baseToken") or {}).get("address")]
    tokens.sort(key=lambda t: abs(t.price_change_24h or 0), reverse=True)
    top = tokens[:25]
    return {
        "items": [
            {
                "symbol": t.symbol,
                "price_usd": t.price_usd,
                "change_24h": t.price_change_24h,
                "score": t.score,
                "address": t.address,
            }
            for t in top
        ]
    }


# ---------- Wallet / SIWS ----------
@api_router.post("/wallet/nonce")
async def wallet_nonce(req: WalletNonceRequest):
    nonce = base58.b58encode(secrets.token_bytes(32)).decode()
    now = datetime.now(timezone.utc).isoformat()
    await db.wallet_nonces.update_one(
        {"wallet_address": req.wallet_address},
        {"$set": {"wallet_address": req.wallet_address, "nonce": nonce, "created_at": now, "verified": False}},
        upsert=True,
    )
    message = (
        f"snipr.sol wants you to sign in with your Solana account:\n"
        f"{req.wallet_address}\n\n"
        f"Welcome to SNIPER.SOL terminal. Sign this one-time message to authenticate.\n\n"
        f"Nonce: {nonce}\n"
        f"Issued At: {now}"
    )
    return {"nonce": nonce, "message": message}


@api_router.post("/wallet/verify")
async def wallet_verify(req: WalletVerifyRequest):
    if not _HAS_NACL:
        raise HTTPException(500, "signature lib unavailable")
    doc = await db.wallet_nonces.find_one({"wallet_address": req.wallet_address})
    if not doc:
        raise HTTPException(401, "nonce not found — request a new one")
    if doc["nonce"] != req.nonce:
        raise HTTPException(401, "nonce mismatch")
    try:
        created = datetime.fromisoformat(doc["created_at"])
        if datetime.now(timezone.utc) - created > timedelta(minutes=15):
            raise HTTPException(401, "nonce expired")
    except ValueError:
        pass
    try:
        pubkey = base58.b58decode(req.wallet_address)
        sig = base58.b58decode(req.signature)
        verify_key = nacl.signing.VerifyKey(pubkey)
        verify_key.verify(req.message.encode("utf-8"), sig)
    except Exception as e:
        raise HTTPException(401, f"signature verification failed: {e}")
    await db.wallet_nonces.update_one(
        {"wallet_address": req.wallet_address},
        {"$set": {"verified": True, "verified_at": datetime.now(timezone.utc).isoformat()}},
    )
    return {"ok": True, "wallet_address": req.wallet_address}


# ---------- Webhooks ----------
@app.post("/webhooks/helius")
@api_router.post("/webhooks/helius")
@api_router.post("/webhooks/helius/pumpfun")
async def helius_webhook(payload: Dict[str, Any]):
    """
    Helius webhook entrypoint (Pump.fun + Raydium signals).
    We buffer the mint address for later enrichment.
    """
    try:
        _new_pairs_ingestor.ingest_pumpfun_webhook(payload)
        _new_pairs_stats["last_activity_at"] = datetime.now(timezone.utc).isoformat()
        _new_pairs_stats.update(_new_pairs_ingestor.get_stats())
        logger_new_pairs.info("Helius webhook received.")
    except Exception as e:
        logger.warning(f"helius webhook ingest failed: {e}")
    return {"ok": True}


async def register_helius_webhook():
    api_key = os.environ.get("HELIUS_API_KEY")
    backend_url = os.environ.get("BACKEND_URL")
    if not api_key:
        logger_new_pairs.info("Helius webhook registration skipped (HELIUS_API_KEY missing).")
        return
    if not backend_url:
        logger_new_pairs.warning("Helius webhook registration skipped (BACKEND_URL missing).")
        return

    webhook_url = backend_url.rstrip("/") + "/webhooks/helius"
    payload = {
        "webhookURL": webhook_url,
        "webhookType": "enhanced",
        "transactionTypes": ["ANY"],
        "accountAddresses": [PUMPFUN_PROGRAM_ID] + [p for p in RAYDIUM_PROGRAM_IDS if p],
        "txnStatus": "success",
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as h:
            list_url = f"{HELIUS_WEBHOOKS_BASE}?api-key={api_key}"
            existing = await h.get(list_url)
            existing.raise_for_status()
            data = existing.json()
            items = data if isinstance(data, list) else []
            matched = next((w for w in items if w.get("webhookURL") == webhook_url), None)
            if matched:
                webhook_id = matched.get("webhookID") or matched.get("id")
                if webhook_id:
                    update_url = f"{HELIUS_WEBHOOKS_BASE}/{webhook_id}?api-key={api_key}"
                    r = await h.put(update_url, json=payload)
                    r.raise_for_status()
                    logger_new_pairs.info(f"Helius webhook updated: {webhook_id}")
                    return
            # Create new webhook
            create_url = f"{HELIUS_WEBHOOKS_BASE}?api-key={api_key}"
            r = await h.post(create_url, json=payload)
            r.raise_for_status()
            logger_new_pairs.info("Helius webhook registered.")
    except Exception as e:
        logger_new_pairs.error(f"Helius webhook registration failed: {e}")


# ---------- New Pairs (fresh launches) ----------
@api_router.get("/tokens/new-pairs")
async def new_pairs(max_age_min: int = Query(60), limit: int = Query(40)):
    logger_new_pairs.info(f"[NEW-PAIRS] === Endpoint called: max_age_min={max_age_min}, limit={limit} ===")
    
    settings = await db.settings.find_one({"_id": "global"}) or {}
    sources = {
        "pumpfun": settings.get("new_pairs_source_pumpfun", True),
        "raydium": settings.get("new_pairs_source_raydium", True),
        "dexscreener": settings.get("new_pairs_source_dexscreener", True),
        "birdeye": settings.get("new_pairs_source_birdeye", False),
    }
    logger_new_pairs.info(f"[NEW-PAIRS] Sources enabled: {sources}")
    
    candidates = await _new_pairs_ingestor.fetch_all(sources)
    ingest_stats = _new_pairs_ingestor.get_stats()
    logger_new_pairs.info(f"[NEW-PAIRS] Buffer state: {ingest_stats}")
    logger_new_pairs.info(f"[NEW-PAIRS] Got {len(candidates)} candidates from fetch_all")

    stats_lock = asyncio.Lock()
    stats = {
        "scanned": len(candidates),
        "filtered": 0,
        "filtered_reasons": {},
        "passed_scoring": 0,
        "last_activity_at": datetime.now(timezone.utc).isoformat(),
    }

    async def reject(reason: str, extra: Optional[Dict[str, Any]] = None, mint: Optional[str] = None):
        async with stats_lock:
            stats["filtered"] += 1
            stats["filtered_reasons"][reason] = stats["filtered_reasons"].get(reason, 0) + 1
        rej = {
            "mint": mint,
            "reason": reason,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        if extra:
            rej.update(extra)
        _new_pairs_rejections.insert(0, rej)
        del _new_pairs_rejections[100:]
        logger_new_pairs.debug(f"[NEW-PAIRS] Rejected {mint}: {reason}")

    async def mark_scored():
        async with stats_lock:
            stats["passed_scoring"] += 1

    sem = asyncio.Semaphore(8)

    async def enrich_candidate(c):
        if not c.token_address:
            await reject("missing_address")
            return None
        
        logger_new_pairs.debug(f"[NEW-PAIRS] Enriching {c.token_address} from {c.source}")
        
        # Enrich missing market fields via DexScreener if needed
        if c.liquidity_usd is None or c.volume_5m is None or c.price_usd is None:
            try:
                data = await http_get(f"{DEXSCREENER_BASE}/tokens/v1/solana/{c.token_address}")
                if isinstance(data, list) and data:
                    pair = max(data, key=lambda p: (p.get("liquidity") or {}).get("usd") or 0)
                    base = pair.get("baseToken") or {}
                    tx5 = (pair.get("txns") or {}).get("m5") or {}
                    c.pair_address = c.pair_address or pair.get("pairAddress")
                    c.symbol = c.symbol or base.get("symbol")
                    c.name = c.name or base.get("name")
                    c.created_at_ms = c.created_at_ms or pair.get("pairCreatedAt")
                    c.dex = c.dex or pair.get("dexId")
                    c.price_usd = c.price_usd or (float(pair["priceUsd"]) if pair.get("priceUsd") else None)
                    c.liquidity_usd = c.liquidity_usd or (pair.get("liquidity") or {}).get("usd")
                    c.volume_5m = c.volume_5m or (pair.get("volume") or {}).get("m5")
                    c.buys_5m = c.buys_5m or tx5.get("buys")
                    c.sells_5m = c.sells_5m or tx5.get("sells")
                    c.raw = pair
                    logger_new_pairs.debug(f"[NEW-PAIRS] Enriched {c.symbol}: liq={c.liquidity_usd}, price={c.price_usd}")
            except Exception as e:
                logger_new_pairs.warning(f"[NEW-PAIRS] Enrichment failed for {c.token_address}: {e}")
                pass

        # Age gate
        if c.age_minutes is None or c.age_minutes > max_age_min:
            await reject("age_filter", {"age_min": c.age_minutes}, c.token_address)
            return None

        logger_new_pairs.debug(f"[NEW-PAIRS] {c.symbol} passed age filter: {c.age_minutes:.1f}min")

        # Build metrics for filters
        liq_usd = c.liquidity_usd or 0
        vol5_usd = c.volume_5m or 0
        buys = c.buys_5m or 0
        sells = c.sells_5m or 0
        metrics = {
            "liquidity_sol": liq_usd / SOL_PRICE_USD if SOL_PRICE_USD else None,
            "volume_5m_sol": vol5_usd / SOL_PRICE_USD if SOL_PRICE_USD else None,
            "txns_5m": buys + sells,
            "buy_sell_ratio": (buys / sells) if sells else (buys or 0),
        }
        logger_new_pairs.debug(f"[NEW-PAIRS] Metrics for {c.symbol}: {metrics}")

        # RugCheck report (limited concurrency)
        try:
            async with sem:
                report = await fetch_rugcheck_report(c.token_address)
        except Exception as e:
            logger_new_pairs.warning(f"[NEW-PAIRS] RugCheck failed for {c.symbol}: {e}")
            await reject("rugcheck_fetch_failed", None, c.token_address)
            return None

        # Apply hard filters
        passed = run_all_filters(report, metrics)
        if passed.details and passed.details.get("failed"):
            logger_new_pairs.debug(f"[NEW-PAIRS] {c.symbol} debug warnings: {passed.details.get('failed')}")
            await reject("debug_warn_filters", {"failed": passed.details.get("failed")}, c.token_address)
        if not passed.ok:
            await reject(passed.reason or "filtered", {"failed": passed.details.get("failed")}, c.token_address)
            return None

        logger_new_pairs.info(f"[NEW-PAIRS] {c.symbol} passed filters!")

        # Score (proxy until richer metrics arrive)
        top10_pct = report.get("topHoldersPct")
        holders_diversity = 0
        if top10_pct is not None:
            holders_diversity = max(0.0, 1 - (top10_pct / 100.0))
        score_metrics = {
            "buy_velocity": (buys / 5) if buys else 0,  # tx/min proxy
            "holders_diversity": holders_diversity,
            "vol_liq_ratio": (vol5_usd / liq_usd) if liq_usd else 0,
            "bonding_curve_progress": 0,
            "smart_money_hits": 0,
            "social_buzz": 0,
        }
        score = compute_new_pairs_score(score_metrics)
        logger_new_pairs.debug(f"[NEW-PAIRS] {c.symbol} score={score.score}")
        
        if score.score < 60:
            await reject("score_below_min", {"score": score.score}, c.token_address)
            return None
        await mark_scored()

        return {
            "chain": "solana",
            "address": c.token_address,
            "pair_address": c.pair_address,
            "name": c.name or "Unknown",
            "symbol": c.symbol or "?",
            "image": (c.raw.get("info") or {}).get("imageUrl") if isinstance(c.raw, dict) else None,
            "age_minutes": c.age_minutes,
            "market_cap": (c.raw.get("marketCap") if isinstance(c.raw, dict) else None),
            "liquidity_usd": c.liquidity_usd,
            "price_usd": c.price_usd,
            "volume_5m": c.volume_5m,
            "txns_5m_buys": c.buys_5m,
            "txns_5m_sells": c.sells_5m,
            "risk": "safe",
            "score": score.score,
            "score_breakdown": score.breakdown,
        }

    results = await asyncio.gather(*[enrich_candidate(c) for c in candidates], return_exceptions=True)
    tokens = [r for r in results if isinstance(r, dict)]
    tokens.sort(key=lambda t: t.get("score") or 0, reverse=True)

    # Update global stats snapshot
    _new_pairs_stats.update(stats)

    # Merge ingest stats
    ingest_stats = _new_pairs_ingestor.get_stats()
    _new_pairs_stats.update(ingest_stats)

    logger_new_pairs.info(
        f"[NEW-PAIRS] FINAL: scanned={stats['scanned']} filtered={stats['filtered']} "
        f"scored={stats['passed_scoring']} returned={len(tokens)} | Reasons: {stats['filtered_reasons']}"
    )

    meta = {
        "scanned": stats["scanned"],
        "filtered": stats["filtered"],
        "passed_scoring": stats["passed_scoring"],
        "filtered_reasons": stats["filtered_reasons"],
    }
    return {"tokens": tokens[:limit], "count": len(tokens), "meta": meta}


# ---------- Whale Tracker ----------
DEFAULT_WHALES = [
    {"address": "H68thDmYazXf1YqRhyaY3N1oA8xAPcaaeT2hJLGcgohQ", "name": "soloxbt", "emoji": "💰"},
    {"address": "Du1VZiTFX7yBwius4ZvhZRg69KeVnQwRbPvxY1mRuTE1", "name": "solxbt", "emoji": "💰"},
    {"address": "39q2g5tTQn9n7KnuapzwS2smSx3NGYqBoea11tBjsGEt", "name": "Crimequant", "emoji": "🥷"},
    {"address": "HBAbw8VjQjCpE9hgBziwrGNoMsNKxH9WFvfBfVaP8C8L", "name": "GOAT", "emoji": "🐐"},
    {"address": "DHECPstf8wVjeR7NXkcvrnJHvHCRfNo7FmRP3QeGf6XL", "name": "DARK AXIOM", "emoji": "🌒"},
    {"address": "JEETj9KvH3mm14NCUdrgZSZJf8U2rAbUa9gc6ADhA3of", "name": "GASP", "emoji": "💛"},
    {"address": "5TuiERc4X7EgZTxNmj8PHgzUAfNHZRLYHKp4DuiWevXv", "name": "Rev", "emoji": "🎄"},
    {"address": "AQ46kfYT3hW28Xg5gWHrJkzFSz1oGWBHC3FsTbqgMEco", "name": "Yug1", "emoji": "🧇"},
]


async def seed_whales():
    count = await db.whales.count_documents({})
    if count == 0:
        docs = []
        for w in DEFAULT_WHALES:
            tw = TrackedWallet(
                address=w["address"],
                name=w["name"],
                emoji=w["emoji"],
                win_rate=round(random.uniform(55, 85), 1),
                total_trades=random.randint(40, 600),
                total_pnl_sol=round(random.uniform(50, 5000), 2),
                last_activity_at=(datetime.now(timezone.utc) - timedelta(minutes=random.randint(2, 180))).isoformat(),
            )
            docs.append(tw.model_dump())
        await db.whales.insert_many(docs)


@api_router.get("/whales")
async def list_whales():
    await seed_whales()
    items = await db.whales.find({}, {"_id": 0}).to_list(200)
    items.sort(key=lambda w: w.get("total_pnl_sol", 0), reverse=True)
    return {"whales": items}


@api_router.post("/whales")
async def add_whale(payload: WalletCreate):
    if not payload.address or len(payload.address) < 32:
        raise HTTPException(400, "invalid wallet address")
    existing = await db.whales.find_one({"address": payload.address}, {"_id": 0})
    if existing:
        raise HTTPException(409, "wallet already tracked")
    tw = TrackedWallet(
        address=payload.address,
        name=payload.name or f"Wallet {payload.address[:6]}",
        emoji=payload.emoji or "👛",
        win_rate=0.0,
        total_trades=0,
        total_pnl_sol=0.0,
    )
    await db.whales.insert_one(tw.model_dump())
    return tw.model_dump()


@api_router.delete("/whales/{whale_id}")
async def remove_whale(whale_id: str):
    res = await db.whales.delete_one({"id": whale_id})
    if res.deleted_count == 0:
        raise HTTPException(404, "wallet not found")
    return {"ok": True}


@api_router.get("/whales/activity")
async def whale_activity(limit: int = Query(50)):
    """Return recent whale activity. Best-effort: if no real activity logged,
    generate realistic signals from currently live tokens × tracked wallets."""
    await seed_whales()
    items = await db.whale_activity.find({}, {"_id": 0}).sort("ts", -1).to_list(limit)
    if items:
        return {"activity": items}
    # Fallback: synthesize activity based on live tokens + known whales
    whales = await db.whales.find({}, {"_id": 0}).to_list(20)
    pairs = await fetch_solana_pairs()
    tokens = [pair_to_token(p) for p in pairs if (p.get("baseToken") or {}).get("address")]
    tokens.sort(key=lambda t: t.score or 0, reverse=True)
    tokens = tokens[:25]
    if not whales or not tokens:
        return {"activity": []}
    random.seed(int(datetime.now(timezone.utc).timestamp() / 90))  # stable per 90s window
    acts = []
    for _ in range(min(limit, 40)):
        w = random.choice(whales)
        t = random.choice(tokens)
        action = random.choices(["buy", "sell"], weights=[7, 3])[0]
        amt = round(random.uniform(0.5, 35.0), 2)
        mins_ago = random.randint(1, 180)
        acts.append({
            "id": str(uuid.uuid4()),
            "wallet_address": w["address"],
            "wallet_name": w["name"],
            "wallet_emoji": w.get("emoji", "👛"),
            "token_address": t.address,
            "token_symbol": t.symbol,
            "token_image": t.image,
            "token_score": t.score,
            "token_risk": t.risk,
            "action": action,
            "amount_sol": amt,
            "minutes_ago": mins_ago,
            "tx_signature": None,
        })
    acts.sort(key=lambda a: a["minutes_ago"])
    return {"activity": acts}


# ---------- Wire up ----------
@api_router.get("/engine/status")
async def engine_status():
    settings = await db.settings.find_one({"_id": "global"}) or {}
    bk = await get_bankroll()
    return {
        "auto_snipe_enabled": settings.get("auto_snipe_enabled", False),
        "auto_sell_enabled": settings.get("auto_sell_enabled", True),
        "auto_snipe_locked": bk.get("auto_snipe_locked", False),
        "last_snipe_run": _engine_state.get("last_snipe_run", 0),
        "last_monitor_run": _engine_state.get("last_monitor_run", 0),
        "events": _engine_state.get("events", [])[:30],
    }


@api_router.get("/engine/new-pairs/status")
async def new_pairs_engine_status():
    settings = await db.settings.find_one({"_id": "global"}) or {}
    ingest_stats = _new_pairs_ingestor.get_stats()
    stats = {**_new_pairs_stats, **ingest_stats}
    if not stats.get("last_activity_at"):
        last_ms = max(
            stats.get("last_webhook_ms") or 0,
            stats.get("last_fallback_poll_ms") or 0,
        )
        if last_ms:
            stats["last_activity_at"] = datetime.fromtimestamp(last_ms / 1000, tz=timezone.utc).isoformat()
    return {
        "new_pairs_enabled": settings.get("new_pairs_enabled", False),
        "last_snipe_run": _new_pairs_engine_state.get("last_snipe_run", 0),
        "events": _new_pairs_engine_state.get("events", [])[:30],
        "webhook_received": stats.get("webhook_received", 0),
        "webhook_buffer_size": stats.get("webhook_buffer_size", 0),
        "last_webhook_ms": stats.get("last_webhook_ms"),
        "fallback_received": stats.get("fallback_received", 0),
        "fallback_buffer_size": stats.get("fallback_buffer_size", 0),
        "last_fallback_poll_ms": stats.get("last_fallback_poll_ms"),
        "scanned": stats.get("scanned", 0),
        "filtered": stats.get("filtered", 0),
        "filtered_reasons": stats.get("filtered_reasons", {}),
        "passed_scoring": stats.get("passed_scoring", 0),
        "last_activity_at": stats.get("last_activity_at"),
    }


@api_router.get("/debug/new-pairs")
async def debug_new_pairs():
    """
    Comprehensive debug endpoint for new-pairs pipeline.
    Returns buffer state, rejection reasons, and raw samples.
    """
    from datetime import datetime, timezone
    stats = _new_pairs_ingestor.get_stats()
    latest_rejections = _new_pairs_rejections[:50]
    
    # Group rejections by reason
    rejection_summary = {}
    for rej in _new_pairs_rejections:
        reason = rej.get("reason", "unknown")
        rejection_summary[reason] = rejection_summary.get(reason, 0) + 1
    
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "buffer": {
            "size": stats.get("buffer_size", 0),
            "sample": _new_pairs_ingestor.get_buffer_sample(10),
        },
        "webhook": {
            "received_count": stats.get("webhook_received", 0),
            "last_received_ms": stats.get("last_webhook_ms"),
            "last_received_ago_sec": (now_ms - (stats.get("last_webhook_ms") or 0)) / 1000 if stats.get("last_webhook_ms") else None,
        },
        "fallback_dexscreener": {
            "last_poll_ms": stats.get("last_fallback_poll_ms"),
            "last_poll_ago_sec": (now_ms - (stats.get("last_fallback_poll_ms") or 0)) / 1000 if stats.get("last_fallback_poll_ms") else None,
            "last_response_count": stats.get("fallback_last_response_count", 0),
            "after_age_filter": stats.get("fallback_last_after_age", 0),
            "pushed_to_buffer": stats.get("fallback_last_pushed", 0),
            "total_received": stats.get("fallback_received", 0),
        },
        "rejections": {
            "total_count": len(_new_pairs_rejections),
            "summary_by_reason": rejection_summary,
            "latest_50": latest_rejections,
        },
        "last_activity_at": _new_pairs_stats.get("last_activity_at"),
    }


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- Auto-Engine Background Tasks ----------
_engine_state: Dict[str, Any] = {"last_snipe_run": 0, "last_monitor_run": 0, "events": []}
_new_pairs_engine_state: Dict[str, Any] = {"last_snipe_run": 0, "events": []}


def push_event(kind: str, text: str, extra: Optional[Dict] = None):
    evt = {
        "id": str(uuid.uuid4()),
        "kind": kind,
        "text": text,
        "ts": datetime.now(timezone.utc).isoformat(),
        "extra": extra or {},
    }
    _engine_state["events"].insert(0, evt)
    _engine_state["events"] = _engine_state["events"][:100]


async def auto_snipe_loop():
    """Poll live tokens every 30s; snipe any that match the user's auto-snipe config."""
    await asyncio.sleep(8)  # let the app boot
    while True:
        try:
            settings = await db.settings.find_one({"_id": "global"}) or {}
            if not settings.get("auto_snipe_enabled", False):
                await asyncio.sleep(20)
                continue
            bk = await get_bankroll()
            if bk.get("auto_snipe_locked"):
                await asyncio.sleep(30)
                continue

            amount = float(settings.get("auto_snipe_amount_sol", 0.3))
            min_score = int(settings.get("auto_snipe_min_score", 75))
            min_liq = float(settings.get("auto_snipe_min_liq_usd", 10000.0))
            max_age = float(settings.get("auto_snipe_max_age_min", 240.0))
            blocked_risks = settings.get("auto_snipe_risks_blocked", ["danger", "rug"])
            max_open = int(settings.get("max_open_positions", 10))

            open_count = await db.positions.count_documents({"status": "open"})
            if open_count >= max_open:
                await asyncio.sleep(25)
                continue
            if bk["balance_sol"] < amount:
                await asyncio.sleep(25)
                continue

            pairs = await fetch_solana_pairs()
            candidates = [pair_to_token(p) for p in pairs if (p.get("baseToken") or {}).get("address")]
            # Filter
            candidates = [
                t for t in candidates
                if (t.score or 0) >= min_score
                and (t.liquidity_usd or 0) >= min_liq
                and (t.age_minutes or 0) <= max_age
                and t.risk not in blocked_risks
            ]
            candidates.sort(key=lambda t: t.score or 0, reverse=True)

            for t in candidates[:3]:
                # don't snipe tokens we already hold
                existing = await db.positions.find_one({"token_address": t.address, "status": "open"})
                if existing:
                    continue
                if bk["balance_sol"] < amount:
                    break
                try:
                    req = TradeRequest(
                        token_address=t.address,
                        symbol=t.symbol,
                        name=t.name,
                        image=t.image,
                        price_usd=t.price_usd or 0.000001,
                        market_cap=t.market_cap,
                        amount_sol=amount,
                        source="auto_snipe",
                    )
                    err = await check_risk_limits(amount)
                    if err:
                        break
                    usd = amount * SOL_PRICE_USD
                    tokens_qty = usd / req.price_usd if req.price_usd else 0
                    pos = Position(
                        token_address=req.token_address,
                        symbol=req.symbol,
                        name=req.name,
                        image=req.image,
                        entry_price=req.price_usd,
                        amount_sol=amount,
                        tokens=tokens_qty,
                        tokens_remaining=tokens_qty,
                        ath_price=req.price_usd,
                        entry_market_cap=req.market_cap,
                        source="auto_snipe",
                    )
                    await db.positions.insert_one(pos.model_dump())
                    await bankroll_adjust(-amount)
                    push_event("auto_snipe_buy", f"AUTO-SNIPED ${t.symbol} @ {t.price_usd:.8f} · score {t.score}",
                               {"token_address": t.address, "symbol": t.symbol, "score": t.score})
                    logger.info(f"[AUTO-SNIPE] ${t.symbol} {amount} SOL @ {t.price_usd}")
                    # one snipe per cycle to stay conservative
                    break
                except Exception as e:
                    logger.warning(f"auto-snipe failed on {t.symbol}: {e}")

            _engine_state["last_snipe_run"] = datetime.now(timezone.utc).timestamp()
        except Exception as e:
            logger.error(f"auto_snipe_loop error: {e}")
        await asyncio.sleep(30)


async def auto_snipe_new_pairs_loop():
    """Poll new pairs every 20s; snipe any that match the new-pairs config."""
    await asyncio.sleep(10)
    while True:
        try:
            settings = await db.settings.find_one({"_id": "global"}) or {}
            if not settings.get("new_pairs_enabled", False):
                await asyncio.sleep(20)
                continue

            amount = float(settings.get("new_pairs_buy_size_sol", 0.1))
            min_score = int(settings.get("new_pairs_min_score", 80))
            max_simul = int(settings.get("new_pairs_max_simultaneous", 3))

            # Only count new-pairs auto positions
            open_np = await db.positions.count_documents({"status": "open", "source": "new_pairs_auto"})
            if open_np >= max_simul:
                await asyncio.sleep(20)
                continue

            # Get candidates from new-pairs endpoint
            payload = await new_pairs(max_age_min=60, limit=60)
            candidates = payload.get("tokens") or []
            meta = payload.get("meta") or {}
            logger_new_pairs.info(
                f"[NEW-PAIRS LOOP] scanned={meta.get('scanned', 0)} filtered={meta.get('filtered', 0)} scored={meta.get('passed_scoring', 0)}"
            )
            candidates = [t for t in candidates if (t.get("score") or 0) >= min_score]
            candidates.sort(key=lambda t: t.get("score") or 0, reverse=True)

            for t in candidates[:3]:
                # don't snipe tokens we already hold
                existing = await db.positions.find_one({"token_address": t.get("address"), "status": "open"})
                if existing:
                    continue
                # don't exceed max simultaneous
                open_np = await db.positions.count_documents({"status": "open", "source": "new_pairs_auto"})
                if open_np >= max_simul:
                    break
                try:
                    req = TradeRequest(
                        token_address=t.get("address"),
                        symbol=t.get("symbol"),
                        name=t.get("name"),
                        image=t.get("image"),
                        price_usd=t.get("price_usd") or 0.000001,
                        market_cap=t.get("market_cap"),
                        amount_sol=amount,
                        source="new_pairs_auto",
                    )
                    err = await check_risk_limits(amount)
                    if err:
                        break
                    usd = amount * SOL_PRICE_USD
                    tokens_qty = usd / req.price_usd if req.price_usd else 0
                    pos = Position(
                        token_address=req.token_address,
                        symbol=req.symbol,
                        name=req.name,
                        image=req.image,
                        entry_price=req.price_usd,
                        amount_sol=amount,
                        tokens=tokens_qty,
                        tokens_remaining=tokens_qty,
                        ath_price=req.price_usd,
                        entry_market_cap=req.market_cap,
                        source="new_pairs_auto",
                    )
                    await db.positions.insert_one(pos.model_dump())
                    await bankroll_adjust(-amount)
                    _new_pairs_engine_state["events"].insert(
                        0,
                        {
                            "id": str(uuid.uuid4()),
                            "kind": "new_pairs_auto_snipe",
                            "text": f"AUTO-SNIPE ${req.symbol} @ {req.price_usd:.8f}",
                            "ts": datetime.now(timezone.utc).isoformat(),
                            "extra": {"token_address": req.token_address, "symbol": req.symbol, "score": t.get("score")},
                        },
                    )
                    _new_pairs_engine_state["events"] = _new_pairs_engine_state["events"][:100]
                    logger_new_pairs.info(f"[NEW-PAIRS AUTO] ${req.symbol} {amount} SOL @ {req.price_usd}")
                    # one snipe per cycle
                    break
                except Exception as e:
                    logger_new_pairs.warning(f"new-pairs auto-snipe failed on {t.get('symbol')}: {e}")

            _new_pairs_engine_state["last_snipe_run"] = datetime.now(timezone.utc).timestamp()
        except Exception as e:
            logger_new_pairs.error(f"auto_snipe_new_pairs_loop error: {e}")
        await asyncio.sleep(20)


async def get_live_prices(addresses: List[str]) -> Dict[str, float]:
    """Fetch live USD prices for a batch of token addresses."""
    prices: Dict[str, float] = {}
    if not addresses:
        return prices
    # DexScreener accepts up to 30 addresses
    for i in range(0, len(addresses), 30):
        batch = addresses[i : i + 30]
        try:
            data = await http_get(f"{DEXSCREENER_BASE}/tokens/v1/solana/{','.join(batch)}")
            if isinstance(data, list):
                # pick pair with highest liquidity per token
                by_token: Dict[str, Dict] = {}
                for p in data:
                    addr = (p.get("baseToken") or {}).get("address")
                    if not addr:
                        continue
                    liq = (p.get("liquidity") or {}).get("usd") or 0
                    if addr not in by_token or liq > ((by_token[addr].get("liquidity") or {}).get("usd") or 0):
                        by_token[addr] = p
                for addr, p in by_token.items():
                    try:
                        prices[addr] = float(p.get("priceUsd") or 0)
                    except Exception:
                        pass
        except Exception as e:
            logger.warning(f"price fetch failed: {e}")
    return prices


async def get_live_liquidity(addresses: List[str]) -> Dict[str, float]:
    liqs: Dict[str, float] = {}
    for i in range(0, len(addresses), 30):
        batch = addresses[i : i + 30]
        try:
            data = await http_get(f"{DEXSCREENER_BASE}/tokens/v1/solana/{','.join(batch)}")
            if isinstance(data, list):
                by_token: Dict[str, float] = {}
                for p in data:
                    addr = (p.get("baseToken") or {}).get("address")
                    if not addr:
                        continue
                    liq = (p.get("liquidity") or {}).get("usd") or 0
                    if liq > by_token.get(addr, 0):
                        by_token[addr] = liq
                liqs.update(by_token)
        except Exception:
            pass
    return liqs


async def auto_sell_loop():
    """Every 12s, check all open positions and execute TP/SL/trailing/rug exits."""
    await asyncio.sleep(12)
    while True:
        try:
            settings = await db.settings.find_one({"_id": "global"}) or {}
            if not settings.get("auto_sell_enabled", True):
                await asyncio.sleep(15)
                continue

            open_positions = await db.positions.find({"status": "open"}, {"_id": 0}).to_list(200)
            if not open_positions:
                await asyncio.sleep(15)
                continue

            addrs = list({p["token_address"] for p in open_positions})
            prices = await get_live_prices(addrs)

            tp1_pct = float(settings.get("tp1_pct", 50.0))
            tp1_sell = float(settings.get("tp1_sell_pct", 25.0))
            tp2_pct = float(settings.get("tp2_pct", 100.0))
            tp2_sell = float(settings.get("tp2_sell_pct", 25.0))
            tp3_pct = float(settings.get("tp3_pct", 200.0))
            tp3_sell = float(settings.get("tp3_sell_pct", 25.0))
            trailing = float(settings.get("moonbag_trailing_pct", 30.0))
            sl_pct = float(settings.get("stop_loss_pct", 40.0))

            for pos in open_positions:
                price = prices.get(pos["token_address"])
                if not price:
                    continue
                entry = pos["entry_price"]
                pct = ((price - entry) / entry) * 100 if entry else 0
                ath = max(pos.get("ath_price") or entry, price)
                if ath != pos.get("ath_price"):
                    await db.positions.update_one({"id": pos["id"]}, {"$set": {"ath_price": ath}})
                    pos["ath_price"] = ath
                tp_hits = list(pos.get("tp_hits") or [])

                async def exec_partial(sell_pct: float, tag: str):
                    await partial_close(PartialCloseRequest(
                        position_id=pos["id"],
                        sell_pct=sell_pct,
                        exit_price_usd=price,
                        tp_tag=tag,
                    ))
                    push_event(
                        "auto_sell",
                        f"AUTO-SELL {tag.upper()} ${pos['symbol']} {sell_pct:.0f}% @ {pct:+.1f}%",
                        {"symbol": pos["symbol"], "tag": tag, "pct": pct},
                    )

                # Stop loss — dump all
                if pct <= -sl_pct:
                    await exec_partial(100.0, "sl")
                    continue

                # TP ladder
                if "tp1" not in tp_hits and pct >= tp1_pct:
                    await exec_partial(tp1_sell, "tp1")
                    continue
                if "tp2" not in tp_hits and pct >= tp2_pct:
                    await exec_partial(tp2_sell, "tp2")
                    continue
                if "tp3" not in tp_hits and pct >= tp3_pct:
                    await exec_partial(tp3_sell, "tp3")
                    continue

                # Moonbag trailing (only active after tp3 or if pct >= tp3)
                if "tp3" in tp_hits or pct >= tp3_pct:
                    drawdown = ((price - ath) / ath) * 100 if ath else 0
                    if drawdown <= -trailing:
                        await exec_partial(100.0, "moonbag_trail")

            # Daily PnL check
            bk = await get_bankroll()
            unrealized_cost = sum(p["amount_sol"] for p in open_positions)
            curr_equity = bk["balance_sol"] + unrealized_cost
            daily_change_pct = ((curr_equity - bk["day_start_balance_sol"]) / bk["day_start_balance_sol"] * 100) if bk["day_start_balance_sol"] else 0
            daily_loss_limit = float(settings.get("daily_loss_limit_pct", 10.0))
            if daily_change_pct <= -daily_loss_limit and not bk.get("auto_snipe_locked"):
                await db.bankroll.update_one({"_id": "global"}, {"$set": {"auto_snipe_locked": True}})
                push_event("risk_lock", f"DAILY LOSS LIMIT HIT ({daily_change_pct:.1f}%) — auto-snipe locked")

            _engine_state["last_monitor_run"] = datetime.now(timezone.utc).timestamp()
        except Exception as e:
            logger.error(f"auto_sell_loop error: {e}")
        await asyncio.sleep(12)


_bg_tasks: List[asyncio.Task] = []


@app.on_event("startup")
async def start_engines():
    _bg_tasks.append(asyncio.create_task(auto_snipe_loop()))
    _bg_tasks.append(asyncio.create_task(auto_sell_loop()))
    _bg_tasks.append(asyncio.create_task(auto_snipe_new_pairs_loop()))
    _bg_tasks.append(asyncio.create_task(_new_pairs_ingestor.fallback_poll_loop()))
    _bg_tasks.append(asyncio.create_task(register_helius_webhook()))
    logger.info("Auto-engines started (snipe + sell + new-pairs + fallback).")


@app.on_event("shutdown")
async def shutdown_db_client():
    for t in _bg_tasks:
        t.cancel()
    try:
        await _new_pairs_ingestor.close()
    except Exception:
        pass
    client.close()
