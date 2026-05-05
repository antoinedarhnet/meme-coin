# 🔧 New Pairs Pipeline - Complete Debug Kit

> **Problem:** `/new-pairs` page shows 0 results  
> **Solution:** Implemented complete logging + debugging tools  
> **Status:** ✅ Ready to test

## 📚 START HERE

1. **Quick Start (2 min):** Read [QUICKSTART_DEBUG.md](QUICKSTART_DEBUG.md)
2. **Full Report (5 min):** Read [COMPLETE_EXECUTION_REPORT.md](COMPLETE_EXECUTION_REPORT.md)
3. **Run Test (1 min):** `bash test_new_pairs.sh`
4. **See Results:** `curl http://localhost:8000/api/debug/new-pairs | jq '.'`

## ⚡ TL;DR

```bash
# Enable debug mode
export DEBUG_FILTERS=true

# Restart backend
docker restart <container>

# Test
bash test_new_pairs.sh

# Check results
curl -s http://localhost:8000/api/tokens/new-pairs | jq '.count'
```

## 📖 Documentation

| Document | Purpose |
|----------|---------|
| [QUICKSTART_DEBUG.md](QUICKSTART_DEBUG.md) | **START HERE** - Quick diagnostics |
| [COMPLETE_EXECUTION_REPORT.md](COMPLETE_EXECUTION_REPORT.md) | Full summary of changes |
| [DEBUG_NEW_PAIRS.md](DEBUG_NEW_PAIRS.md) | Detailed debugging guide |
| [EXPECTED_LOGS.md](EXPECTED_LOGS.md) | What logs should look like |
| [EXECUTION_SUMMARY.md](EXECUTION_SUMMARY.md) | List of code changes |
| [FILES_REFERENCE.md](FILES_REFERENCE.md) | Where to find everything |
| [curl_commands.sh](curl_commands.sh) | Copy-paste curl commands |

## 🧪 Tools

- **[test_new_pairs.sh](test_new_pairs.sh)** - Automated test (run this first)
- **[curl_commands.sh](curl_commands.sh)** - Manual testing commands
- **[backend/.env.example](backend/.env.example)** - Configuration template
- **[backend/README_NEW_PAIRS.md](backend/README_NEW_PAIRS.md)** - Backend guide

## ✅ What Was Fixed

- ✅ Added verbose logging at every pipeline step
- ✅ Enhanced `/api/debug/new-pairs` endpoint
- ✅ Created `DEBUG_FILTERS` mode for testing filters
- ✅ Improved frontend error messages
- ✅ Created automated test script
- ✅ Comprehensive documentation

## 🚀 Verify It Works

```bash
# 1. Run test script
bash test_new_pairs.sh

# 2. Check debug dashboard
curl -s http://localhost:8000/api/debug/new-pairs | jq '.buffer.size'

# 3. Check tokens endpoint
curl -s http://localhost:8000/api/tokens/new-pairs | jq '.count'

# 4. Visit frontend
# http://localhost:3000/new-pairs
# Should show token list
```

## 📞 Having Issues?

1. Read [QUICKSTART_DEBUG.md](QUICKSTART_DEBUG.md) - "Most Likely Problems"
2. Run `bash test_new_pairs.sh` for automated diagnosis
3. Check [DEBUG_NEW_PAIRS.md](DEBUG_NEW_PAIRS.md) for detailed guide
4. See [EXPECTED_LOGS.md](EXPECTED_LOGS.md) for log examples

## 🔍 Key Endpoints

- **Debug Dashboard:** `http://localhost:8000/api/debug/new-pairs`
- **New Pairs:** `http://localhost:8000/api/tokens/new-pairs`
- **Engine Status:** `http://localhost:8000/api/engine/new-pairs/status`

## 📊 Files Modified

```
backend/services/new_pairs/ingestion.py  ← Enhanced logging
backend/services/new_pairs/filters.py    ← DEBUG_FILTERS mode
backend/server.py                        ← Improved endpoints
frontend/src/pages/NewPairs.jsx          ← Better errors
```

## ✨ Quick Commands

```bash
# Enable debug
export DEBUG_FILTERS=true

# Test everything
bash test_new_pairs.sh

# See debug info
curl http://localhost:8000/api/debug/new-pairs | jq '.'

# See tokens
curl http://localhost:8000/api/tokens/new-pairs

# View logs
docker logs -f <container> 2>&1 | grep -i "new-pairs"
```

## 🎯 Next Steps

1. Read [QUICKSTART_DEBUG.md](QUICKSTART_DEBUG.md)
2. Run `bash test_new_pairs.sh`
3. If issues, follow the troubleshooting guide
4. Deploy when working

---

**Status:** ✅ Complete & Ready  
**Last Updated:** 2026-05-05  
**Support:** See documentation files above
