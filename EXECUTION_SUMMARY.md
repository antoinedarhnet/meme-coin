# 🔧 EXECUTION SUMMARY - New Pairs Pipeline Debug

## Problème Déclaré
```
Page /app/new-pairs affiche :
- 0 RESULTS
- 0 TOKENS SCANNED  
- 0 FILTERED
- "Stream interrupted"

NI le webhook Helius NI le fallback polling DexScreener ne ramènent de données.
```

## ✅ MODIFICATIONS EFFECTUÉES

### 1️⃣ `backend/services/new_pairs/ingestion.py` - Logging Verbeux
**But:** Tracer chaque étape du pipeline d'ingestion

#### Changements:
- ✅ **fallback_poll_loop()**: Logging au démarrage et à chaque itération
  - `[FALLBACK LOOP] Starting fallback_poll_loop`
  - `[FALLBACK LOOP] Buffer now has X candidates`
  
- ✅ **_poll_dexscreener_search()**: Logging détaillé par étape
  - `[FALLBACK] === Polling DexScreener search ===`
  - `[FALLBACK] Got X pairs from API`
  - `[FALLBACK] After age filter: Y pairs` (rejet des pairs trop vieilles)
  - `[FALLBACK] Rejection reasons: {not_solana: 5, too_old: 10, ...}`
  - `[FALLBACK] Pushed Z to buffer`
  
- ✅ **_poll_birdeye_new_listing()**: Logging structure similaire
- ✅ **_poll_pumpfun_frontend()**: Logging structure similaire
  
- ✅ **fetch_all()**: Logging d'agrégation
  - `[FETCH_ALL] Starting with sources={...}`
  - `[FETCH_ALL] Task {i} returned X candidates`
  - `[FETCH_ALL] Collected X candidates, Y after dedup`
  
- ✅ **_from_buffer()**: Logging du nettoyage
  - `[FROM_BUFFER] Before cleanup: X, After (fresh): Y`

**Résultat:** Chaque appel à l'endpoint new-pairs verra exactement où ça bloque.

---

### 2️⃣ `backend/server.py` - Endpoint /tokens/new-pairs Amélioré
**But:** Tracer le pipeline de filtrage et scoring

#### Changements:
- ✅ Logging au début: sources activées, buffer initial
- ✅ Logging pour chaque candidat:
  - Enrichissement via DexScreener
  - Passage des filtres age
  - Calcul des métriques
  - Appel RugCheck
  - Résultats des filtres
  - Score final
- ✅ Logging final détaillé avec raisons de rejet

**Résultat:** Console logs montrent exactement pourquoi un token est accepté/rejeté.

---

### 3️⃣ `backend/services/new_pairs/filters.py` - Mode DEBUG
**But:** Permettre de tester les filtres sans les rejeter réellement

#### Changements:
- ✅ **check_security()**: Logging + mode debug
  - Affiche `[DEBUG_FILTERS] mint_revoked=... freeze_revoked=...`
  - Si DEBUG_FILTERS=true: log la raison mais retourne `FilterResult(True)` (pas de rejet)
  
- ✅ **check_distribution()**: Logging + mode debug
  - Affiche `[DEBUG_FILTERS] top10_pct=X dev_pct=Y holders=Z`
  - Si DEBUG_FILTERS=true: avertit mais accepte
  
- ✅ **check_liquidity_volume()**: Logging + mode debug
  - Affiche `[DEBUG_FILTERS] liq=X vol5=Y tx5=Z bs=W`
  - Si DEBUG_FILTERS=true: avertit mais accepte

**Variable d'environnement:**
```bash
DEBUG_FILTERS=true  # Active mode warn-only
```

**Résultat:** Permet de voir TOUS les tokens et POURQUOI ils seraient rejetés, sans les rejeter.

---

### 4️⃣ `backend/server.py` - Endpoint /debug/new-pairs Amélioré
**But:** Dashboard complète pour diagnostiquer l'état du pipeline

#### Retourne:
```json
{
  "timestamp": "ISO datetime",
  "buffer": {
    "size": 15,                      // Nombre candidats en buffer
    "sample": [...]                  // 10 premiers candidats
  },
  "webhook": {
    "received_count": 0,             // Nombre webhooks reçus
    "last_received_ms": null,        // Quand le dernier webhook
    "last_received_ago_sec": null    // Il y a combien de temps
  },
  "fallback_dexscreener": {
    "last_poll_ms": 1714956000000,   // Quand le dernier poll
    "last_poll_ago_sec": 5.2,        // Il y a combien de temps (< 15s = OK)
    "last_response_count": 50,       // Pairs retournées par l'API
    "after_age_filter": 12,          // Pairs qui passent le filtre age
    "pushed_to_buffer": 8,           // Pairs réellement buffered
    "total_received": 8              // Total depuis démarrage
  },
  "rejections": {
    "total_count": 42,
    "summary_by_reason": {
      "age_filter": 5,
      "liquidity < 5 SOL": 20,
      "< 15 txns in 5m": 17
    },
    "latest_50": [...]               // Details des 50 derniers rejets
  }
}
```

**Résultat:** Une seule requête pour voir l'état complet du système.

---

### 5️⃣ `frontend/src/pages/NewPairs.jsx` - Meilleure Gestion d'Erreur
**But:** Messages d'erreur plus utiles au lieu de "Stream interrupted"

#### Changements:
- ✅ Logging avant chaque fetch
- ✅ Distinction entre erreurs:
  - Timeout (15s)
  - Connexion refusée
  - Réponse du serveur
  - Exception JavaScript
- ✅ Messages d'erreur spécifiques:
  - "Backend timeout (15s) - check server logs"
  - "Cannot reach backend - connection refused"
  - "Backend error: {details}"

**Résultat:** L'utilisateur sait si c'est le backend, le réseau, ou l'API.

---

### 6️⃣ Fichiers de Documentation

#### `DEBUG_NEW_PAIRS.md`
- Curl commands pour tester les APIs directement
- Checklist de debug complète
- Explications des problèmes possibles
- Logs attendus au démarrage

#### `test_new_pairs.sh`
Script bash automatisé qui teste:
1. ✅ Santé du backend
2. ✅ API DexScreener
3. ✅ API Birdeye
4. ✅ API Pump.fun
5. ✅ Endpoint /debug/new-pairs
6. ✅ Endpoint /tokens/new-pairs
7. 📊 Résumé avec diagnostique

#### `backend/.env.example`
Documenté toutes les variables d'environnement incluant:
- `DEBUG_FILTERS=true` pour mode warn-only
- `NEW_PAIRS_FALLBACK_MAX_HOURS=24` pour cutoff age

---

## 🚀 COMMENT UTILISER

### Étape 1: Activer le Debug Mode
```bash
# Dans .env (backend):
DEBUG_FILTERS=true

# Ou en ligne de commande:
export DEBUG_FILTERS=true
cd backend && python -m uvicorn server:app --reload
```

### Étape 2: Lancer le Script de Test
```bash
bash /app/test_new_pairs.sh
```

**Résultat attendu:**
```
✅ DexScreener API returns 50 pairs
✅ Birdeye API returns 20 items
✅ Pump.fun API returns 30 coins
✅ Debug endpoint responds
   Buffer size: 25
   Webhook received: 0
   Fallback pushed to buffer: 25
   Last fallback poll: 3.2s ago
✅ Endpoint returns results:
   Tokens: 8
   Scanned: 25
   Filtered: 17
   Passed scoring: 8
```

### Étape 3: Vérifier les Logs
```bash
# Logs en live:
docker logs <container> -f 2>&1 | grep -i "new-pairs\|fallback"

# Ou écrire dans un fichier:
docker logs <container> 2>&1 > /tmp/logs.txt
grep -i "fallback\|new-pairs" /tmp/logs.txt | tail -50
```

### Étape 4: Endpoint de Debug
```bash
# Voir l'état complet:
curl -s http://localhost:8000/api/debug/new-pairs | jq '.'

# Voir les rejets:
curl -s http://localhost:8000/api/debug/new-pairs | jq '.rejections'

# Voir le buffer:
curl -s http://localhost:8000/api/debug/new-pairs | jq '.buffer.sample'
```

---

## 📊 DIAGNOSTIQUE RAPIDE

### Problème: Buffer Vide (size: 0)
```bash
curl -s http://localhost:8000/api/debug/new-pairs | jq '.fallback_dexscreener'
```
- Si `pushed_to_buffer: 0` → API retourne rien ou fallback ne tourne pas
- Si `last_poll_ago_sec > 60` → fallback_poll_loop ne tourne pas

### Problème: Tous les Tokens Rejetés
```bash
# Activer DEBUG_FILTERS=true puis:
curl -s http://localhost:8000/api/debug/new-pairs | jq '.rejections.summary_by_reason'
```
- Voir quels filtres rejettent le plus
- Réduire les seuils dans filters.py

### Problème: "Stream interrupted" au Frontend
```bash
# Vérifier backend health:
curl -s http://localhost:8000/api/

# Vérifier l'endpoint new-pairs:
curl -w "\nStatus: %{http_code}\n" http://localhost:8000/api/tokens/new-pairs

# Vérifier les logs du serveur:
docker logs <container> 2>&1 | grep -i "error\|exception"
```

---

## 🎯 PROCHAINES ÉTAPES SI TOUJOURS PAS DE RÉSULTATS

### Cas 1: APIs Externes Down
Si DexScreener/Birdeye/Pump.fun ne retournent rien:
- Tester directement: `curl https://api.dexscreener.com/latest/dex/search?q=SOL`
- Vérifier rate limits
- Passer à la prochaine source (déjà en place)

### Cas 2: Filtres Trop Stricts
Si buffer a des données mais 0 tokens retournés:
- Activer `DEBUG_FILTERS=true`
- Voir les raisons de rejet
- Réduire les seuils:
  - `liquidity_sol < 5` → passer à `< 2`
  - `txns_5m < 15` → passer à `< 5`
  - `buy_sell_ratio <= 1.2` → passer à `<= 1.0`

### Cas 3: RugCheck Failure Rate
Si beaucoup de "rugcheck_fetch_failed":
- RugCheck API peut être instable
- Ajouter retry logic ou timeout plus long
- Ou rendre RugCheck optionnel (skip si timeout)

---

## ✨ RÉSUMÉ DES AMÉLIORATIONS

| Aspect | Avant | Après |
|--------|-------|-------|
| **Logging** | Minimal | Verbose à chaque étape |
| **Debug Mode** | N/A | DEBUG_FILTERS=true |
| **Debug Endpoint** | Basique | Complet + rejections détaillés |
| **Frontend Error** | "Stream interrupted" | Erreurs spécifiques |
| **Curl Tests** | N/A | Script et commandes prêtes |
| **Documentation** | Minimale | Complète + checklist |

---

## 📝 NOTES IMPORTANTES

1. **Fallback Loop**: Lancée au startup via `@app.on_event("startup")`
   - Tourne en arrière-plan
   - Poll DexScreener toutes les 10s si pas de webhook depuis 30s
   - Remplit le buffer avec des pairs fraîches

2. **Buffer**: Unifié entre webhook + fallback
   - `_buffer[token_address] = candidate`
   - Nettoyé automatiquement par age (cutoff_ms)

3. **Scoring**: Minimum de 60 pour être retourné
   - Peut passer à 0 en mode DEBUG_FILTERS

4. **Frontend**: Retry toutes les 20s (ou 5s si erreur)
   - Affiche dernier refresh time
   - Montre stats scanned/filtered en temps réel

---

Créé: 2026-05-05
Status: ✅ Prêt pour deployment + debug
