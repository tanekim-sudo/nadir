# NADIR — Narrative Adversarial Detection and Investment Recognition

A systematic investment intelligence platform that identifies enterprise technology companies where market narrative has maximally overshot underlying business reality, executes trades when all conditions are confirmed, and learns from outcomes to improve signal accuracy over time.

## Architecture

```
Frontend (Next.js 14)  →  Backend (FastAPI)  →  PostgreSQL
     ↑                        ↓
  Recharts              Celery + Redis  →  Claude AI
  Tailwind CSS               ↓
  NextAuth             Alpaca Trade API
```

## The NADIR System

### Detection Signals (High Frequency)

The system identifies **Nadir Packages** — companies where five independent signals simultaneously indicate maximum narrative-reality divergence:

| # | Signal | Source | Threshold | Why |
|---|--------|--------|-----------|-----|
| 1 | **Short Interest** | Finviz, IBorrowDesk | >20% of float + top 20% borrow rate | Extreme bearish positioning |
| 2 | **Analyst Sentiment** | Polygon.io | >70% sell ratings | Consensus abandonment |
| 3 | **Insider Buying** | SEC EDGAR Form 4 | Composite score ≥ 8.0 | Management conviction signal |
| 4 | **Customer Job Posting Velocity** | Theirstack, SerpAPI | velocity_score > -0.10 | Customers still hiring for the product |
| 5 | **Short Squeeze Probability** | Polygon, Finviz | squeeze_score > 0.65 | Mechanical conditions for violent reversal |

**Signal Design Rationale**: Signals 1-2 measure the intensity of the negative narrative. Signal 3 measures insider conviction against the narrative. Signal 4 measures whether the bear thesis is contradicted by real-world adoption. Signal 5 measures the mechanical conditions for a price reversal.

### Validation Signals (Lower Frequency, Post-Entry)

| Signal | Frequency | Purpose |
|--------|-----------|---------|
| **GRR (Gross Revenue Retention)** | Quarterly (on 10-Q) | Primary falsification check — if GRR drops below floor, thesis is wrong |

GRR was removed from detection because it is too low frequency to use as a screen. It is the most important *ongoing monitoring* signal after a position is entered.

### Constrained Reverse-DCF Belief Stack

When a company reaches WATCH state (3+ conditions), the system runs a **constrained reverse-DCF decomposition**:

1. **Market Price Decomposition**: Calculate EV from price, shares, debt, cash
2. **Solve for Implied Assumptions**: Use `scipy.optimize.minimize` to find the (growth, terminal_margin, WACC) combination that makes a 10-year DCF equal the current EV
3. **Node Decomposition**: Break implied assumptions into a tree of fundamental drivers:
   - **Node A (Revenue Growth)** → A1: TAM, A2: Market Share, A3: Pricing Power, A4: Expansion Revenue
   - **Node B (Terminal Margin)** → B1: Gross Margin, B2: Sales Efficiency, B3: R&D Leverage, B4: Competitive Intensity
   - **Node C (WACC)** → C1: Business Risk, C2: Financial Risk, C3: Execution Risk
4. **Evidence Scoring**: Each leaf node is scored against observable evidence (direction, confidence, gap magnitude)
5. **Conviction Scoring**: `conviction = gap_magnitude × confidence_weight` identifies the primary mispricing node
6. **Quantitative Variant View**: "The market prices Node X at Y. Evidence suggests Z. If corrected, fair value implies W% upside."

### Pipeline Schedule

| Time (ET) | Stage |
|-----------|-------|
| 5:00 AM Mon | Customer job posting velocity (weekly) |
| 6:00 AM | Short interest + squeeze probability |
| 6:15 AM | Analyst sentiment + insider buying |
| 7:00 AM | DCF decomposition (WATCH+ companies) |
| 7:30-7:45 AM | Score belief stack nodes, calculate conviction |
| 8:00 AM | Evaluate 5 Nadir conditions (full universe) |
| 8:15-8:45 AM | Validate, size, create approval alerts |
| 9:00 AM | Exit monitor (GRR falsification, stop loss, time limit) |
| 9:15 AM | Predictions + daily digest |

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 20+
- Docker & Docker Compose
- API keys: Anthropic, Polygon.io, Alpaca

### Setup

```bash
# Clone and configure
cp .env.example .env
# Edit .env with your API keys

# Option 1: Full Docker
docker compose up --build

# Option 2: Local development
make setup
make dev
```

### Access
- **Frontend**: http://localhost:3000
- **API Docs**: http://localhost:8000/api/docs
- **API Health**: http://localhost:8000/api/health

## Project Structure

```
NADIR/
├── backend/
│   ├── app/
│   │   ├── core/           # Config, Celery, Claude client
│   │   ├── db/             # SQLAlchemy session
│   │   ├── models/         # Database models (13 tables)
│   │   ├── routers/        # FastAPI route handlers
│   │   ├── schemas/        # Pydantic request/response models
│   │   ├── services/       # Core business logic
│   │   │   ├── universe_manager.py              # ETF holdings sync
│   │   │   ├── signal_collectors.py             # SI, AS, IB collectors + GRR monitoring
│   │   │   ├── customer_job_posting_velocity.py # Job posting velocity signal
│   │   │   ├── short_squeeze_probability.py     # Squeeze probability signal
│   │   │   ├── belief_stack_engine.py           # Constrained reverse-DCF engine
│   │   │   ├── nadir_validator.py               # False positive detection
│   │   │   ├── position_sizer.py                # Half-Kelly sizing
│   │   │   ├── trade_executor.py                # Alpaca integration
│   │   │   ├── exit_monitor.py                  # Exit conditions (GRR falsification)
│   │   │   ├── thesis_generator.py              # AI thesis generation
│   │   │   ├── prediction_registry.py           # Track & resolve predictions
│   │   │   ├── analytics.py                     # Performance metrics
│   │   │   └── nadir_agent.py                   # Pipeline orchestrator
│   │   └── main.py         # FastAPI application
│   ├── alembic/            # Database migrations
│   ├── tests/              # Test suite
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── app/            # Next.js pages (6 pages)
│   │   ├── components/     # Shared UI components
│   │   └── lib/            # API client & hooks
│   └── Dockerfile
├── docker-compose.yml
├── Makefile
└── .env.example
```

## Dashboard Pages

1. **Command Center** (`/`) — Real-time overview: stats, state distribution, live alerts, top companies, open positions
2. **Universe** (`/universe`) — Searchable/filterable table of all tracked companies
3. **Company Detail** (`/company/{ticker}`) — Deep-dive with 5 tabs: Signals (radar chart), Belief Stack (DCF tree), Thesis, Predictions, History
4. **Positions** (`/positions`) — Open/closed positions with GRR monitoring, equity curve, win rate
5. **Predictions** (`/predictions`) — Prediction registry with calibration chart
6. **Analytics** (`/analytics`) — Signal performance, Kelly calibration, cumulative returns

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/universe` | List all companies |
| GET | `/api/universe/{ticker}` | Company detail |
| POST | `/api/universe/add` | Add ticker |
| DELETE | `/api/universe/{ticker}` | Remove ticker |
| GET | `/api/signals/{ticker}` | Current signals |
| GET | `/api/signals/{ticker}/history` | Signal history |
| POST | `/api/signals/refresh/{ticker}` | Manual refresh |
| GET | `/api/nadir/watchlist` | 3+ conditions |
| GET | `/api/nadir/complete` | All 5 conditions |
| GET | `/api/nadir/{ticker}/validate` | Run validation |
| GET | `/api/nadir/{ticker}/thesis` | Get/generate thesis |
| GET | `/api/beliefs/{ticker}` | Belief stack (DCF tree + nodes) |
| POST | `/api/beliefs/{ticker}/refresh` | Rebuild DCF decomposition |
| GET | `/api/positions` | Open positions |
| POST | `/api/positions/{ticker}/approve` | Approve trade |
| POST | `/api/positions/{ticker}/exit` | Manual exit |
| GET | `/api/predictions` | All predictions |
| POST | `/api/predictions` | Create prediction |
| PUT | `/api/predictions/{id}/resolve` | Record outcome |
| GET | `/api/alerts` | Unreviewed alerts |
| GET | `/api/alerts/stream` | SSE real-time feed |
| GET | `/api/analytics/performance` | Performance data |
| GET | `/api/analytics/signals` | Signal accuracy |
| GET | `/api/analytics/kelly` | Kelly calibration |

## Safety Features

- **Paper trading by default** — Set `ALPACA_LIVE=true` to enable live trading
- **Human approval gate** — All live trades require dashboard approval
- **Position limits** — Max 20% per position, max 80% total exposure
- **Half-Kelly sizing** — Conservative position sizing
- **Auto stop-loss** — Positions auto-close at -35%
- **GRR falsification** — Auto-exit if GRR drops below floor (post-entry monitoring)
- **Conviction shift alerts** — Alerts when primary mispricing node conviction changes >0.15
- **Minimum edge threshold** — Skips positions where Kelly < 5%

## Testing

```bash
cd backend
python -m pytest tests/ -v
```

## Makefile Commands

```
make setup    — Install dependencies, run migrations
make dev      — Start all services locally
make scan     — Trigger manual scan
make test     — Run test suite
make logs     — Tail Docker logs
make stop     — Stop all services
make clean    — Stop and remove data
```

## License

Proprietary. All rights reserved.
