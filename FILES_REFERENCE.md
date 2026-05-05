# 📚 Files Reference Guide

## 📋 Where to Find What

### 🎯 **Quick Start (READ FIRST)**
- **[QUICKSTART_DEBUG.md](/QUICKSTART_DEBUG.md)** - 30-second diagnostic guide
  - Most likely problems & instant fixes
  - Run this first!

### 🧪 **Testing & Debugging**
- **[curl_commands.sh](/curl_commands.sh)** - Copy-paste ready curl commands
  - Test external APIs
  - Check backend endpoints
  - Quick health checks
  
- **[test_new_pairs.sh](/test_new_pairs.sh)** - Automated test script
  ```bash
  bash /app/test_new_pairs.sh
  ```
  - Tests all APIs and endpoints
  - Shows summary with diagnostics

### 📊 **Detailed Documentation**
- **[DEBUG_NEW_PAIRS.md](/DEBUG_NEW_PAIRS.md)** - Comprehensive debugging guide
  - All curl commands explained
  - Possible problems & solutions
  - Expected outputs for each scenario
  - Configuration options
  
- **[EXPECTED_LOGS.md](/EXPECTED_LOGS.md)** - What to look for in logs
  - Success case logs
  - Failure case examples
  - How to read each log message
  - Debug endpoint response examples

### 📝 **Technical Summary**
- **[EXECUTION_SUMMARY.md](/EXECUTION_SUMMARY.md)** - Complete list of changes
  - What was modified in each file
  - Why each change was made
  - Expected improvements
  
### ⚙️ **Configuration**
- **[backend/.env.example](/backend/.env.example)** - Environment variables
  - `DEBUG_FILTERS=true` - Enable debug mode
  - `NEW_PAIRS_FALLBACK_MAX_HOURS=24` - Age cutoff
  - Other options documented

---

## 🔧 Files Modified

### Backend Python Files

| File | Changes | Line Count |
|------|---------|-----------|
| `backend/services/new_pairs/ingestion.py` | ✅ Verbose logging at every step | +150 lines |
| `backend/services/new_pairs/filters.py` | ✅ DEBUG_FILTERS mode, detailed logs | +50 lines |
| `backend/server.py` | ✅ Enhanced /tokens/new-pairs + improved /debug/new-pairs | +80 lines |

### Frontend Files

| File | Changes |
|------|---------|
| `frontend/src/pages/NewPairs.jsx` | ✅ Better error messages, logging |

---

## 🚀 Quick Command Reference

### 1. Instant Health Check
```bash
bash /app/test_new_pairs.sh
```

### 2. View Debug Dashboard
```bash
curl -s http://localhost:8000/api/debug/new-pairs | jq '.'
```

### 3. View New Pairs
```bash
curl -s http://localhost:8000/api/tokens/new-pairs | jq '.count'
```

### 4. Enable Debug Mode
```bash
export DEBUG_FILTERS=true
# Restart backend
```

### 5. See Logs in Real-Time
```bash
docker logs <container> -f 2>&1 | grep -i "new-pairs\|fallback"
```

### 6. Run Test Script
```bash
bash /app/curl_commands.sh
```

---

## 📍 Key Endpoints

| Endpoint | Purpose | Example |
|----------|---------|---------|
| `/api/debug/new-pairs` | **Debug dashboard** - see buffer, rejections, stats | `curl http://localhost:8000/api/debug/new-pairs` |
| `/api/tokens/new-pairs` | Get tokens (what frontend uses) | `curl http://localhost:8000/api/tokens/new-pairs` |
| `/api/engine/new-pairs/status` | Engine status | `curl http://localhost:8000/api/engine/new-pairs/status` |

---

## 🔍 Problem Diagnosis Tree

```
Are you getting 0 tokens?
├─ YES → Check QUICKSTART_DEBUG.md
│        └─ "Problem 1: Buffer Empty" → Check if APIs work
│        └─ "Problem 2: All Rejected" → Reduce filter thresholds
│        └─ "Problem 3: RugCheck Fail" → Enable DEBUG_FILTERS=true
│
└─ NO (getting tokens) → You're done! ✅
```

---

## 📊 Expected Behavior

### ✅ WORKING:
```
curl http://localhost:8000/api/debug/new-pairs
{
  "buffer": {"size": 15},
  "fallback_dexscreener": {
    "last_poll_ago_sec": 5,
    "pushed_to_buffer": 15
  }
}

curl http://localhost:8000/api/tokens/new-pairs
{
  "count": 8,
  "tokens": [...],
  "meta": {"scanned": 15, "filtered": 7, "passed_scoring": 8}
}
```

### ❌ NOT WORKING:
```
curl http://localhost:8000/api/debug/new-pairs
{
  "buffer": {"size": 0},           ← Empty buffer!
  "fallback_dexscreener": {
    "pushed_to_buffer": 0          ← No data pushed!
  }
}
```

---

## 🎯 Troubleshooting Flowchart

1. **Run test script:** `bash /app/test_new_pairs.sh`
2. **Check DexScreener API:** `curl https://api.dexscreener.com/latest/dex/search?q=SOL | jq '.pairs | length'`
   - If 0 → API is down, system will retry
   - If > 0 → API works, check backend
3. **Check buffer:** `curl http://localhost:8000/api/debug/new-pairs | jq '.buffer.size'`
   - If 0 → Fallback loop not running or failed
   - If > 0 → Buffer works, check filters
4. **Check filters:** `curl http://localhost:8000/api/debug/new-pairs | jq '.rejections'`
   - See what's rejecting tokens
   - Enable `DEBUG_FILTERS=true` to see details
5. **Check endpoint:** `curl http://localhost:8000/api/tokens/new-pairs | jq '.count'`
   - Should show > 0

---

## 📚 Reading Order

### For Busy People (5 minutes)
1. [QUICKSTART_DEBUG.md](/QUICKSTART_DEBUG.md) - Read "Instant Diagnostics"
2. Run: `bash /app/test_new_pairs.sh`
3. Check: `curl http://localhost:8000/api/debug/new-pairs`

### For Thorough Understanding (30 minutes)
1. [QUICKSTART_DEBUG.md](/QUICKSTART_DEBUG.md) - Full guide
2. [DEBUG_NEW_PAIRS.md](/DEBUG_NEW_PAIRS.md) - Detailed explanations
3. [EXPECTED_LOGS.md](/EXPECTED_LOGS.md) - Log examples
4. Run tests and compare to expected output

### For Developers (1+ hour)
1. [EXECUTION_SUMMARY.md](/EXECUTION_SUMMARY.md) - What changed
2. Review code changes in modified files
3. [DEBUG_NEW_PAIRS.md](/DEBUG_NEW_PAIRS.md) - Deep dive
4. [EXPECTED_LOGS.md](/EXPECTED_LOGS.md) - Learn from examples
5. Edit filter thresholds as needed

---

## 🔐 Security Notes

- All `/api/debug/*` endpoints are for development
- In production, restrict access or remove
- Never commit real API keys to `.env.example`
- `DEBUG_FILTERS=true` should only be enabled during debugging

---

## 🚀 Deployment Checklist

- [ ] Tests pass: `bash test_new_pairs.sh` returns ✅
- [ ] `curl http://localhost:8000/api/tokens/new-pairs` returns tokens
- [ ] `DEBUG_FILTERS=false` in .env (disabled)
- [ ] Check backend logs for errors: no `[ERROR]` or `[CRITICAL]`
- [ ] Verify API rate limits haven't been hit
- [ ] Frontend shows tokens instead of "Stream interrupted"
- [ ] Fallback loop running: `last_poll_ago_sec < 15`

---

## 📞 Support Resources

| Issue | Check File | Section |
|-------|-----------|---------|
| "Stream interrupted" | QUICKSTART_DEBUG.md | Problem 3 |
| Buffer empty | DEBUG_NEW_PAIRS.md | Problèm 1 |
| No tokens returned | DEBUG_NEW_PAIRS.md | Problèm 2 |
| API not working | DEBUG_NEW_PAIRS.md | Curl Commands |
| Need example logs | EXPECTED_LOGS.md | Success/Failure Cases |
| Want to understand changes | EXECUTION_SUMMARY.md | Full details |

---

**Last Updated:** 2026-05-05  
**Status:** ✅ Complete documentation  
**Total Files:** 8 new/modified documentation files
