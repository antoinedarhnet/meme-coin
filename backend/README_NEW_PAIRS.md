# 🔍 New Pairs Pipeline - Debug & Fix Guide

**Problem:** Page `/new-pairs` shows 0 results with "Stream interrupted"

## 🚨 Quick Fix (2 minutes)

```bash
# 1. Enable debug mode
export DEBUG_FILTERS=true

# 2. Restart backend
docker restart <container_name>

# 3. Check health
bash /app/test_new_pairs.sh

# 4. View results
curl -s http://localhost:8000/api/tokens/new-pairs | jq '.count'
```

If you see tokens returned, the system is working! ✅

---

## 📊 Full Diagnosis (10 minutes)

### Step 1: Test External APIs

```bash
# DexScreener (main source)
curl -s "https://api.dexscreener.com/latest/dex/search?q=SOL" | jq '.pairs | length'

# Should return > 0. If 0, API is down.
```

### Step 2: Check Backend Buffer

```bash
# See what's in the buffer
curl -s http://localhost:8000/api/debug/new-pairs | jq '.buffer'

# Output should show:
# {
#   "size": 15,        ✅ Non-zero
#   "sample": [...]    ✅ Has data
# }
```

### Step 3: Check Why Tokens Are Rejected

```bash
# See rejection reasons
curl -s http://localhost:8000/api/debug/new-pairs | jq '.rejections.summary_by_reason'

# Common rejections:
# - "age_filter": 5           → Pairs older than max_age_min
# - "liquidity < 5 SOL": 12   → Low liquidity (MOST COMMON)
# - "< 15 txns in 5m": 8      → Low activity
# - "rugcheck_fetch_failed": 3 → RugCheck API error
```

### Step 4: Fix if Needed

If most rejections are "liquidity < 5 SOL" or similar:
```bash
# Edit filters.py to be less strict:
vim backend/services/new_pairs/filters.py

# Change:
# if liq is None or liq < 5:      # 5 SOL → 2 SOL
# if tx5 is None or tx5 < 15:     # 15 txns → 5 txns

# Restart:
docker restart <container>

# Retest:
curl -s http://localhost:8000/api/tokens/new-pairs | jq '.count'
```

---

## 🧪 Automated Testing

```bash
# Run complete test suite
bash /app/test_new_pairs.sh

# Expected output:
# ✅ DexScreener API returns 50 pairs
# ✅ Birdeye API returns 20 items
# ✅ Pump.fun API returns 30 coins
# ✅ Debug endpoint responds
#    Buffer size: 25
#    Fallback pushed to buffer: 25
# ✅ Endpoint returns results:
#    Tokens: 8
#    Scanned: 25
```

---

## 🔧 Configuration

Edit `backend/.env`:
```bash
# Enable verbose debug logging
DEBUG_FILTERS=true

# Set how old pairs can be (in hours)
NEW_PAIRS_FALLBACK_MAX_HOURS=24

# Set minimum score required
NEW_PAIRS_MIN_SCORE=60
```

---

## 📚 Documentation Files

| File | Purpose |
|------|---------|
| **[QUICKSTART_DEBUG.md](/QUICKSTART_DEBUG.md)** | 30-second diagnosis + fixes |
| **[DEBUG_NEW_PAIRS.md](/DEBUG_NEW_PAIRS.md)** | Detailed troubleshooting guide |
| **[curl_commands.sh](/curl_commands.sh)** | Ready-to-copy curl commands |
| **[EXPECTED_LOGS.md](/EXPECTED_LOGS.md)** | What logs should look like |
| **[EXECUTION_SUMMARY.md](/EXECUTION_SUMMARY.md)** | List of all code changes made |
| **[FILES_REFERENCE.md](/FILES_REFERENCE.md)** | Where to find everything |

---

## 🎯 Common Problems & Solutions

### Problem: Buffer Empty (size: 0)
**Cause:** Fallback polling not working  
**Fix:**
```bash
# Check if fallback loop is running
curl -s http://localhost:8000/api/debug/new-pairs | jq '.fallback_dexscreener.last_poll_ago_sec'

# Should be < 15. If null, loop isn't running.
# Check logs: docker logs <container> 2>&1 | grep -i fallback
```

### Problem: All Tokens Rejected
**Cause:** Filters too strict for fresh pairs  
**Fix:**
```bash
# Enable debug mode to see reasons
export DEBUG_FILTERS=true

# Reduce thresholds in filters.py:
# liquidity < 5 → < 2
# txns_5m < 15 → < 5
```

### Problem: "Stream interrupted" on Frontend
**Cause:** Backend returning 0 tokens  
**Fix:**
1. Run: `bash test_new_pairs.sh`
2. Check which step fails
3. See relevant section above

---

## 📋 Checklist: Is It Working?

- [ ] `curl http://localhost:8000/api/debug/new-pairs | jq '.buffer.size'` returns > 0
- [ ] `curl http://localhost:8000/api/tokens/new-pairs | jq '.count'` returns > 0
- [ ] Frontend page `/new-pairs` shows tokens
- [ ] No "Stream interrupted" error
- [ ] Fallback polling running (last_poll_ago_sec < 15)

If all ✅, you're good to go!

---

## 🔍 Advanced Debugging

### See All Logs
```bash
docker logs <container> -f 2>&1 | grep -i "new-pairs\|fallback\|error"
```

### Test Each Component
```bash
# Just the enrichment
curl http://localhost:8000/api/debug/new-pairs | jq '.buffer.sample[0]'

# Just the filtration
curl http://localhost:8000/api/debug/new-pairs | jq '.rejections'

# Just the scoring
curl http://localhost:8000/api/tokens/new-pairs | jq '.tokens[0].score'
```

### Monitor in Real-Time
```bash
watch -n 3 'curl -s http://localhost:8000/api/debug/new-pairs | jq ".buffer.size, .fallback_dexscreener.last_poll_ago_sec"'
```

---

## 📞 Still Stuck?

1. Read: [QUICKSTART_DEBUG.md](/QUICKSTART_DEBUG.md)
2. Run: `bash /app/test_new_pairs.sh`
3. Check: `curl http://localhost:8000/api/debug/new-pairs | jq '.'`
4. Look up your error in [DEBUG_NEW_PAIRS.md](/DEBUG_NEW_PAIRS.md)
5. See examples in [EXPECTED_LOGS.md](/EXPECTED_LOGS.md)

---

## ✅ Verification Steps

After fixing:
```bash
# 1. Test passes
bash /app/test_new_pairs.sh

# 2. Backend returns tokens
curl -s http://localhost:8000/api/tokens/new-pairs | jq '.count'

# 3. Buffer has data
curl -s http://localhost:8000/api/debug/new-pairs | jq '.buffer.size'

# 4. Fallback is running
curl -s http://localhost:8000/api/debug/new-pairs | jq '.fallback_dexscreener.last_poll_ago_sec'

# 5. Frontend shows tokens
# Visit http://localhost:3000/new-pairs - should show token list
```

---

**Last Updated:** 2026-05-05  
**Status:** 🟢 Ready for production testing  
**Support:** See documentation files listed above
