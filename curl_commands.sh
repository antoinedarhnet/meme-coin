#!/bin/bash
# 🔧 Copy-Paste Curl Commands for New Pairs Debug
# All URLs assume backend running on http://localhost:8000

# ============= TEST EXTERNAL APIs =============

echo "=== Testing DexScreener API ==="
curl -s "https://api.dexscreener.com/latest/dex/search?q=SOL" | jq '{pairs_count: (.pairs | length), sample: .pairs[0]}'

echo ""
echo "=== Testing Birdeye API ==="
curl -s "https://public-api.birdeye.so/defi/v2/tokens/new_listing" | jq '{count: (.data | length), sample: .data[0]}'

echo ""
echo "=== Testing Pump.fun API ==="
curl -s "https://frontend-api.pump.fun/coins?offset=0&limit=50&sort=created_timestamp" | jq '{count: (.coins | length), sample: .coins[0]}'

# ============= TEST BACKEND ENDPOINTS =============

echo ""
echo ""
echo "=== Backend Health ==="
curl -s "http://localhost:8000/api/" | jq '.'

echo ""
echo "=== Debug Dashboard (Most Important) ==="
curl -s "http://localhost:8000/api/debug/new-pairs" | jq '.'

echo ""
echo "=== Debug - Just Buffer Status ==="
curl -s "http://localhost:8000/api/debug/new-pairs" | jq '.buffer'

echo ""
echo "=== Debug - Just Fallback Status ==="
curl -s "http://localhost:8000/api/debug/new-pairs" | jq '.fallback_dexscreener'

echo ""
echo "=== Debug - Just Rejections ==="
curl -s "http://localhost:8000/api/debug/new-pairs" | jq '.rejections'

echo ""
echo "=== New Pairs Endpoint (Main) ==="
curl -s "http://localhost:8000/api/tokens/new-pairs?max_age_min=60&limit=10" | jq '.'

echo ""
echo "=== New Pairs - Just Count ==="
curl -s "http://localhost:8000/api/tokens/new-pairs?max_age_min=60&limit=10" | jq '.count'

echo ""
echo "=== New Pairs - Just Meta ==="
curl -s "http://localhost:8000/api/tokens/new-pairs?max_age_min=60&limit=10" | jq '.meta'

echo ""
echo "=== New Pairs - First Token ==="
curl -s "http://localhost:8000/api/tokens/new-pairs?max_age_min=60&limit=10" | jq '.tokens[0]'

echo ""
echo "=== Engine Status ==="
curl -s "http://localhost:8000/api/engine/new-pairs/status" | jq '.'

# ============= QUICK HEALTH CHECK =============

echo ""
echo ""
echo "=== QUICK HEALTH CHECK ==="
BUFFER_SIZE=$(curl -s "http://localhost:8000/api/debug/new-pairs" | jq '.buffer.size' 2>/dev/null || echo "?")
TOKEN_COUNT=$(curl -s "http://localhost:8000/api/tokens/new-pairs" | jq '.count' 2>/dev/null || echo "?")
DEXSCREENER=$(curl -s "https://api.dexscreener.com/latest/dex/search?q=SOL" | jq '.pairs | length' 2>/dev/null || echo "?")

echo "DexScreener API: $DEXSCREENER pairs"
echo "Buffer size: $BUFFER_SIZE"
echo "Tokens returned: $TOKEN_COUNT"

if [ "$TOKEN_COUNT" -gt 0 ]; then
    echo "✅ SUCCESS - New pairs pipeline is working!"
else
    echo "❌ PROBLEM - No tokens returned"
    if [ "$BUFFER_SIZE" -eq 0 ]; then
        echo "   → Buffer is empty, check fallback polling"
    else
        echo "   → Buffer has data but filters rejecting all tokens"
    fi
fi

# ============= SPECIFIC DEBUGGING =============

echo ""
echo ""
echo "=== Testing Buffer Sample ==="
curl -s "http://localhost:8000/api/debug/new-pairs" | jq '.buffer.sample[] | {source, token_address, created_at_ms}' | head -20

echo ""
echo "=== Last 10 Rejections ==="
curl -s "http://localhost:8000/api/debug/new-pairs" | jq '.rejections.latest_50[0:10]'

echo ""
echo "=== Rejection Summary ==="
curl -s "http://localhost:8000/api/debug/new-pairs" | jq '.rejections.summary_by_reason'

echo ""
echo "=== Fallback Poll Timing ==="
curl -s "http://localhost:8000/api/debug/new-pairs" | jq '.fallback_dexscreener | {last_poll_ago_sec, last_response_count, pushed_to_buffer}'

# ============= WITH PRETTY PRINT =============

echo ""
echo ""
echo "=== Pretty Print All Debug Info ==="
curl -s "http://localhost:8000/api/debug/new-pairs" | jq -C '.'

# ============= STATUS CODE CHECKS =============

echo ""
echo ""
echo "=== Status Code Checks ==="
echo "Debug endpoint:"
curl -w "HTTP %{http_code}\n" -s -o /dev/null "http://localhost:8000/api/debug/new-pairs"

echo "New pairs endpoint:"
curl -w "HTTP %{http_code}\n" -s -o /dev/null "http://localhost:8000/api/tokens/new-pairs"

echo "DexScreener API:"
curl -w "HTTP %{http_code}\n" -s -o /dev/null "https://api.dexscreener.com/latest/dex/search?q=SOL"

# ============= RAW RESPONSES =============

echo ""
echo ""
echo "=== Raw Debug Response (full) ==="
curl -s "http://localhost:8000/api/debug/new-pairs"

echo ""
echo ""
echo "=== Raw New Pairs Response (full) ==="
curl -s "http://localhost:8000/api/tokens/new-pairs?max_age_min=60&limit=5"

# ============= FORMATTED FOR COPY-PASTE =============
# Remove everything above and copy only the command you need:

# Quick check (5 seconds):
# curl -s http://localhost:8000/api/debug/new-pairs | jq '.buffer.size, .fallback_dexscreener | {last_poll_ago_sec, pushed_to_buffer}, "Tokens returned:", (.buffer.size | if . > 0 then "✅" else "❌" end)'

# Show everything (detailed):
# curl -s http://localhost:8000/api/debug/new-pairs | jq '.'

# Show only rejections:
# curl -s http://localhost:8000/api/debug/new-pairs | jq '.rejections'

# Show only buffer:
# curl -s http://localhost:8000/api/debug/new-pairs | jq '.buffer'

# Get actual tokens:
# curl -s http://localhost:8000/api/tokens/new-pairs | jq '.tokens[] | {symbol, score, age_minutes}'

# Monitor in real-time (every 3 seconds):
# watch -n 3 'curl -s http://localhost:8000/api/debug/new-pairs | jq ".buffer.size, .fallback_dexscreener.pushed_to_buffer, (.buffer.size | if . > 0 then \"✅ OK\" else \"❌ Empty\" end)"'
