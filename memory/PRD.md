# SNIPR.SOL — Solana Memecoin Sniping Terminal

## Original Problem Statement
French user asked for a Solana memecoin sniping platform inspired by GMGN/BullX/Photon. Iterative feature requests:
- V1 (Feb 2026): Live feed, KOL surveillance, narratives, paper trading, scoring, risk detection
- V2 (Feb 2026): Trade markers + SELL button
- V3 (Apr 2026): Paper Trading Engine + Auto-Snipe + Auto-Sell TP/SL ladder + Risk limits

## User Choices
- Data source: **DexScreener public API** (real Solana tokens, free tier)
- Trading: **100% paper trading / simulation** (no real blockchain tx for now)
- KOL/Twitter: Simulation (Nitter scraping deferred — instances unreliable)
- Trends: Deferred (pytrends rate-limit issues)
- Theme: Tactical Terminal — Cabinet Grotesk + JetBrains Mono

## Architecture
- **Backend**: FastAPI + Motor (MongoDB) + httpx → DexScreener public API
- **Frontend**: React 19 + Tailwind + Recharts + Sonner toasts + Lucide icons
- **Background engines**: `auto_snipe_loop` (30s polling) and `auto_sell_loop` (12s monitoring) started via FastAPI `on_event("startup")`

## Implemented Features

### V1 (Feb 2026)
- Live token feed with AI scoring (0-100) + risk classifier
- KOL watchlist + cross-call radar (simulation)
- Narrative heatmap (8 metas)
- Paper portfolio with equity curve
- Trading terminal UI with neon accents

### V2 (Feb 2026)
- `MY TRADES ON THIS TOKEN` panel on token detail
- Visual entry-to-now bars (green/red based on P&L)
- Entry markers strip above DexScreener chart
- `● HOLDING` badge on dashboard for owned tokens
- Live SELL at current DexScreener price
- `GET /api/portfolio/positions` with `token_address` + `status` filters

### V3 (Apr 2026) — Paper Trading Engine
- **Virtual bankroll** — 10 SOL default, editable via `PUT /api/bankroll`, reset via `POST /api/bankroll/reset` (closes open positions)
- **Auto-Snipe Engine** (background task) — polls DexScreener every 30s, applies user rules (min_score, min_liq_usd, max_age_min, risks_blocked, amount_sol), skips tokens already held, respects bankroll balance + max_open_positions
- **Auto-Sell TP/SL Ladder** (background task every 12s) — tiered sells: TP1 @ +50% / TP2 @ +100% / TP3 @ +200%, moonbag trailing -30% from ATH, SL -40% dump all. Configurable per-TP sell %
- **Tiered positions** with `tokens_remaining`, `tp_hits[]`, `ath_price`, `realized_pnl_sol`, `source` ∈ {manual, auto_snipe, copy_trade, kol_call}
- **Partial close endpoint** `POST /api/portfolio/partial-close` with tp_tag
- **Risk limits** — max_position_pct, max_open_positions, daily_loss_limit_pct (auto-locks bankroll until UTC midnight on breach), daily_profit_lock_pct
- **Engine events feed** — last 30 engine actions streamed to UI via `/api/engine/status`
- **UI additions**: paper trading banner (top), bankroll chip (header), auto-snipe toggle (header, ARMED/LOCKED/OFF), engine events strip, expanded Settings page (4 sections: Auto-Snipe, Auto-Sell ladder, Risk limits, Trading defaults), Portfolio page with source/tp_hits columns + bankroll panel + P&L by source

## Backend Endpoints
- Core: `/tokens/live`, `/tokens/{addr}`, `/ticker`, `/narratives`
- KOLs: `/kols` CRUD, `/kols/calls`
- Portfolio: `/portfolio/positions`, `/portfolio/buy`, `/portfolio/close`, `/portfolio/partial-close`, `/portfolio/stats`, `/portfolio/trade-log`
- Bankroll: `/bankroll` GET/PUT, `/bankroll/reset`
- Engine: `/engine/status`
- Alerts: `/alerts` CRUD
- Settings: `/settings` GET/PUT

## Honest Limitations (deferred)
- **Phantom Wallet connect** — UI button only, no signMessage flow yet
- **WebSocket** — using 8-12s polling instead
- **Twitter/X real-time** — simulation only (Nitter unreliable)
- **Google Trends** — skipped (429 rate limits)
- **Copy-trading smart wallets** — not yet implemented
- **Telegram notifications** — awaiting user bot token
- **Helius holders + bubble map** — awaiting user API key
- **Real on-chain sniping** (Jupiter) — not implemented, paper only

## Backlog
- P1: Phantom wallet sign-in with Solana
- P1: WebSocket stream for sub-second updates
- P1: Copy-trading engine via Solana RPC polling
- P1: Telegram notifications on auto-snipe/auto-sell
- P2: Nitter scraping (best-effort, 1 instance at a time)
- P2: Performance analytics tab (backtest simulator)
- P2: Bubble map with Helius
- P3: Real on-chain trading toggle (Jupiter + Phantom)

## Next Tasks
1. End-to-end testing via `testing_agent_v3`
2. Iterate on user feedback

## V3.0 PRODUCTION Rebrand (Apr 2026)

### Priority 1 — LIVE MODE branding
- Removed yellow "PAPER TRADING" banner; replaced with green "LIVE MODE · SOLANA MAINNET · DEXSCREENER STREAMING"
- Footer now reads "LIVE MODE · SOLANA MAINNET"
- Landing + Dashboard + TokenDetail: all "paper" / "simulation" text scrubbed
- "SNIPE NOW (PAPER)" → "SNIPE NOW"
- Discrete `paper_mode` boolean added to Settings (default true; toggle in Trading Defaults with explanation). When false, engine would route to on-chain Jupiter (not yet wired — requires Phantom connect)

### Priority 2 — Portfolio PNL v2
- Hero PNL big number (60px green/red with glow) with % vs initial, USD equivalent, live balance
- 24H / 7D / ALL TIME timeframe tabs (backend filters positions by opened_at)
- 6 KPI cards: Realized · Unrealized · Win Rate · Invested · Recovered · Avg Hold
- Equity curve area chart with BEST/WORST trade badges inline in the header
- 5-way filter: All / Open / Closed / Profit / Loss
- 11-column trade table: Token · Source · Buy Price · Current/Sell · Amount · PNL SOL · PNL $ · PNL % · Hold · Status · SELL
- Live unrealized PnL computed client-side from DexScreener prices for open positions
- CSV export button (server-rendered `GET /api/portfolio/export-csv`)
- Reset bankroll button

### New endpoints
- `GET /api/portfolio/stats?timeframe=24h|7d|all`
- `GET /api/portfolio/equity-history?timeframe=...`
- `GET /api/portfolio/export-csv`

### Next phases (on hold until user goes)
- P3: New pairs sniping (<2min launches) via Raydium polling
- P4: Whale Tracker with 8 preloaded wallets (via Solana public RPC)
- P5: Rugcheck.xyz integration, Copy Whale / KOL Mention signals, sound alerts, keyboard shortcuts
- P6: Phantom wallet connect + Jupiter swap for real on-chain execution (requires user sign)
