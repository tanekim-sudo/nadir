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

The system identifies **Nadir Packages** — companies where five independent signals simultaneously indicate maximum narrative-reality divergence:

| # | Signal | Source | Threshold |
|---|--------|--------|-----------|
| 1 | **Short Interest** | Finviz, IBorrowDesk | >20% of float + top 20% borrow rate |
| 2 | **Analyst Sentiment** | Polygon.io | >70% sell ratings |
| 3 | **Insider Buying** | SEC EDGAR Form 4 | Composite score ≥ 8.0 |
| 4 | **GRR Stability** | SEC EDGAR 10-Q/10-K + Claude | GRR >88% and stable |
| 5 | **Moral Language** | Analyst reports + Claude | Average score >6.0/10 |

When all 5 conditions are met, the system:
1. Builds a 4-layer **Belief Stack** (Surface → Financial → Structural → Axiom)
2. Runs secondary **Validation** to detect false positives
3. Sizes positions using **half-Kelly criterion**
4. Generates a complete **Investment Thesis**
5. Routes for **human approval** (live trades always require approval)

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
│   │   ├── models/         # 8 database models
│   │   ├── routers/        # FastAPI route handlers
│   │   ├── schemas/        # Pydantic request/response models
│   │   ├── services/       # Core business logic
│   │   │   ├── universe_manager.py      # ETF holdings sync
│   │   │   ├── signal_collectors.py     # 5 signal collectors
│   │   │   ├── belief_stack_builder.py  # 4-layer analysis
│   │   │   ├── nadir_validator.py       # False positive detection
│   │   │   ├── position_sizer.py        # Half-Kelly sizing
│   │   │   ├── trade_executor.py        # Alpaca integration
│   │   │   ├── exit_monitor.py          # 5 exit conditions
│   │   │   ├── thesis_generator.py      # AI thesis generation
│   │   │   ├── prediction_registry.py   # Track & resolve predictions
│   │   │   ├── analytics.py             # Performance metrics
│   │   │   └── nadir_agent.py           # Pipeline orchestrator
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
3. **Company Detail** (`/company/{ticker}`) — Deep-dive with 5 tabs: Signals (radar chart), Belief Stack, Thesis, Predictions, History
4. **Positions** (`/positions`) — Open/closed positions, equity curve, win rate chart
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
| GET | `/api/beliefs/{ticker}` | Belief stack |
| POST | `/api/beliefs/{ticker}/refresh` | Rebuild beliefs |
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
- **GRR falsification** — Auto-exit if GRR drops below floor
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
