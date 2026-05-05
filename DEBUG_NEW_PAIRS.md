# 🔍 Debug Guide: New Pairs Pipeline

## Problème Déclaré
Page `/new-pairs` affiche 0 résultats avec "Stream interrupted", ni webhook Helius ni fallback polling ne ramènent de données.

## 🧪 Curl Commands pour Tester Manuellement

### 1. Test DexScreener API (Fallback Source #1)
```bash
# Test simple de l'endpoint DexScreener search
curl -s "https://api.dexscreener.com/latest/dex/search?q=SOL" | head -200

# Parse et compter les résultats
curl -s "https://api.dexscreener.com/latest/dex/search?q=SOL" | jq '.pairs | length'

# Voir les 3 premières paires
curl -s "https://api.dexscreener.com/latest/dex/search?q=SOL" | jq '.pairs[0:3]'

# Filtrer seulement paires Solana créées < 24h
curl -s "https://api.dexscreener.com/latest/dex/search?q=SOL" | jq '.pairs[] | select(.chainId == "solana") | {symbol: .baseToken.symbol, created: .pairCreatedAt, liq: .liquidity.usd}' | head -50
```

### 2. Test Birdeye API (Fallback Source #2)
```bash
# Test direct
curl -s "https://public-api.birdeye.so/defi/v2/tokens/new_listing" | jq '.' | head -100

# Compter les résultats
curl -s "https://public-api.birdeye.so/defi/v2/tokens/new_listing" | jq '.data | length'
```

### 3. Test Pump.fun API (Fallback Source #3)
```bash
# Test direct
curl -s "https://frontend-api.pump.fun/coins?offset=0&limit=50&sort=created_timestamp" | jq '.coins | length'

# Voir les coins retournés
curl -s "https://frontend-api.pump.fun/coins?offset=0&limit=50&sort=created_timestamp" | jq '.coins[0:3]'
```

### 4. Backend Debug Endpoints

#### Voir l'état global du pipeline
```bash
curl -s "http://localhost:8000/api/debug/new-pairs" | jq '.'
```

Réponse attendue:
```json
{
  "timestamp": "2026-05-05T...",
  "buffer": {
    "size": 0,  // ❌ PROBLÈME SI 0
    "sample": []
  },
  "webhook": {
    "received_count": 0,  // ❌ PROBLÈME SI 0
    "last_received_ms": null,  // ❌ PROBLÈME SI null
    "last_received_ago_sec": null
  },
  "fallback_dexscreener": {
    "last_poll_ms": 1714956000000,  // ✅ DOIT avoir une valeur
    "last_response_count": 50,  // ✅ DOIT avoir des pairs
    "after_age_filter": 12,  // ✅ DOIT avoir des pairs
    "pushed_to_buffer": 8,  // ✅ DOIT être > 0
    "total_received": 8
  },
  "rejections": {
    "total_count": 2,
    "summary_by_reason": {
      "age_filter": 2
    }
  }
}
```

#### Voir les données de new-pairs
```bash
curl -s "http://localhost:8000/api/tokens/new-pairs?max_age_min=60&limit=10" | jq '.'
```

Réponse attendue:
```json
{
  "tokens": [...],  // ✅ DOIT avoir des tokens
  "count": 5,  // ✅ DOIT être > 0
  "meta": {
    "scanned": 15,  // ✅ Nombre candidats trouvés
    "filtered": 12,  // Nombre rejeté
    "passed_scoring": 3,  // ✅ Nombre finaux
    "filtered_reasons": {
      "age_filter": 5,
      "liquidity < 5 SOL": 4,
      "rugcheck_fetch_failed": 3
    }
  }
}
```

## 🔍 Problèmes Possibles et Solutions

### Problème 1: Buffer Vide (size: 0)
**Causes possibles:**
1. Webhook jamais reçu → OK, fallback devrait prendre le relais
2. Fallback ne fonctionne pas → **GRAVE**
3. Buffer vidé trop rapidement par le cutoff_ms

**Check:**
- `fallback_dexscreener.pushed_to_buffer` doit être > 0
- Si 0, les APIs retournent peut-être pas de données

### Problème 2: DexScreener Fallback Reçoit Rien
**Test direct:**
```bash
curl -s "https://api.dexscreener.com/latest/dex/search?q=SOL" | jq '.pairs | length'
```
- Si 0 → l'API de DexScreener est down ou ratelimitée
- Si > 0 → la boucle fallback ne tourne pas

**Check les logs:**
```bash
# Voir si fallback_poll_loop s'exécute
docker logs <container> 2>&1 | grep -i "fallback"

# Voir tous les logs new-pairs
docker logs <container> 2>&1 | grep -i "new-pairs\|fallback"
```

### Problème 3: Tous les Tokens Rejeté par Filtres
**Causes:**
1. Liquidity `< 5 SOL` → très strict pour des **fresh pairs**
2. `< 15 txns in 5m` → trop strict pour des nouveaux tokens
3. `buy/sell ratio <= 1.2` → rejet si peu d'activité
4. RugCheck échoue pour les nouveaux tokens

**Solution:**
Activez `DEBUG_FILTERS=true` pour logger chaque rejet au lieu de rejeter réellement.

### Problème 4: Frontend "Stream interrupted"
**Causes:**
- Endpoint `/tokens/new-pairs` retourne 0 résultats
- Timeout du fetch (défaut: 15s)
- CORS issue

**Check:**
```bash
curl -s "http://localhost:8000/api/tokens/new-pairs?max_age_min=60&limit=10" -w "\nStatus: %{http_code}\n"
```

## 📋 Checklist de Debug

- [ ] **Fallback loop tourne:**
  ```bash
  # Voir timestamp de last_fallback_poll_ms
  curl -s "http://localhost:8000/api/debug/new-pairs" | jq '.fallback_dexscreener.last_poll_ms'
  ```

- [ ] **DexScreener API fonctionne:**
  ```bash
  curl -s "https://api.dexscreener.com/latest/dex/search?q=SOL" | jq '.pairs | length'
  ```

- [ ] **Buffer reçoit des candidats:**
  ```bash
  curl -s "http://localhost:8000/api/debug/new-pairs" | jq '.fallback_dexscreener.pushed_to_buffer'
  ```

- [ ] **Filtres ne rejettent pas tout:**
  ```bash
  curl -s "http://localhost:8000/api/debug/new-pairs" | jq '.rejections.summary_by_reason'
  ```

- [ ] **Endpoint retourne des tokens:**
  ```bash
  curl -s "http://localhost:8000/api/tokens/new-pairs?max_age_min=60&limit=5" | jq '.count'
  ```

## 🚀 Activation du Mode DEBUG

### Option 1: Variable d'environnement
```bash
export DEBUG_FILTERS=true
# Relancer le serveur
```

### Option 2: Dans le code
Modifier `filters.py`:
```python
DEBUG_FILTERS = True  # Force mode debug
```

Avec `DEBUG_FILTERS=true`, les filtres **ne rejettent pas, ils avertissent seulement** et retournent `FilterResult(True)`.

## 📊 Logs Attendus au Démarrage

```
2026-05-05 10:00:00 - INFO - [FALLBACK LOOP] Starting fallback_poll_loop
2026-05-05 10:00:02 - INFO - [FALLBACK] === Polling DexScreener search ===
2026-05-05 10:00:02 - INFO - [FALLBACK] Got 50 pairs from API
2026-05-05 10:00:02 - INFO - [FALLBACK] After age filter: 12 pairs
2026-05-05 10:00:02 - INFO - [FALLBACK] Pushed 8 to buffer
2026-05-05 10:00:02 - INFO - [FALLBACK] === Polling Birdeye new listing ===
2026-05-05 10:00:03 - INFO - [FALLBACK] Got 20 items from Birdeye
2026-05-05 10:00:03 - INFO - [FALLBACK] Birdeye pushed 5 to buffer
```

## 🎯 Prochaines Étapes

1. **Vérifier les APIs fonctionnent** → curl commands ci-dessus
2. **Activer DEBUG_FILTERS** → mode "warn only"
3. **Checker les logs** → voir où ça bloque
4. **Réduire les filtres** si trop stricts
5. **Ajouter Pump.fun/Birdeye** comme sources si DexScreener down
