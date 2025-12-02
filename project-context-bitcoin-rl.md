# Meta-Level Strategy for Managing Multiple Bitcoin Trading Strategies

## Concept
This project defines a **meta-level (top) strategy** that manages and coordinates several independent Bitcoin trading strategies. Each strategy runs separately (as a microservice or module), produces its own trading recommendation, and the meta-strategy decides how to combine these recommendations into a single trading action.

The target market is **Bitcoin futures** so that the system can:
- go long
- go short
- stay flat/hold

---

## Main Components

### 1. Strategy Services (Microservices)
- Each trading idea/logic is implemented as an independent strategy service (Python-based).
- Strategies will be sourced from existing, proven open-source algo-trading codebases (after manual review).
- Each strategy is called at runtime and returns a structured **recommendation** for the current time step.
- We have **not** finalized the exact output schema of a strategy yet — only that it will be unified so the meta-engine can consume it.
- The purpose is to combine *already working* or *already defined* strategies, not to reinvent every signal from scratch.

#### Strategy Candidates (to be wrapped as microservices)

1. **Technical strategies**  
   - Trend / Moving Averages
   - Volatility / Breakout
   - Simple mean-reversion around VWAP/range

2. **Flows / On-exchange data**  
   - Exchange inflows
   - Exchange outflows

3. **Derivatives-based**  
   - Funding rate extremes
   - Open interest spikes / perp–spot imbalance

4. **News / Event-driven**  
   - Detect breaking crypto/BTC news from major sources  
   - Mark news-related windows as “high attention”

5. **Social / Sentiment**  
   - Spikes in BTC mentions  
   - Basic positive/negative sentiment

#### Strategies Already Selected for POC Implementation

1. **Volatility System**- ATR-based breakout detector that identifies strong volatility expansions and signals directional entries.

2. **Supertrend Strategy**- Trend-following system using three Supertrend layers with optimized parameters to confirm trend direction.

3. **OTT Strategy**- Optimized Trend Tracker that uses CMO-based smoothing to detect early trend shifts and clean reversal signals.

4. **BbandRsi**- Mean-reversion strategy combining Bollinger Bands and RSI; enters on oversold conditions and exits on overbought signals.

#### Tick & Timeframe Management

- The system uses a **cron-based tick scheduler** (APScheduler) that runs independently of strategy timeframes.
- The global tick frequency is defined by `GLOBAL_TICK` in `config.py` (e.g., "1m"), which determines how often the tick cycle executes.
- Each tick cycle performs the following steps:
   1. **Sync market data** from exchange to database
   2. **Determine which strategies should run** based on the current time
   3. **Prepare data** for scheduled strategies
   4. **Execute strategies in parallel**
- Strategies are defined in `strategies_registry.json` with their own `timeframe` (e.g., "1h", "4h").
- A strategy only executes when the current time aligns with its timeframe boundary:
   - Example: A "1h" strategy runs at 00:00, 01:00, 02:00, etc. (when `minutes_now % 60 == 0`)
   - Strategies that don't align with the current tick are skipped entirely (not invoked at all)
- This design allows flexible tick frequencies (e.g., 1-minute ticks) while strategies execute at their own intervals.

#### Centralized Data Management

- The system stores only `MIN_TIMEFRAME` raw candles in the database, defined in `config.py` (e.g., "1h").
- Database storage uses PostgreSQL with TimescaleDB hypertables for time-series optimization.
- Historical data retention is controlled by `MAX_LOOKBACK_HOURS` (e.g., 720 hours = 30 days).
- Each strategy declares in `strategies_registry.json`:
   - `timeframe`: The candle interval it operates on (e.g., "1h", "4h")
   - `lookback_hours`: How many hours of historical data it requires (e.g., 66 hours)
- Data preparation happens once per tick for all scheduled strategies:
   1. **Load base data** from database using `MIN_TIMEFRAME` and `MAX_LOOKBACK_HOURS`
   2. **Resample** the base data to each strategy's specific timeframe using pandas resampling
   3. **Calculate bars needed**: `bars = lookback_hours * 60 / timeframe_minutes`
   4. **Trim** the resampled data to the exact number of bars each strategy needs
   5. Return a data map: `{strategy_name: prepared_dataframe}`
- Market data sync is idempotent and incremental:
   - Initial load: `initialize_market_data()` fetches full historical range
   - Periodic sync: `sync_market_data()` fetches only new candles since last DB entry
   - Old data pruning: Automatic cleanup keeps only `MAX_LOOKBACK_HOURS` of data

### 2. RL-Based Decision Engine
- Above the strategy services sits a **Reinforcement Learning (RL)** engine that chooses the final action.  
- We will conduct a **dedicated research phase** to determine which **RL algorithm** (e.g., PPO, A2C, SAC, DDPG, etc.) best fits our problem characteristics and available data.  
- A separate study will be performed on how to optimally define the **Action**, **State**, and **Reward** spaces to reflect real trading dynamics and avoid overfitting.  
- The current plan is to use **FinRL** as the main RL framework, given its finance-oriented environments and built-in support for multiple algorithms.  
- The RL environment will be customized so that its **observation** is essentially “what all strategies said right now” plus a few global fields (e.g., current position, volatility).  
- The RL **action space** will be a **limited, predefined set** of actions (e.g., increase exposure, decrease exposure, stay flat, possibly reverse). We are **not** locking to “always buy/sell full position.”  
- Whenever a **new strategy** is added to the system, the RL model will be **retrained** so it can learn all permutations/combinations of the available strategies.  
- There will also be **periodic retraining** (daily/weekly) to re-align the meta-strategy with current market conditions.

### 3. RL Training Engine (Offline Training Project)

A separate project will be created specifically for **training RL models**.  
This project will run locally on developers’ laptops (CLI-only) or, in the future, on cloud compute environments.  
It will connect to the main project server- and therefore also to the client- through the cloud.

#### Training Workflow
1. **Download raw market data**  
   Pull historical candles from the exchange for the full training period.

2. **Run all strategies over historical data**  
   Each strategy is executed across the defined training window, and its outputs are collected into a unified structure that becomes part of the **FinRL state vector**.

3. **Download additional data / indicators**  
   Collect any extra features needed for RL.

4. **Feature engineering & preprocessing**  
   Use FinRL’s `FeatureEngineer` / `DataProcessor` to construct a clean feature set.  
   Output: a DataFrame formatted for FinRL crypto environments alongside the strategy outputs.

5. **Split data**  
   Create train/test windows and prepare the FinRL crypto trading environment.

6. **Train multiple ElegantRL models**  
   Train several candidate algorithms (e.g., PPO, A2C, SAC) for comparison.

7. **Testing / Trading (out-of-sample)**  
   Evaluate each model on untouched data **without any fine-tuning** to avoid data leakage or overfitting.

8. **Backtest & evaluation**  
   Run backtests, compute metrics (Sharpe, max drawdown, win-rate), and summarize performance.

#### Model Storage & Deployment

- All *evaluation results* will be uploaded to the cloud DB for display in the client GUI.  
- **Model files themselves remain local** on the training machine to save cloud storage.  
- The GUI will highlight the best-performing model based on evaluation metrics.  
- Once selected, that model will be **uploaded to the cloud DB** and delivered to the live trading engine.  
- This approach allows:
  - parallel training runs by multiple developers
  - minimal cloud compute usage
  - minimal DB storage footprint 
  - simple version management (model list stored in DB; uploading occurs only when selecting a model).

### 4. Exchange Integration
- Actual order placement will be done via **CCXT**.
- Primary exchange for now: **Kraken**.
- Using CCXT keeps the system exchange-agnostic and lets us switch or add exchanges with minimal changes.
- Trading is intended for **Bitcoin futures** to support long/short/flat flows.

### 5. Runtime Environment
- The **server-side part** of the project will run on **AWS**, most likely on a **Kubernetes cluster**.
- Each trading strategy will run as its **own pod** (separate deployable unit), so strategies stay isolated and can be updated independently.
- Strategy pods will be invoked **concurrently** to minimize latency in each decision cycle.
- The **client-side part** is a separate desktop application (Java/JavaFX) that connects to the server-side services for monitoring and control.

### 6. Client Application
- A **desktop GUI** is planned, built in **Java / JavaFX**.
- Purpose: monitor system state and executed actions; chart embedding is planned but not finalized yet (we may later feed Kraken data into the chart and overlay trades).

---

## Performance Considerations
- We will use **multi-threading / concurrency** specifically for **invoking multiple strategy services in parallel**, so the meta-engine can get all recommendations in one time window.
- The actual **RL decision** and **order execution** will remain controlled/sequential to keep consistency and avoid race conditions with real funds.

---

## Not Yet Finalized
- **Strategy output schema**: we know it must be unified, but exact fields (e.g. confidence, horizon) are not fixed yet.  
- **RL research phase**: we will perform a dedicated research phase to determine which **Reinforcement Learning algorithm** (e.g., PPO, A2C, SAC, DDPG, etc.) best fits our trading framework.  
- **RL environment design**: we will also study how to optimally define the **Action**, **State**, and **Reward** spaces to ensure effective learning and prevent overfitting.  
- **Risk controls**: max position, daily loss caps, etc. have **not** been defined yet — this will be added once the basic loop runs.  

---

## Technologies (current choice)
- **Python** — strategy services and server-side logic
- **FinRL** — main RL engine for training/decision learning
- **CCXT** — exchange/execution layer (Kraken first)
- **Java / JavaFX** — desktop client/GUI
- **AWS** — hosting/running strategy services in parallel
- **Kubernetes + Helm** — orchestration and packaging (one pod per strategy)
- **GitHub Actions** — CI for building, testing, and publishing service images
- **ArgoCD** — GitOps-based CD for deploying updated services to the Kubernetes cluster
- **1Password** — secure storage and sharing of secrets, especially exchange API keys

---

## Repository & Project Management (GitHub)
- **GitHub Repositories** — Repository structure is still open (single monorepo vs. multiple repos).
- **GitHub Projects / Issues** — for task management, backlog, and tracking new strategies to be onboarded.
- **GitHub Actions (CI)** — automated builds, tests, linting, and container image creation on each push/PR.
- **ArgoCD (CD)** — pulls from the GitHub repos and syncs to the Kubernetes cluster (GitOps flow).

---

## Algorithm POC Environment & Setup

A Proof-of-Concept (POC) implementation of the algorithmic engine has begun.  
The initial development environment and project structure are defined as follows:

### Development Environment
- **IDE:** PyCharm (Professional)
- **Python Version:** 3.11.7  
- **Virtual Environment:** `.venv` created and managed directly through PyCharm (no external conda/poetry).
- **Dependency Policy:**  
  - Install all packages via PyCharm’s package management GUI.  
  - Avoid external environment managers unless required for production later on.

---
## Database Infrastructure

- **PostgreSQL 16.11** with **TimescaleDB 2.23.1** extension
- Time-series optimizations: hypertables, resampling, 90% compression
- ACID-compliant for orders/metadata + time-series performance for OHLCV candles
- Python: **psycopg2-binary 2.9.9**, **SQLAlchemy 2.0.23**

---

## Purpose of this Document
This document is meant to give LLMs full context about:
- what the project is trying to achieve,
- what components already exist conceptually,
- which tools/libraries have been chosen,
- and which parts are intentionally *not* finalized yet.

It should be used as a high-level description of the system’s architecture and intent, not as a final implementation spec.