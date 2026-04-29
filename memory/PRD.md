# SNIPR.SOL — Solana Memecoin Sniping Terminal

## Original Problem Statement
"salut a partir de ce prompt fait un site de sniping de meme coin le prompt et pas tres détaillier si tu veux rajouter et améliorer des choses te géne pas merci"
+ Detailed prompt: pro-grade Solana memecoin sniping platform with real-time detection (Pump.fun, Raydium, DexScreener, Helius, Birdeye), AI scoring 0-100, rug/honeypot detection, X/Twitter KOL surveillance with cross-call signals, viral trend analysis, dashboard like GMGN/BullX/Photon, Phantom wallet 1-click snipe, paper trading.

## User Choices
- Data source: **DexScreener public API** (real Solana tokens, no key required)
- Trading: **Paper trading mode** (simulated, safe)
- KOL/Twitter: **Realistic simulation** (6 default KOLs + cross-call signal generator)
- Auth: **Local session** (no server-side auth in V1)
- Theme: **Tactical Terminal** — deep obsidian + neon green/cyan/violet (Cabinet Grotesk + JetBrains Mono)

## User Personas
- **Memecoin Trader** — Wants to detect new launches before they pump
- **Risk-Aware Hunter** — Needs scoring + rug detection to filter scams
- **KOL Follower** — Tracks alpha callers and convergence signals

## Architecture
- **Backend**: FastAPI + Motor (MongoDB) + httpx → DexScreener public API (`token-boosts/latest`, `token-boosts/top`, `token-profiles/latest`, `tokens/v1/solana/{addrs}`, `latest/dex/search`)
- **Frontend**: React 19 + Tailwind + Shadcn primitives + Recharts + Sonner toasts + Lucide icons
- **DB Collections**: `kols`, `positions`, `alerts`, `settings`
- **Scoring algorithm** (max 100): liquidity 25 + vol/liq ratio 15 + buy/sell pressure 15 + momentum 20 + tx/sec 10 + socials 10 + age sweet-spot 5

## Implemented (Feb 2026)
### Backend (`/api/*`)
- `GET /tokens/live` — Live Solana feed with filters (sort, risk, min_liq, min_score, limit)
- `GET /tokens/{addr}` — Detail + score breakdown + DexScreener pair
- `GET /ticker` — Top 25 movers for marquee
- `GET/POST/DELETE /kols` — KOL CRUD (auto-seeded with 6 famous callers)
- `GET /kols/calls` — Latest mentions + cross-calls aggregation
- `GET /narratives` — 8 viral metas with token matching
- `GET/POST /portfolio/buy|close` + `GET /portfolio/positions|stats` — Paper trading
- `GET/POST/DELETE /alerts` — Alert rules CRUD
- `GET/PUT /settings` — Trading defaults

### Frontend
- `/` Landing — Hero, live mocked terminal preview (real data), 6-feature bento, live scores table, scoring algorithm card, CTA
- `/app` Dashboard — Filter bar (search/risk/sort/min-liq/min-score), live data table with score ring, risk badge, quick-snipe button, auto-refresh 25s
- `/app/kol` KOL Watchlist — KOL grid (add/remove), Cross-Call Radar panel, Latest Mentions feed
- `/app/trending` — Narrative heatmap (8 metas) + matched tokens grid
- `/app/token/:addr` — Token detail with embedded DexScreener chart, AI score breakdown, snipe panel, pair stats, socials
- `/app/portfolio` — KPI cards, equity curve (recharts), positions table, close trade
- `/app/settings` — Trading defaults form + alert rules CRUD

## Backlog (P0/P1/P2)
- **P1**: Real Phantom Wallet connection + Sign-in with Solana
- **P1**: WebSocket streaming (currently 25s polling)
- **P1**: Real X/Twitter API integration (currently realistic simulation)
- **P2**: Bubble map visualization (holder wallet interconnection)
- **P2**: Live alert notifications (Telegram/Discord webhooks)
- **P2**: Holder distribution from Helius RPC
- **P2**: Trending tokens from Google Trends/Reddit/TikTok
- **P3**: Real on-chain sniping (Jupiter aggregator) with priority fees

## Next Tasks
1. End-to-end testing via `testing_agent_v3`
2. Iterate on user feedback
