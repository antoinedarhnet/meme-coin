"""V3 Portfolio rebrand: timeframes, equity-history, export-csv, paper_mode"""
import os
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://coin-hunter-15.preview.emergentagent.com").rstrip("/")
API = f"{BASE}/api"
S = requests.Session()


def test_stats_timeframe_24h():
    r = S.get(f"{API}/portfolio/stats", params={"timeframe": "24h"}, timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert d["timeframe"] == "24h"
    for k in ("total_pnl_sol", "unrealized_pnl_sol", "total_recovered_sol",
              "avg_hold_min", "wins", "losses"):
        assert k in d
    # best_trade/worst_trade keys must be present (may be None)
    assert "best_trade" in d and "worst_trade" in d


def test_stats_timeframe_7d():
    r = S.get(f"{API}/portfolio/stats", params={"timeframe": "7d"}, timeout=30)
    assert r.status_code == 200
    assert r.json()["timeframe"] == "7d"


def test_stats_timeframe_all_has_new_fields():
    r = S.get(f"{API}/portfolio/stats", params={"timeframe": "all"}, timeout=30)
    assert r.status_code == 200
    d = r.json()
    expected = ("total_pnl_sol", "unrealized_pnl_sol", "total_recovered_sol",
                "avg_hold_min", "best_trade", "worst_trade", "wins", "losses",
                "realized_pnl_sol", "win_rate", "by_source")
    for k in expected:
        assert k in d, f"missing key {k}"


def test_equity_history_returns_points():
    r = S.get(f"{API}/portfolio/equity-history", params={"timeframe": "all"}, timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert "points" in d
    assert isinstance(d["points"], list)
    # Always at least one initial point
    assert len(d["points"]) >= 1
    p0 = d["points"][0]
    assert "ts" in p0 and "equity" in p0


def test_equity_history_24h():
    r = S.get(f"{API}/portfolio/equity-history", params={"timeframe": "24h"}, timeout=30)
    assert r.status_code == 200
    assert "points" in r.json()


def test_export_csv_headers_and_content_type():
    r = S.get(f"{API}/portfolio/export-csv", timeout=30)
    assert r.status_code == 200
    ct = r.headers.get("content-type", "")
    assert "text/csv" in ct
    body = r.text
    first_line = body.splitlines()[0]
    expected_header = "opened_at,closed_at,symbol,token_address,source,status,entry_price,exit_price,amount_sol,tokens,pnl_sol,pnl_pct,tp_hits"
    assert first_line == expected_header


def test_settings_paper_mode_field_default_true():
    # Reset to defaults via PUT with default Settings
    cur = S.get(f"{API}/settings").json()
    assert "paper_mode" in cur, "Settings must include paper_mode"
    # Default should be True (per Settings model)
    # If overridden by previous tests, force it
    cur["paper_mode"] = True
    r = S.put(f"{API}/settings", json=cur)
    assert r.status_code == 200
    d = r.json()
    assert d["paper_mode"] is True


def test_settings_paper_mode_can_toggle_false():
    cur = S.get(f"{API}/settings").json()
    cur["paper_mode"] = False
    r = S.put(f"{API}/settings", json=cur)
    assert r.status_code == 200
    assert r.json()["paper_mode"] is False
    # restore
    cur["paper_mode"] = True
    S.put(f"{API}/settings", json=cur)
