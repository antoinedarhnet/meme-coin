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
    amount_sol: float  # SOL invested
    tokens: float  # token amount bought
    entry_market_cap: Optional[float] = None
    status: str = "open"  # open / closed
    exit_price: Optional[float] = None
    pnl_sol: Optional[float] = None
    pnl_pct: Optional[float] = None
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


class CloseRequest(BaseModel):
    position_id: str
    exit_price_usd: float


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


# ---------- Paper Trading ----------
@api_router.get("/portfolio/positions")
async def list_positions():
    items = await db.positions.find({}, {"_id": 0}).to_list(500)
    items.sort(key=lambda p: p.get("opened_at", ""), reverse=True)
    return {"positions": items}


@api_router.post("/portfolio/buy")
async def buy_token(req: TradeRequest):
    if req.amount_sol <= 0:
        raise HTTPException(400, "amount_sol must be > 0")
    sol_price = 180.0  # paper sim
    usd = req.amount_sol * sol_price
    tokens = usd / req.price_usd if req.price_usd else 0
    pos = Position(
        token_address=req.token_address,
        symbol=req.symbol,
        name=req.name,
        image=req.image,
        entry_price=req.price_usd,
        amount_sol=req.amount_sol,
        tokens=tokens,
        entry_market_cap=req.market_cap,
    )
    await db.positions.insert_one(pos.model_dump())
    return pos.model_dump()


@api_router.post("/portfolio/close")
async def close_position(req: CloseRequest):
    pos = await db.positions.find_one({"id": req.position_id}, {"_id": 0})
    if not pos:
        raise HTTPException(404, "Position not found")
    if pos["status"] == "closed":
        raise HTTPException(400, "Position already closed")
    sol_price = 180.0
    exit_usd = pos["tokens"] * req.exit_price_usd
    exit_sol = exit_usd / sol_price
    pnl_sol = exit_sol - pos["amount_sol"]
    pnl_pct = (pnl_sol / pos["amount_sol"]) * 100 if pos["amount_sol"] else 0
    update = {
        "status": "closed",
        "exit_price": req.exit_price_usd,
        "pnl_sol": round(pnl_sol, 4),
        "pnl_pct": round(pnl_pct, 2),
        "closed_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.positions.update_one({"id": req.position_id}, {"$set": update})
    pos.update(update)
    return pos


@api_router.get("/portfolio/stats")
async def portfolio_stats():
    items = await db.positions.find({}, {"_id": 0}).to_list(1000)
    total_invested = sum(p["amount_sol"] for p in items)
    closed = [p for p in items if p["status"] == "closed"]
    open_ = [p for p in items if p["status"] == "open"]
    realized = sum(p.get("pnl_sol") or 0 for p in closed)
    wins = sum(1 for p in closed if (p.get("pnl_sol") or 0) > 0)
    win_rate = (wins / len(closed) * 100) if closed else 0
    return {
        "total_invested_sol": round(total_invested, 4),
        "realized_pnl_sol": round(realized, 4),
        "win_rate": round(win_rate, 1),
        "open_positions": len(open_),
        "closed_positions": len(closed),
        "trades_total": len(items),
    }


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
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
