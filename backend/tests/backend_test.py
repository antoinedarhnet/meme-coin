"""Solana Sniping Terminal - Backend API tests"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://coin-hunter-15.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="session")
def s():
    return requests.Session()


# Health
def test_root(s):
    r = s.get(f"{API}/", timeout=30)
    assert r.status_code == 200
    assert r.json().get("status") == "online"


# Tokens live
def test_tokens_live_default(s):
    r = s.get(f"{API}/tokens/live", timeout=60)
    assert r.status_code == 200
    data = r.json()
    assert "tokens" in data and isinstance(data["tokens"], list)
    if data["tokens"]:
        t = data["tokens"][0]
        for k in ("address", "symbol", "score", "risk"):
            assert k in t


@pytest.mark.parametrize("sort", ["score", "age", "volume", "mc", "change_24h"])
def test_tokens_live_sorts(s, sort):
    r = s.get(f"{API}/tokens/live", params={"sort": sort, "limit": 10}, timeout=60)
    assert r.status_code == 200
    assert isinstance(r.json().get("tokens"), list)


def test_tokens_live_filters(s):
    r = s.get(f"{API}/tokens/live", params={"min_liq": 10000, "min_score": 30, "risk": "safe", "limit": 20}, timeout=60)
    assert r.status_code == 200
    for t in r.json()["tokens"]:
        assert (t.get("liquidity_usd") or 0) >= 10000
        assert (t.get("score") or 0) >= 30
        assert t.get("risk") == "safe"


# Token detail
def test_token_detail(s):
    live = s.get(f"{API}/tokens/live", params={"limit": 5}, timeout=60).json()
    if not live["tokens"]:
        pytest.skip("No live tokens available")
    addr = live["tokens"][0]["address"]
    r = s.get(f"{API}/tokens/{addr}", timeout=60)
    assert r.status_code == 200
    d = r.json()
    assert "token" in d and "score" in d and "raw" in d and "all_pairs" in d
    assert "breakdown" in d["score"]


# Ticker
def test_ticker(s):
    r = s.get(f"{API}/ticker", timeout=60)
    assert r.status_code == 200
    items = r.json()["items"]
    assert isinstance(items, list)
    assert len(items) <= 25
    if items:
        for k in ("symbol", "price_usd", "change_24h", "score", "address"):
            assert k in items[0]


# KOLs
def test_kols_seed(s):
    r = s.get(f"{API}/kols", timeout=30)
    assert r.status_code == 200
    kols = r.json()["kols"]
    assert len(kols) >= 6


def test_kol_add_dup_delete(s):
    handle = f"TEST_{int(time.time())}"
    r = s.post(f"{API}/kols", json={"handle": handle, "name": "Test K"})
    assert r.status_code == 200
    kol = r.json()
    assert kol["handle"].startswith("@")
    # duplicate
    r2 = s.post(f"{API}/kols", json={"handle": handle})
    assert r2.status_code == 409
    # delete
    rd = s.delete(f"{API}/kols/{kol['id']}")
    assert rd.status_code == 200


def test_kols_calls(s):
    r = s.get(f"{API}/kols/calls", timeout=60)
    assert r.status_code == 200
    d = r.json()
    assert "calls" in d and "cross_calls" in d
    for c in d["cross_calls"]:
        assert c["callers_count"] >= 2


# Narratives
def test_narratives(s):
    r = s.get(f"{API}/narratives", timeout=60)
    assert r.status_code == 200
    n = r.json()["narratives"]
    assert len(n) == 8
    for it in n:
        assert "matched_tokens" in it


# Portfolio
def test_portfolio_flow(s):
    live = s.get(f"{API}/tokens/live", params={"limit": 5}, timeout=60).json()
    if not live["tokens"]:
        pytest.skip("No tokens")
    t = live["tokens"][0]
    payload = {
        "token_address": t["address"],
        "symbol": t["symbol"],
        "name": t["name"],
        "image": t.get("image"),
        "price_usd": t.get("price_usd") or 0.0001,
        "market_cap": t.get("market_cap"),
        "amount_sol": 1.0,
    }
    rb = s.post(f"{API}/portfolio/buy", json=payload)
    assert rb.status_code == 200
    pos = rb.json()
    assert pos["status"] == "open"

    rl = s.get(f"{API}/portfolio/positions")
    assert rl.status_code == 200
    assert any(p["id"] == pos["id"] for p in rl.json()["positions"])

    rc = s.post(f"{API}/portfolio/close", json={"position_id": pos["id"], "exit_price_usd": (payload["price_usd"]) * 1.5})
    assert rc.status_code == 200
    closed = rc.json()
    assert closed["status"] == "closed"
    assert closed["pnl_sol"] is not None

    rs = s.get(f"{API}/portfolio/stats")
    assert rs.status_code == 200
    stats = rs.json()
    for k in ("total_invested_sol", "realized_pnl_sol", "win_rate", "open_positions", "closed_positions"):
        assert k in stats


# Alerts
def test_alerts_crud(s):
    r = s.post(f"{API}/alerts", json={"name": "TEST_alert", "type": "score", "score_threshold": 80, "channels": ["browser"]})
    assert r.status_code == 200
    alert = r.json()
    rl = s.get(f"{API}/alerts")
    assert rl.status_code == 200
    assert any(a["id"] == alert["id"] for a in rl.json()["alerts"])
    rd = s.delete(f"{API}/alerts/{alert['id']}")
    assert rd.status_code == 200


# Settings
def test_settings(s):
    r = s.get(f"{API}/settings")
    assert r.status_code == 200
    cur = r.json()
    cur["default_slippage"] = 25.5
    ru = s.put(f"{API}/settings", json=cur)
    assert ru.status_code == 200
    assert ru.json()["default_slippage"] == 25.5
