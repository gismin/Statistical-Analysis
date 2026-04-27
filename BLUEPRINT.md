# Statistical Analysis — Project Blueprint

**Goal:** A web-based statistical analysis tool for crypto (and later equity) markets, surfacing probabilistic insights about when and how far price moves — so traders can make faster, data-backed decisions.

**Reference inspiration:** [BrighterData](https://brighterdata.com/features)

---

## Product Overview

Four core features:

| Feature | What It Does |
|---|---|
| **Time** | When highs/lows are typically formed; reversal vs. continuation probability at similar times |
| **Distance** | How far price moved vs. historical sessions; reversal vs. extension probability |
| **Summary** | Combined Time + Distance view across two timeframes; Confidence Targets |
| **Overview** | All assets × all insights in one sortable table — scannable in seconds |

---

## Tech Stack Decision

| Layer | Choice | Rationale |
|---|---|---|
| **Backend** | Python + FastAPI | Async, fast, great for data pipelines |
| **Data** | CCXT (crypto) + yfinance (equity later) | Free tier, covers major exchanges |
| **Storage** | PostgreSQL + TimescaleDB extension | Native time-series, good for OHLCV |
| **Cache** | Redis | Pre-computed stats served in < 100ms |
| **Frontend** | Next.js + TypeScript | SSR for SEO, great DX, fast tables |
| **UI Components** | shadcn/ui + Tailwind CSS | Clean, accessible, customizable |
| **Charts** | TradingView Lightweight Charts | Institutional-grade, free |
| **Auth** | Clerk (or Supabase Auth) | Fast to wire up, handles JWT |
| **Deployment** | Railway (backend) + Vercel (frontend) | Easy CI/CD, free tiers for MVP |

---

## Phase Blueprint

### Phase 0 — Foundation (Week 1–2)
**Goal:** Skeleton project runs locally, data flows from exchange to database.

**Tasks:**
- [ ] Monorepo structure: `/backend`, `/frontend`, `/scripts`
- [ ] Backend: FastAPI app with health endpoint
- [ ] Database: PostgreSQL + TimescaleDB via Docker Compose
- [ ] Data ingestion script: fetch OHLCV (1D, 1W) for top 10 crypto pairs via CCXT
- [ ] Store raw candles in `ohlcv` table with `(symbol, timeframe, open_time)` primary key
- [ ] Cron job or APScheduler to refresh daily
- [ ] Redis for caching computed results
- [ ] Frontend: Next.js scaffold, Tailwind + shadcn/ui configured
- [ ] `.env` template and Docker Compose for local dev

**Deliverable:** `GET /api/health` returns OK; database has real OHLCV data; frontend shell renders.

---

### Phase 1 — Time Feature (Week 3–4)
**Goal:** For any asset + timeframe, show when highs/lows were formed and what happened next.

**Core Stat: "Time of High/Low" Distribution**

For each historical session:
- Record `session_high_time` and `session_low_time` as % of session elapsed when the extreme was set
- Bucket into time slots (e.g., 0–10%, 10–20%, … 90–100%)
- For each bucket: count how often price **reversed** (didn't re-take the extreme) vs. **continued** (took it out later)

**Backend tasks:**
- [ ] `time_stats` table: precomputed per `(symbol, timeframe, time_bucket)`
- [ ] `POST /api/stats/time` — accepts `{symbol, timeframe}`, returns time distribution + current session position
- [ ] Computation engine: label each candle as "high first" or "low first", detect continuation vs. reversal
- [ ] "Unusually early" flag: if current extreme is in the earliest 20th percentile, flag it

**Frontend tasks:**
- [ ] Time Feature page: bar chart of reversal probability by time bucket
- [ ] Highlight current session's bucket
- [ ] Warning badge for "early high/low"

**Deliverable:** Time page live for BTC/USDT daily.

---

### Phase 2 — Distance Feature (Week 5–6)
**Goal:** Show how today's range compares to historical sessions and what came next.

**Core Stat: "Range as % of ATR" Distribution**

For each historical session:
- Compute `current_range = |high - low|` at each point in the session
- Normalize: `range_pct = current_range / ATR(14)` for that session
- Bucket sessions by range_pct at time of query (e.g., 0–25%, 25–50%, 50–75%, 75–100%, >100%)
- For each bucket: reversal rate, continuation rate, median extension

**Backend tasks:**
- [ ] ATR computation integrated into ingestion pipeline
- [ ] `distance_stats` table: precomputed per `(symbol, timeframe, range_bucket)`
- [ ] `POST /api/stats/distance` — returns distribution + current session's bucket
- [ ] "Small wick" warning: if current range is in lowest 25th percentile historically

**Frontend tasks:**
- [ ] Distance Feature page: histogram of session outcomes by range bucket
- [ ] Current session highlighted
- [ ] Warning badge for "small range — historically likely to extend"

**Deliverable:** Distance page live for BTC/USDT daily.

---

### Phase 3 — Summary Feature (Week 7–8)
**Goal:** Combine Time + Distance across two timeframes; add Confidence Targets.

**Confidence Targets**

For a given asset + timeframe:
- Given current range and time elapsed, what % of historical sessions went on to reach `+X%` further?
- Compute target levels: `current_high + X%` where X is the 75th, 50th, 25th percentile extension
- Display as price levels with % confidence labels

**Backend tasks:**
- [ ] `POST /api/stats/summary` — accepts `{symbol, tf1, tf2}`, returns combined Time + Distance stats for both timeframes + Confidence Targets
- [ ] Weighted signal: combine Time probability + Distance probability into a single directional bias score

**Frontend tasks:**
- [ ] Summary page: side-by-side TF1 vs TF2 comparison cards
- [ ] Confidence Target levels shown on a mini price chart
- [ ] Directional bias indicator (bullish / bearish / neutral) per timeframe

**Deliverable:** Summary page live. BTC weekly vs. daily comparison works.

---

### Phase 4 — Overview Page (Week 9–10)
**Goal:** All assets × all stats in one sortable, filterable table.

**Columns (configurable):**
- Asset
- Timeframe
- Time: current bucket + reversal %
- Distance: current bucket + reversal %
- Bias (combined score)
- Early High/Low flag
- Small Range flag
- Last updated

**Backend tasks:**
- [ ] `GET /api/overview` — returns all precomputed stats for all tracked assets in one payload
- [ ] Background job: recompute all stats every 15 min during market hours
- [ ] Pagination + filtering support

**Frontend tasks:**
- [ ] Overview table with TanStack Table (sorting, filtering, column toggle)
- [ ] Color-coded cells (green = high reversal probability, red = high continuation probability)
- [ ] Quick-link from each row to the asset's Summary page
- [ ] Asset watchlist: user can pin/unpin assets

**Deliverable:** Overview page shows top 20 crypto pairs, sortable.

---

### Phase 5 — Auth, Polish, and Deployment (Week 11–12)
**Goal:** Production-ready, publicly accessible, monetization-ready.

**Tasks:**
- [ ] Auth: Clerk or Supabase Auth — free tier + paid tier gating
- [ ] User watchlists persisted to DB
- [ ] Rate limiting on API endpoints
- [ ] Error boundaries + loading states throughout frontend
- [ ] Mobile-responsive layout audit
- [ ] Deploy backend to Railway, frontend to Vercel
- [ ] Set up GitHub Actions CI: lint + test on every PR
- [ ] Custom domain + SSL
- [ ] Basic analytics (Posthog)

**Deliverable:** Live public URL. Shareable.

---

### Phase 6 — Equity Markets (Post-launch)
**Goal:** Extend the same infrastructure to stocks.

**Tasks:**
- [ ] Add yfinance adapter alongside CCXT
- [ ] Handle market hours (equity sessions are fixed; crypto is 24/7)
- [ ] Session definition for equity: regular hours vs. extended hours
- [ ] Backfill top 50 S&P 500 tickers
- [ ] Overview page: toggle between Crypto / Equity / All

---

## Data Model (Simplified)

```sql
-- Raw candles
CREATE TABLE ohlcv (
  symbol      TEXT,
  timeframe   TEXT,
  open_time   TIMESTAMPTZ,
  open        NUMERIC,
  high        NUMERIC,
  low         NUMERIC,
  close       NUMERIC,
  volume      NUMERIC,
  PRIMARY KEY (symbol, timeframe, open_time)
);

-- Precomputed session stats
CREATE TABLE session_stats (
  symbol           TEXT,
  timeframe        TEXT,
  session_date     DATE,
  high_time_pct    NUMERIC,  -- % of session elapsed when high was set
  low_time_pct     NUMERIC,
  range_atr_pct    NUMERIC,  -- range as % of ATR
  high_taken_out   BOOLEAN,  -- did price break the high later?
  low_taken_out    BOOLEAN,
  PRIMARY KEY (symbol, timeframe, session_date)
);

-- Cached aggregates (invalidated every 15 min)
CREATE TABLE stats_cache (
  symbol      TEXT,
  timeframe   TEXT,
  stat_type   TEXT,  -- 'time' | 'distance' | 'summary'
  payload     JSONB,
  computed_at TIMESTAMPTZ,
  PRIMARY KEY (symbol, timeframe, stat_type)
);
```

---

## Realistic Timeline

| Phase | Duration | Cumulative |
|---|---|---|
| Phase 0: Foundation | 2 weeks | Week 2 |
| Phase 1: Time Feature | 2 weeks | Week 4 |
| Phase 2: Distance Feature | 2 weeks | Week 6 |
| Phase 3: Summary Feature | 2 weeks | Week 8 |
| Phase 4: Overview Page | 2 weeks | Week 10 |
| Phase 5: Auth + Deploy | 2 weeks | Week 12 |
| Phase 6: Equity (later) | 3–4 weeks | Week 15–16 |

**Total to public launch (crypto): ~12 weeks working part-time (10–15 hrs/week)**
**Total to full product (+ equity): ~16 weeks**

---

## First Session Checklist (Do This Now)

- [ ] Clone repo locally
- [ ] Create monorepo folders: `backend/`, `frontend/`, `scripts/`, `docs/`
- [ ] Set up `docker-compose.yml` with Postgres + Redis
- [ ] Install FastAPI + CCXT, fetch first OHLCV batch for BTC/USDT
- [ ] Scaffold Next.js frontend
- [ ] Commit and push Phase 0 scaffold

---

## Key Risks

| Risk | Mitigation |
|---|---|
| Exchange API rate limits | Cache aggressively; fetch once per candle close |
| Historical data availability | Use free tier carefully; backfill incrementally |
| Stat accuracy at small sample sizes | Show confidence intervals; warn when N < 30 |
| Scope creep | Ship one feature fully before starting the next |
