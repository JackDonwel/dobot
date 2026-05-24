[README.md](https://github.com/user-attachments/files/28190453/README.md)
# TBot — Multi-Agent AI Trading System

**Version 0.2.0** — LangGraph orchestration with LLM backbone for automated forex trading during the London session.

TBot uses three specialized AI agents (Analyst → Executor → Critic) connected by a LangGraph state machine to analyze major forex pairs, execute trades, and learn from outcomes. Supports local LLMs (Ollama), cloud LLMs (OpenAI), or rule-based mock mode.

---

## Features

- **3-Agent Pipeline** — Analyst researches and generates signals; Executor validates and executes; Critic reviews outcomes and stores lessons
- **Multi-Provider LLM** — OpenAI, Ollama (local), or mock (rule-based) — zero API cost for testing
- **Live Market Data** — yfinance integration for real forex data (EUR/USD, GBP/USD) with automatic synthetic fallback
- **MetaApi Ready** — Codebase includes full MetaApi SDK wrapper for real MetaTrader data and trade execution (requires valid token)
- **Memory & Learning** — SQLite trade log + ChromaDB vector store for lessons learned; fine-tuning dataset export
- **Web Dashboard** — FastAPI dark-themed UI at `http://127.0.0.1:8080` with live prices, trade history, news, and quick actions
- **London Session Aware** — Time-windowed execution; respects session hours configurable via `.env`
- **Risk Controls** — Configurable risk-per-trade, minimum R:R ratio, stop-loss/take-profit calculation

---

## Architecture

```
┌──────────┐    ┌──────────┐    ┌──────────┐
│ Analyst  │───▶│ Executor │───▶│  Critic  │
│ (signal  │    │ (validate│    │ (review  │
│  + setup)│    │  + trade)│    │  + learn)│
└──────────┘    └──────────┘    └──────────┘
     │               │               │
     ▼               ▼               ▼
  Market Data     Broker          Memory
  (yfinance /     (paper /       (SQLite +
   MetaApi)        MetaApi)       ChromaDB)
```

Data flows left-to-right through a LangGraph `StateGraph`. Each agent is a typed Python node, state is a Pydantic model. Outputs are persisted to SQLite (trades) and ChromaDB (lessons).

---

## Installation

### Prerequisites
- Python 3.11+
- (Optional) [Ollama](https://ollama.ai) for local LLM inference

### Quick Start

```bash
git clone https://github.com/yourusername/tbot.git
cd tbot
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

The `tbot` CLI will be available in your venv. To make it globally accessible:

```bash
ln -s "$(pwd)/.venv/bin/tbot" ~/.local/bin/tbot
# Ensure ~/.local/bin is on your PATH
```

### Optional Dependencies

For MetaTrader live trading via MetaApi:
```bash
pip install metaapi-cloud-sdk
```

---

## Configuration

Copy and edit the environment file:

```bash
cp .env.example .env
```

Key settings:

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `mock` | `openai`, `ollama`, or `mock` |
| `OPENAI_API_KEY` | — | Required if using OpenAI |
| `OLLAMA_MODEL` | `qwen2.5:14b` | Model for local inference |
| `ACCOUNT_BALANCE` | `10000.0` | Paper trading starting balance |
| `RISK_PER_TRADE` | `0.01` | 1% risk per trade |
| `MIN_REWARD_RATIO` | `4.0` | Minimum 1:4 risk-to-reward |
| `MAJOR_PAIRS` | `["EUR/USD","GBP/USD"]` | Pairs to analyze |
| `DATA_PROVIDER` | `auto` | `auto`, `metaapi`, `yfinance`, `synthetic` |

### MetaApi (Real Trading)

To connect a live MetaTrader account:

1. Get a JWT token from [app.metaapi.cloud/token](https://app.metaapi.cloud/token)
2. Set your MetaTrader account ID and region:

```env
META_API_TOKEN=your-jwt-token
META_API_ACCOUNT_ID=your-metaapi-account-id
META_API_REGION=new-york
DATA_PROVIDER=auto
```

> **Note**: The MetaApi integration code is complete but requires a valid, active token. See [MetaApi Integration](#metaapi-integration) below.

---

## Usage

### CLI Commands

```bash
# Full London-session analysis of all major pairs
tbot run

# Analyze a single pair
tbot once EUR/USD

# Quick system status
tbot status

# Launch web dashboard
tbot dashboard --port 8080

# Continuous monitoring during session hours
tbot watch
```

### Web Dashboard

Start the dashboard:

```bash
tbot dashboard
```

Open [http://127.0.0.1:8080](http://127.0.0.1:8080) to see:
- System status (LLM provider, account balance, trade stats)
- Live forex prices with change indicators
- Trade history table
- Learning lessons from past trades
- News ticker with sentiment
- Quick-action buttons (analyze pair, run session)

---

## Data Sources

| Source | Description | Status |
|--------|-------------|--------|
| **yfinance** | Real forex data via Yahoo Finance | ✅ Default — works out of the box |
| **Synthetic** | Procedural price generation with trends/jitter | ✅ Automatic fallback |
| **MetaApi** | Real MetaTrader data via metaapi-cloud-sdk | ⚠️ Code ready, token auth pending |

The `DATA_PROVIDER=auto` setting tries MetaApi first, falls back to yfinance, then synthetic.

---

## MetaApi Integration

The codebase includes complete MetaApi integration (`metaapi_provider.py`, `metaapi_broker.py`) supporting:

- **Market Data** — `get_historical_candles()`, `get_current_price()`, `account_summary()`
- **Trade Execution** — `place_market_order()`, `close_position()` via MetaTrader
- **Automatic Deployment** — Deploys and connects MetaTrader accounts on demand
- **Resampling** — 1H → 4H candle resampling built in

**Current status**: The MetaApi SDK v29.1.1 is installed and the wrapper code is complete, but the JWT token returns `401 Unauthorized`. Verify your token is active at [app.metaapi.cloud/token](https://app.metaapi.cloud/token).

---

## Project Structure

```
src/tbot/
├── agents/        # Analyst, Executor, Critic nodes
│   ├── analyst.py
│   ├── executor.py
│   └── critic.py
├── core/          # LangGraph state machine
│   ├── graph.py
│   └── session.py
├── memory/        # Persistence layer
│   ├── store.py
│   └── chroma_store.py
├── models/        # Pydantic schemas + config
│   ├── config.py
│   └── schemas.py
├── tools/         # External integrations
│   ├── market.py            # yfinance + synthetic data
│   ├── metaapi_provider.py  # MetaApi data adapter
│   ├── metaapi_broker.py    # MetaApi trade execution
│   ├── broker.py            # Paper broker + factory
│   ├── news.py              # RSS news + sentiment
│   └── positioning.py       # Position sizing
├── web/           # FastAPI dashboard
│   └── app.py
└── cli.py         # CLI entry point
```

---

## Technology Stack

| Component | Technology |
|-----------|------------|
| Orchestration | LangGraph |
| LLM Interface | LangChain (OpenAI / Ollama / Mock) |
| Market Data | yfinance, MetaApi SDK |
| Persistence | SQLite (trades), ChromaDB (lessons) |
| Web UI | FastAPI + vanilla JS (embedded) |
| Backend | Python 3.11+, Pydantic, httpx |

---

## License

MIT
