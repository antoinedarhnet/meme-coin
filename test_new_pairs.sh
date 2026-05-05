#!/bin/bash
# 🧪 Test Script pour Debug New Pairs Pipeline
# Usage: bash test_new_pairs.sh

set -e

BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"
DEXSCREENER_URL="https://api.dexscreener.com"

echo "🧪 New Pairs Pipeline Debug Test"
echo "================================="
echo "Backend: $BACKEND_URL"
echo ""

# Test 1: Check Backend Health
echo "📡 TEST 1: Backend Health Check"
echo "--------------------------------"
if curl -s "$BACKEND_URL/api/" | jq . > /dev/null 2>&1; then
    echo "✅ Backend is up"
else
    echo "❌ Backend is DOWN or unreachable"
    exit 1
fi
echo ""

# Test 2: Check DexScreener API
echo "📡 TEST 2: DexScreener API"
echo "----------------------------"
DEXSCREENER_RESPONSE=$(curl -s "$DEXSCREENER_URL/latest/dex/search?q=SOL")
PAIR_COUNT=$(echo "$DEXSCREENER_RESPONSE" | jq '.pairs | length' 2>/dev/null || echo 0)

if [ "$PAIR_COUNT" -gt 0 ]; then
    echo "✅ DexScreener API returns $PAIR_COUNT pairs"
    SAMPLE=$(echo "$DEXSCREENER_RESPONSE" | jq '.pairs[0] | {symbol: .baseToken.symbol, created: .pairCreatedAt, liq: .liquidity.usd}')
    echo "   Sample: $SAMPLE"
else
    echo "❌ DexScreener API returns 0 pairs"
fi
echo ""

# Test 3: Check Birdeye API
echo "📡 TEST 3: Birdeye API"
echo "----------------------"
BIRDEYE_RESPONSE=$(curl -s "https://public-api.birdeye.so/defi/v2/tokens/new_listing" 2>/dev/null)
BIRDEYE_COUNT=$(echo "$BIRDEYE_RESPONSE" | jq '.data | length' 2>/dev/null || echo 0)

if [ "$BIRDEYE_COUNT" -gt 0 ]; then
    echo "✅ Birdeye API returns $BIRDEYE_COUNT items"
else
    echo "⚠️  Birdeye API returns 0 items (might be up or rate-limited)"
fi
echo ""

# Test 4: Check Pump.fun API
echo "📡 TEST 4: Pump.fun API"
echo "------------------------"
PUMPFUN_RESPONSE=$(curl -s "https://frontend-api.pump.fun/coins?offset=0&limit=50&sort=created_timestamp" 2>/dev/null)
PUMPFUN_COUNT=$(echo "$PUMPFUN_RESPONSE" | jq '.coins | length' 2>/dev/null || echo 0)

if [ "$PUMPFUN_COUNT" -gt 0 ]; then
    echo "✅ Pump.fun API returns $PUMPFUN_COUNT coins"
else
    echo "⚠️  Pump.fun API returns 0 coins (might be up or rate-limited)"
fi
echo ""

# Test 5: Check Backend Debug Endpoint
echo "📡 TEST 5: Backend Debug Endpoint"
echo "----------------------------------"
DEBUG_RESPONSE=$(curl -s "$BACKEND_URL/api/debug/new-pairs" 2>/dev/null)

if [ -z "$DEBUG_RESPONSE" ]; then
    echo "❌ Debug endpoint failed"
else
    echo "✅ Debug endpoint responds"
    
    BUFFER_SIZE=$(echo "$DEBUG_RESPONSE" | jq '.buffer.size' 2>/dev/null || echo "?")
    WEBHOOK_COUNT=$(echo "$DEBUG_RESPONSE" | jq '.webhook.received_count' 2>/dev/null || echo "?")
    FALLBACK_PUSHED=$(echo "$DEBUG_RESPONSE" | jq '.fallback_dexscreener.pushed_to_buffer' 2>/dev/null || echo "?")
    LAST_POLL=$(echo "$DEBUG_RESPONSE" | jq '.fallback_dexscreener.last_poll_ago_sec' 2>/dev/null || echo "?")
    
    echo "   Buffer size: $BUFFER_SIZE"
    echo "   Webhook received: $WEBHOOK_COUNT"
    echo "   Fallback pushed to buffer: $FALLBACK_PUSHED"
    echo "   Last fallback poll: ${LAST_POLL}s ago"
fi
echo ""

# Test 6: Check New Pairs Endpoint
echo "📡 TEST 6: New Pairs Endpoint"
echo "------------------------------"
NEWPAIRS_RESPONSE=$(curl -s "$BACKEND_URL/api/tokens/new-pairs?max_age_min=60&limit=10" 2>/dev/null)

if [ -z "$NEWPAIRS_RESPONSE" ]; then
    echo "❌ New pairs endpoint failed"
else
    TOKEN_COUNT=$(echo "$NEWPAIRS_RESPONSE" | jq '.count' 2>/dev/null || echo 0)
    SCANNED=$(echo "$NEWPAIRS_RESPONSE" | jq '.meta.scanned' 2>/dev/null || echo 0)
    FILTERED=$(echo "$NEWPAIRS_RESPONSE" | jq '.meta.filtered' 2>/dev/null || echo 0)
    SCORED=$(echo "$NEWPAIRS_RESPONSE" | jq '.meta.passed_scoring' 2>/dev/null || echo 0)
    
    echo "✅ Endpoint returns results:"
    echo "   Tokens: $TOKEN_COUNT"
    echo "   Scanned: $SCANNED"
    echo "   Filtered: $FILTERED"
    echo "   Passed scoring: $SCORED"
    
    if [ "$TOKEN_COUNT" -eq 0 ]; then
        echo ""
        echo "⚠️  WARNING: 0 tokens returned!"
        echo "   Failure reasons:"
        echo "$NEWPAIRS_RESPONSE" | jq '.meta.filtered_reasons' 2>/dev/null || echo "   (Unable to parse)"
    fi
fi
echo ""

# Summary
echo "📊 SUMMARY"
echo "=========="
if [ "$BUFFER_SIZE" -gt 0 ] && [ "$TOKEN_COUNT" -gt 0 ]; then
    echo "✅ ALL SYSTEMS GO! Buffer has $BUFFER_SIZE candidates, returned $TOKEN_COUNT tokens"
elif [ "$PAIR_COUNT" -eq 0 ]; then
    echo "❌ PROBLEM: DexScreener API returns 0 pairs - can't fetch new pairs"
elif [ "$FALLBACK_PUSHED" -eq 0 ]; then
    echo "❌ PROBLEM: Fallback poll not working - no pairs pushed to buffer"
elif [ "$TOKEN_COUNT" -eq 0 ]; then
    echo "⚠️  WARNING: Buffer has data but 0 tokens returned - filters too strict?"
    echo "   Check DEBUG_FILTERS mode or reduce filter thresholds"
else
    echo "✅ System partially working, but check logs for issues"
fi
