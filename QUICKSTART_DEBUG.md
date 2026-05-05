# 🔍 Quick Start: New Pairs Debug

**Problem:** Page `/new-pairs` shows 0 results + "Stream interrupted"

## ⚡ Instant Diagnostics (30 seconds)

```bash
# Run automated test script
bash /app/test_new_pairs.sh

# View debug dashboard
curl -s http://localhost:8000/api/debug/new-pairs | jq '.'

# View new pairs (should return tokens)
curl -s http://localhost:8000/api/tokens/new-pairs | jq '.count'
```

## 🎯 Most Likely Problems & Fixes

### Problem 1: Buffer Empty (buffer.size = 0)
**Fix:** Fallback polling isn't working
```bash
# Check if DexScreener API works
curl -s "https://api.dexscreener.com/latest/dex/search?q=SOL" | jq '.pairs | length'

# Should return > 0. If 0, API is down.
```

### Problem 2: 0 Tokens Returned (but buffer has data)
**Fix:** Filters are too strict
```bash
# Enable debug mode (warn instead of reject):
export DEBUG_FILTERS=true

# Restart backend
# Then check what's being rejected:
curl -s http://localhost:8000/api/debug/new-pairs | jq '.rejections.summary_by_reason'
```

### Problem 3: RugCheck Failures
**Fix:** RugCheck API might be slow/down
```bash
# Skip RugCheck check temporarily:
# Edit filters.py: catch rugcheck errors and pass
# Or: add timeout parameter
```

## 📋 Full Debugging Steps

1. **Check if APIs work:**
   ```bash
   # DexScreener (main source)
   curl -s "https://api.dexscreener.com/latest/dex/search?q=SOL" | jq '.pairs[0:2]'
   
   # Birdeye (backup)
   curl -s "https://public-api.birdeye.so/defi/v2/tokens/new_listing" | jq '.data[0:2]'
   
   # Pump.fun (backup)
   curl -s "https://frontend-api.pump.fun/coins?offset=0&limit=5" | jq '.coins[0:2]'
   ```

2. **Enable verbose logging:**
   ```bash
   # In backend/.env
   DEBUG_FILTERS=true
   LOG_LEVEL=DEBUG
   
   # Restart backend
   ```

3. **Watch the logs:**
   ```bash
   # Terminal 1: See all new-pairs logs
   docker logs <container> -f 2>&1 | grep -i "new-pairs\|fallback"
   
   # Terminal 2: Call the endpoint
   curl -s http://localhost:8000/api/tokens/new-pairs | jq '.'
   ```

4. **Check rejection reasons:**
   ```bash
   curl -s http://localhost:8000/api/debug/new-pairs | jq '.rejections.summary_by_reason'
   
   # Most likely:
   # - "age_filter": pairs older than max_age_min
   # - "liquidity < 5 SOL": pairs with low liquidity
   # - "< 15 txns in 5m": pairs with low activity
   # - "rugcheck_fetch_failed": RugCheck API error
   ```

5. **Reduce filter thresholds (if needed):**
   ```python
   # In backend/services/new_pairs/filters.py
   
   # Current (very strict for fresh pairs):
   if liq is None or liq < 5:  # 5 SOL minimum
   if tx5 is None or tx5 < 15:  # 15 txns minimum
   
   # Less strict:
   if liq is None or liq < 2:  # 2 SOL minimum
   if tx5 is None or tx5 < 5:   # 5 txns minimum
   ```

## 📊 Expected Output

### ✅ All Good
```json
{
  "buffer": {"size": 25},
  "fallback_dexscreener": {
    "last_poll_ago_sec": 3,      // <15s = OK
    "pushed_to_buffer": 25        // >0 = OK
  },
  "tokens": [...],                // Should have items
  "count": 8                       // >0 = OK
}
```

### ❌ Problem: Buffer Empty
```json
{
  "buffer": {"size": 0},          // ❌ Empty!
  "fallback_dexscreener": {
    "pushed_to_buffer": 0         // ❌ No data pushed
  }
}
```
→ DexScreener API down OR fallback loop not running

### ❌ Problem: Buffer Full but No Tokens
```json
{
  "buffer": {"size": 25},         // ✅ Has data
  "tokens": [],                   // ❌ But 0 returned!
  "rejections": {
    "summary_by_reason": {
      "liquidity < 5 SOL": 20,
      "< 15 txns in 5m": 5
    }
  }
}
```
→ Filters too strict. Reduce thresholds or enable DEBUG_FILTERS

## 🔧 Configuration Files

| File | Purpose |
|------|---------|
| `backend/.env.example` | All env vars with DEBUG_FILTERS option |
| `DEBUG_NEW_PAIRS.md` | Detailed curl commands and examples |
| `EXECUTION_SUMMARY.md` | Full list of changes made |
| `test_new_pairs.sh` | Automated test script |

## 🚀 Deploy After Fix

```bash
# 1. Verify with test script
bash /app/test_new_pairs.sh

# 2. Disable debug mode
# In backend/.env:
DEBUG_FILTERS=false

# 3. Restart backend
docker restart <container>

# 4. Verify from UI
# Visit /new-pairs page - should show tokens
```

## 💡 Pro Tips

- **Check logs first:** `docker logs <container> 2>&1 | tail -100`
- **Use debug endpoint:** Much faster than frontend
- **Test APIs directly:** Isolate whether it's backend or API issue
- **Enable DEBUG_FILTERS=true:** See what filters reject
- **Check buffer sample:** `curl http://localhost:8000/api/debug/new-pairs | jq '.buffer.sample'`

## 📞 Still Stuck?

1. Check `DEBUG_NEW_PAIRS.md` for detailed examples
2. Review `EXECUTION_SUMMARY.md` for what was changed
3. Look at recent commits/changes in git
4. Check if external APIs are rate-limited or down

---

**Last Updated:** 2026-05-05  
**Status:** 🟢 All debug tools in place
