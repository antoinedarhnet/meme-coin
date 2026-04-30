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



# ---------- V3: Bankroll + Auto-Engine tests ----------

def test_bankroll_default(s):
    # Ensure clean slate
    s.post(f"{API}/bankroll/reset")
    r = s.get(f"{API}/bankroll")
    assert r.status_code == 200
    bk = r.json()
    assert bk["initial_sol"] > 0
    assert bk["balance_sol"] == bk["initial_sol"]
    for k in ("initial_sol", "balance_sol", "realized_pnl_sol", "day_start_balance_sol", "auto_snipe_locked"):
        assert k in bk


def test_bankroll_put_resets(s):
    r = s.put(f"{API}/bankroll", json={"initial_sol": 25.0})
    assert r.status_code == 200
    d = r.json()
    assert d["initial_sol"] == 25.0
    assert d["balance_sol"] == 25.0
    assert d["realized_pnl_sol"] == 0.0
    assert d["auto_snipe_locked"] is False


def test_bankroll_reset_wipes_open(s):
    # reset starts clean
    s.put(f"{API}/bankroll", json={"initial_sol": 10.0})
    # Create a position
    live = s.get(f"{API}/tokens/live", params={"limit": 3}, timeout=60).json()
    if not live["tokens"]:
        pytest.skip("no tokens")
    t = live["tokens"][0]
    s.post(f"{API}/portfolio/buy", json={
        "token_address": t["address"], "symbol": t["symbol"], "name": t["name"],
        "price_usd": t.get("price_usd") or 0.0001, "amount_sol": 0.5, "source": "manual",
    })
    open_before = s.get(f"{API}/portfolio/positions", params={"status": "open"}).json()["positions"]
    assert len(open_before) >= 1

    r = s.post(f"{API}/bankroll/reset")
    assert r.status_code == 200
    bk = r.json()
    assert bk["balance_sol"] == bk["initial_sol"]
    open_after = s.get(f"{API}/portfolio/positions", params={"status": "open"}).json()["positions"]
    assert len(open_after) == 0


def test_portfolio_buy_deducts_bankroll_and_source(s):
    s.post(f"{API}/bankroll/reset")
    before = s.get(f"{API}/bankroll").json()["balance_sol"]
    live = s.get(f"{API}/tokens/live", params={"limit": 3}, timeout=60).json()
    if not live["tokens"]:
        pytest.skip("no tokens")
    t = live["tokens"][0]
    payload = {
        "token_address": t["address"], "symbol": t["symbol"], "name": t["name"],
        "price_usd": t.get("price_usd") or 0.0001, "amount_sol": 1.0, "source": "manual",
    }
    rb = s.post(f"{API}/portfolio/buy", json=payload)
    assert rb.status_code == 200
    pos = rb.json()
    assert pos["source"] == "manual"
    after = s.get(f"{API}/bankroll").json()["balance_sol"]
    assert abs((before - after) - 1.0) < 1e-6


def test_portfolio_buy_insufficient_balance(s):
    s.put(f"{API}/bankroll", json={"initial_sol": 0.5})
    live = s.get(f"{API}/tokens/live", params={"limit": 3}, timeout=60).json()
    if not live["tokens"]:
        pytest.skip("no tokens")
    t = live["tokens"][0]
    r = s.post(f"{API}/portfolio/buy", json={
        "token_address": t["address"], "symbol": t["symbol"], "name": t["name"],
        "price_usd": t.get("price_usd") or 0.0001, "amount_sol": 10.0, "source": "manual",
    })
    assert r.status_code == 400
    assert "insufficient" in r.text.lower()
    # cleanup
    s.post(f"{API}/bankroll/reset")
    s.put(f"{API}/bankroll", json={"initial_sol": 10.0})


def test_portfolio_close_credits_bankroll(s):
    s.post(f"{API}/bankroll/reset")
    live = s.get(f"{API}/tokens/live", params={"limit": 3}, timeout=60).json()
    if not live["tokens"]:
        pytest.skip("no tokens")
    t = live["tokens"][0]
    buy = s.post(f"{API}/portfolio/buy", json={
        "token_address": t["address"], "symbol": t["symbol"], "name": t["name"],
        "price_usd": t.get("price_usd") or 0.0001, "amount_sol": 1.0, "source": "manual",
    }).json()
    bal_after_buy = s.get(f"{API}/bankroll").json()["balance_sol"]
    rc = s.post(f"{API}/portfolio/close", json={
        "position_id": buy["id"],
        "exit_price_usd": (t.get("price_usd") or 0.0001) * 2.0,
    })
    assert rc.status_code == 200
    closed = rc.json()
    assert closed["status"] == "closed"
    assert closed["pnl_sol"] is not None
    bal_after_close = s.get(f"{API}/bankroll").json()["balance_sol"]
    # 2x exit => should credit ~2 SOL
    assert bal_after_close > bal_after_buy + 1.5


def test_partial_close_tp1(s):
    s.post(f"{API}/bankroll/reset")
    live = s.get(f"{API}/tokens/live", params={"limit": 3}, timeout=60).json()
    if not live["tokens"]:
        pytest.skip("no tokens")
    t = live["tokens"][0]
    buy = s.post(f"{API}/portfolio/buy", json={
        "token_address": t["address"], "symbol": t["symbol"], "name": t["name"],
        "price_usd": t.get("price_usd") or 0.0001, "amount_sol": 1.0, "source": "manual",
    }).json()
    r = s.post(f"{API}/portfolio/partial-close", json={
        "position_id": buy["id"], "sell_pct": 25, "exit_price_usd": (t.get("price_usd") or 0.0001) * 1.5,
        "tp_tag": "tp1",
    })
    assert r.status_code == 200
    p = r.json()
    assert p["status"] == "open"
    assert "tp1" in p["tp_hits"]
    assert p["tokens_remaining"] < buy["tokens"]
    assert p["tokens_remaining"] > 0


def test_portfolio_stats_new_fields(s):
    r = s.get(f"{API}/portfolio/stats")
    assert r.status_code == 200
    st = r.json()
    for k in ("bankroll_sol", "initial_sol", "daily_pnl_sol", "daily_pnl_pct", "by_source", "auto_snipe_locked"):
        assert k in st


def test_trade_log(s):
    r = s.get(f"{API}/portfolio/trade-log")
    assert r.status_code == 200
    assert "log" in r.json()


def test_engine_status(s):
    r = s.get(f"{API}/engine/status")
    assert r.status_code == 200
    d = r.json()
    for k in ("auto_snipe_enabled", "auto_sell_enabled", "auto_snipe_locked", "events"):
        assert k in d
    assert isinstance(d["events"], list)


def test_settings_auto_snipe_fields_and_event(s):
    # Clean slate
    s.post(f"{API}/bankroll/reset")
    cur = s.get(f"{API}/settings").json()
    cur.update({
        "auto_snipe_enabled": True,
        "auto_snipe_amount_sol": 0.3,
        "auto_snipe_min_score": 70,
        "auto_snipe_min_liq_usd": 5000.0,
        "auto_snipe_max_age_min": 2000.0,
        "auto_sell_enabled": True,
        "max_open_positions": 10,
    })
    ru = s.put(f"{API}/settings", json=cur)
    assert ru.status_code == 200
    assert ru.json()["auto_snipe_enabled"] is True

    st = s.get(f"{API}/engine/status").json()
    assert st["auto_snipe_enabled"] is True

    # Wait for auto-snipe loop to pick up (loop has 8s init + 30s cycles)
    deadline = time.time() + 50
    sniped = False
    while time.time() < deadline:
        ev = s.get(f"{API}/engine/status").json().get("events", [])
        if any(e.get("kind") == "auto_snipe_buy" for e in ev):
            sniped = True
            break
        time.sleep(3)

    # Disable to prevent further snipes
    cur["auto_snipe_enabled"] = False
    s.put(f"{API}/settings", json=cur)

    assert sniped, "no auto_snipe_buy event observed within 50s"
    open_pos = s.get(f"{API}/portfolio/positions", params={"status": "open"}).json()["positions"]
    assert any(p.get("source") == "auto_snipe" for p in open_pos)


def test_disable_auto_snipe_stops(s):
    cur = s.get(f"{API}/settings").json()
    cur["auto_snipe_enabled"] = False
    s.put(f"{API}/settings", json=cur)
    st = s.get(f"{API}/engine/status").json()
    assert st["auto_snipe_enabled"] is False
    # cleanup for subsequent tests
    s.post(f"{API}/bankroll/reset")
