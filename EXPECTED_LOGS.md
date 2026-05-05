# 📝 Expected Logs - New Pairs Pipeline

## ✅ SUCCESS CASE: Everything Working

### At Startup (first 5-10 seconds)
```
2026-05-05 10:00:00 - INFO - [FALLBACK LOOP] Starting fallback_poll_loop
2026-05-05 10:00:02 - INFO - [FALLBACK] === Polling DexScreener search ===
2026-05-05 10:00:02 - DEBUG - [FALLBACK] GET https://api.dexscreener.com/latest/dex/search params={'q': 'SOL'}
2026-05-05 10:00:03 - INFO - [FALLBACK] Got 50 pairs from API
2026-05-05 10:00:03 - INFO - [FALLBACK] After age filter: 12 pairs
2026-05-05 10:00:03 - INFO - [FALLBACK] Rejection reasons: {'not_solana': 20, 'too_old': 18}
2026-05-05 10:00:03 - INFO - [FALLBACK] Pushed 12 to buffer
2026-05-05 10:00:03 - DEBUG - [FALLBACK] Buffered PUMP/9xQeKq5euS5g5BVT9NsWkVbuDw8d7KZGWKYqunTag2mK age=3.2min liq=45000
2026-05-05 10:00:03 - DEBUG - [FALLBACK] Buffered DOGE/5tqbYvpYhv2y8RmY7x5sJnKkQjY7pzMgXqXqc8zQvDYj age=8.1min liq=32000
...
2026-05-05 10:00:04 - INFO - [FALLBACK] === Polling Birdeye new listing ===
2026-05-05 10:00:04 - INFO - [FALLBACK] Got 20 items from Birdeye
2026-05-05 10:00:04 - INFO - [FALLBACK] Birdeye pushed 5 to buffer
2026-05-05 10:00:04 - INFO - [FALLBACK] === Polling Pump.fun frontend ===
2026-05-05 10:00:05 - INFO - [FALLBACK] Got 50 coins from Pump.fun
2026-05-05 10:00:05 - INFO - [FALLBACK] Pump.fun pushed 8 to buffer
2026-05-05 10:00:05 - INFO - [FALLBACK LOOP] Buffer now has 25 candidates
```

### When User Calls /tokens/new-pairs
```
2026-05-05 10:00:20 - INFO - [NEW-PAIRS] === Endpoint called: max_age_min=60, limit=40 ===
2026-05-05 10:00:20 - INFO - [NEW-PAIRS] Sources enabled: {'pumpfun': True, 'raydium': True, 'dexscreener': True, 'birdeye': False}
2026-05-05 10:00:20 - INFO - [NEW-PAIRS] Got 25 candidates from fetch_all
2026-05-05 10:00:20 - DEBUG - [NEW-PAIRS] Enriching 9xQeKq5euS5g5BVT9NsWkVbuDw8d7KZGWKYqunTag2mK from dexscreener_search
2026-05-05 10:00:21 - DEBUG - [NEW-PAIRS] Enriched PUMP: liq=45000, price=0.000234
2026-05-05 10:00:21 - DEBUG - [NEW-PAIRS] PUMP passed age filter: 3.2min
2026-05-05 10:00:21 - DEBUG - [NEW-PAIRS] Metrics for PUMP: {'liquidity_sol': 250, 'volume_5m_sol': 12, 'txns_5m': 45, 'buy_sell_ratio': 1.8}
2026-05-05 10:00:22 - DEBUG - [NEW-PAIRS] PUMP passed filters!
2026-05-05 10:00:22 - DEBUG - [NEW-PAIRS] PUMP score=72
2026-05-05 10:00:22 - INFO - [NEW-PAIRS] DOGE passed filters!
2026-05-05 10:00:22 - DEBUG - [NEW-PAIRS] DOGE score=65
2026-05-05 10:00:22 - INFO - [NEW-PAIRS] Rejected 9xQeKq5euS5g5BVT9NsWkVbuDw8d7KZGWKYqunTag2mK: rugcheck_fetch_failed
2026-05-05 10:00:24 - INFO - [NEW-PAIRS] FINAL: scanned=25 filtered=18 scored=7 returned=7 | 
        Reasons: {'age_filter': 5, 'liquidity < 5 SOL': 8, 'rugcheck_fetch_failed': 5}
```

---

## ❌ FAILURE CASE 1: Fallback Loop Not Running

### Symptom
```
Buffer has size 0
last_fallback_poll_ms is null
No [FALLBACK] logs appear
```

### Logs (Bad)
```
2026-05-05 10:00:00 - INFO - [FALLBACK LOOP] Starting fallback_poll_loop
2026-05-05 10:00:10 - ERROR - [FALLBACK LOOP] error: ... (exc_info shows stack trace)
```

### Fix
- Check if `fallback_poll_loop()` is called in `start_engines()`
- Verify `await _new_pairs_ingestor.fallback_poll_loop()` in server.py startup
- Look at exception in stack trace

---

## ❌ FAILURE CASE 2: DexScreener API Down

### Symptom
```
Buffer has size 0
fallback_dexscreener.last_response_count = 0
No DOGE/PUMP/etc tokens in sample
```

### Logs (Bad)
```
2026-05-05 10:00:03 - INFO - [FALLBACK] === Polling DexScreener search ===
2026-05-05 10:00:03 - ERROR - [FALLBACK] DexScreener fetch failed: ConnectionError: Max retries exceeded
2026-05-05 10:00:03 - INFO - [FALLBACK] Got 0 pairs from API
```

### Fix
- Test DexScreener API: `curl https://api.dexscreener.com/latest/dex/search?q=SOL`
- If fails, API is down - it will retry in 10s
- Should fallback to Birdeye/Pump.fun instead

---

## ❌ FAILURE CASE 3: All Tokens Rejected by Filters

### Symptom
```
buffer.size = 25          ✅ Buffer has data
count = 0                 ❌ But no tokens returned
meta.scanned = 25         ✅ Scanned 25
meta.filtered = 23        ✅ Rejected 23
meta.passed_scoring = 2   ❌ Only 2 passed
returned = 0              ❌ But score < 60 so rejected
```

### Logs (if no DEBUG_FILTERS)
```
2026-05-05 10:00:20 - INFO - [NEW-PAIRS] FINAL: scanned=25 filtered=23 scored=2 returned=0 | 
        Reasons: {'liquidity < 5 SOL': 15, '< 15 txns in 5m': 8}
```

### Logs (if DEBUG_FILTERS=true)
```
2026-05-05 10:00:21 - DEBUG - [NEW-PAIRS] Metrics: {'liquidity_sol': 2.5, 'volume_5m_sol': 0.5, 'txns_5m': 3, ...}
2026-05-05 10:00:21 - WARNING - [DEBUG_FILTERS] liq=2.5 vol5=0.5 tx5=3 bs=1.1
2026-05-05 10:00:21 - WARNING - [DEBUG_FILTERS] WARN: liquidity < 5 SOL (value=2.5)
2026-05-05 10:00:21 - WARNING - [DEBUG_FILTERS] WARN: 5m volume < 2 SOL (value=0.5)
2026-05-05 10:00:21 - WARNING - [DEBUG_FILTERS] WARN: < 15 txns in 5m (value=3)
2026-05-05 10:00:21 - WARNING - [DEBUG_FILTERS] WARN: buy/sell ratio <= 1.2 (value=1.1)
```

### Fix
- Reduce thresholds in `filters.py`:
  ```python
  if liq is None or liq < 2:      # Was 5
  if vol5 is None or vol5 < 1:    # Was 2
  if tx5 is None or tx5 < 5:      # Was 15
  if bs is None or bs <= 1.0:     # Was 1.2
  ```

---

## ❌ FAILURE CASE 4: RugCheck API Errors

### Symptom
```
meta.filtered_reasons: {'rugcheck_fetch_failed': 20}
Most tokens rejected due to RugCheck
```

### Logs
```
2026-05-05 10:00:21 - WARNING - [NEW-PAIRS] RugCheck failed for PUMP: HTTPError 429 Too Many Requests
2026-05-05 10:00:21 - DEBUG - [NEW-PAIRS] Rejected 9xQeKq...: rugcheck_fetch_failed
```

### Fix
- RugCheck API is rate-limited or down
- Option 1: Add retry logic with backoff
- Option 2: Skip RugCheck if timeout
- Option 3: Use Birdeye/other sources for security checks

---

## 📊 Debug Endpoint Response Examples

### ✅ Healthy State
```json
{
  "buffer": {
    "size": 23,
    "sample": [
      {
        "source": "dexscreener_search",
        "token_address": "9xQeKq...",
        "created_at_ms": 1714956000000
      }
    ]
  },
  "webhook": {
    "received_count": 0,
    "last_received_ms": null
  },
  "fallback_dexscreener": {
    "last_poll_ago_sec": 3.5,       ✅ < 15 seconds = working
    "last_response_count": 50,       ✅ Got data from API
    "after_age_filter": 12,          ✅ Passed age check
    "pushed_to_buffer": 12           ✅ Added to buffer
  },
  "rejections": {
    "summary_by_reason": {
      "age_filter": 5,
      "liquidity < 5 SOL": 8
    }
  }
}
```

### ❌ Fallback Not Running
```json
{
  "buffer": {"size": 0},             ❌ Empty!
  "fallback_dexscreener": {
    "last_poll_ms": null,            ❌ Never ran
    "last_poll_ago_sec": null,
    "pushed_to_buffer": 0            ❌ Nothing pushed
  }
}
```

### ❌ API Returns 0 Data
```json
{
  "fallback_dexscreener": {
    "last_response_count": 0,        ❌ API returned nothing
    "after_age_filter": 0,           ❌ No candidates passed age
    "pushed_to_buffer": 0            ❌ Nothing in buffer
  }
}
```

---

## 🎯 How to Read Logs

### Key Patterns to Look For

✅ **GOOD Signs:**
- `[FALLBACK] Got X pairs from API` where X > 0
- `[FALLBACK] After age filter: Y pairs` where Y > 0
- `[FALLBACK] Pushed Z to buffer` where Z > 0
- `Buffer now has W candidates` where W > 0
- `FINAL: scanned=X filtered=Y scored=Z` where Z > 0

❌ **BAD Signs:**
- `[FALLBACK] Got 0 pairs from API` → API problem
- `[FALLBACK LOOP] error:` → exception in polling loop
- `DexScreener fetch failed:` → API down or rate-limited
- `[NEW-PAIRS] FINAL: ... returned=0` → filters too strict
- `Buffer now has 0 candidates` → nothing to process

### Filter Rejection Logs (with DEBUG_FILTERS=true)
```
[DEBUG_FILTERS] liq=1.5 vol5=0.3 tx5=2 bs=1.1
[DEBUG_FILTERS] WARN: liquidity < 5 SOL (value=1.5)    ← Reason for rejection
[DEBUG_FILTERS] WARN: 5m volume < 2 SOL (value=0.3)    ← Another reason
[DEBUG_FILTERS] WARN: < 15 txns in 5m (value=2)         ← Another reason
```

---

## 🚀 Testing Checklist

- [ ] See `[FALLBACK LOOP] Starting` at startup
- [ ] See `[FALLBACK] Got X pairs` every 10-15s
- [ ] See `[FALLBACK] Pushed Y to buffer` with Y > 0
- [ ] `curl /api/debug/new-pairs` shows `buffer.size > 0`
- [ ] `curl /api/tokens/new-pairs` returns tokens
- [ ] Frontend shows tokens instead of "Stream interrupted"

---

**Created:** 2026-05-05  
**Version:** 1.0  
**Status:** ✅ Complete logging specification
