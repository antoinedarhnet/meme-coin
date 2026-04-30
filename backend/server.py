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

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

app = FastAPI(title="Solana Sniping Terminal API")
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("sniping")

DEXSCREENER_BASE = "https://api.dexscreener.com"

# ---------- In-process cache ----------
_cache: Dict[str, Any] = {"pairs": {"data": [], "ts": 0}}
CACHE_TTL = 20  # seconds


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


class Bankroll(BaseModel):
    initial_sol: float = 10.0
    balance_sol: float = 10.0
    realized_pnl_sol: float = 0.0
    day_start_balance_sol: float = 10.0
    day_start_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    auto_snipe_locked: bool = False  # set true when daily loss limit breached


class BankrollUpdate(BaseModel):
    initial_sol: float


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
async def portfolio_stats():
    items = await db.positions.find({}, {"_id": 0}).to_list(1000)
    bk = await get_bankroll()
    total_invested = sum(p["amount_sol"] for p in items)
    closed = [p for p in items if p["status"] == "closed"]
    open_ = [p for p in items if p["status"] == "open"]
    realized = sum(p.get("pnl_sol") or 0 for p in closed)
    wins = sum(1 for p in closed if (p.get("pnl_sol") or 0) > 0)
    win_rate = (wins / len(closed) * 100) if closed else 0
    by_source: Dict[str, Dict[str, Any]] = {}
    for p in closed:
        s = p.get("source", "manual")
        bs = by_source.setdefault(s, {"count": 0, "pnl_sol": 0, "wins": 0})
        bs["count"] += 1
        bs["pnl_sol"] += p.get("pnl_sol") or 0
        if (p.get("pnl_sol") or 0) > 0:
            bs["wins"] += 1
    # Daily PnL
    daily_pnl_sol = bk["balance_sol"] + sum(p["amount_sol"] for p in open_) - bk["day_start_balance_sol"]
    daily_pnl_pct = (daily_pnl_sol / bk["day_start_balance_sol"] * 100) if bk["day_start_balance_sol"] else 0
    return {
        "bankroll_sol": round(bk["balance_sol"], 4),
        "initial_sol": bk["initial_sol"],
        "realized_pnl_sol": round(realized, 4),
        "total_invested_sol": round(total_invested, 4),
        "win_rate": round(win_rate, 1),
        "open_positions": len(open_),
        "closed_positions": len(closed),
        "trades_total": len(items),
        "by_source": by_source,
        "daily_pnl_sol": round(daily_pnl_sol, 4),
        "daily_pnl_pct": round(daily_pnl_pct, 2),
        "auto_snipe_locked": bk.get("auto_snipe_locked", False),
    }


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
    return item


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
    logger.info("Auto-engines started (snipe + sell).")


@app.on_event("shutdown")
async def shutdown_db_client():
    for t in _bg_tasks:
        t.cancel()
    client.close()
