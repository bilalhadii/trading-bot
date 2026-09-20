# AGENTS.md — AI Trading System

## Role of Codex

You are the coding and research agent for this repository. Work directly on the local codebase, run tests/backtests when appropriate, and preserve reproducibility.

The human owner prefers hands-on, step-by-step development. Before making significant changes, explain what will change and why. For risky or multi-file changes, inspect the existing implementation first.

## Project Goal

Build and validate a deterministic algorithmic trading system, then progressively add context and ML only after the deterministic strategy has a demonstrated out-of-sample edge.

Current conceptual strategy path:

PDH/PDL -> liquidity interaction/sweep -> ORB breakout -> retest -> confirmation -> entry -> exit

Do not jump directly to ML or a large feature stack. Change one major idea at a time.

## Current Development Stage

The current control strategy is:

`ORB_BASELINE_2R`

The next strategy to implement is:

`ORB_RETEST_2R`

The baseline must remain unchanged and serve as the control for every experiment.

## Environment

- OS: macOS
- Editor: VS Code
- Python: 3.12.14
- Git: 2.39.5
- PostgreSQL: 16.15 (Homebrew)
- Database: `ai_trading`
- Python virtual environment: `.venv`
- Alpaca SDK: `alpaca-py 0.44.0`
- Market data source: Alpaca
- Paper trading account is configured
- Timezone for strategy logic: `America/New_York`

Known dependencies include:
- pandas
- numpy
- SQLAlchemy
- psycopg2
- python-dotenv
- pytz
- alpaca-py

Never expose or commit credentials from `.env`.

## Repository Structure

Current structure:

```text
ai-trading-system/
├── .env
├── .gitignore
├── database/
│   ├── __init__.py
│   └── connection.py
├── data/
│   ├── __init__.py
│   ├── alpaca_client.py
│   ├── db_writer.py
│   ├── validator.py
│   └── historical_downloader.py
├── strategy/
│   ├── __init__.py
│   ├── session.py
│   ├── orb.py
│   ├── signals.py
│   ├── daily_levels.py
│   └── trade_setup.py
├── backtest/
│   ├── __init__.py
│   ├── engine.py
│   ├── storage.py
│   ├── excursion.py
│   └── metrics.py
├── scripts/
│   ├── __init__.py
│   ├── download_data.py
│   ├── download_historical.py
│   ├── test_orb.py
│   ├── run_backtest.py
│   └── compare_pdh.py
└── tests/
```

## Data Layer

Main table:

```sql
CREATE TABLE IF NOT EXISTS market_candles (
    id BIGSERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    open NUMERIC(20, 8) NOT NULL,
    high NUMERIC(20, 8) NOT NULL,
    low NUMERIC(20, 8) NOT NULL,
    close NUMERIC(20, 8) NOT NULL,
    volume BIGINT NOT NULL,
    trade_count BIGINT,
    vwap NUMERIC(20, 8),
    UNIQUE (ticker, timestamp)
);

CREATE INDEX IF NOT EXISTS idx_market_candles_ticker_timestamp
ON market_candles (ticker, timestamp);
```

`db_writer.py` uses an idempotent insert pattern with:

```sql
ON CONFLICT (ticker, timestamp) DO NOTHING
```

Data validation checks:
- non-empty data
- required columns
- timezone-aware timestamps
- chronological sorting
- duplicates
- high >= low
- nonnegative volume

Raw Alpaca data contains extended-hours candles. Strategy logic filters to the regular US equity session.

AAPL 2024 data currently loaded:
- 187,812 total 1-minute bars
- first timestamp: 2024-01-02 01:00:00-08
- last timestamp: 2024-12-31 15:53:00-08

Regular-session shortened days observed:
- 2024-07-03: 361 bars
- 2024-11-29: 324 bars
- 2024-12-24: 306 bars

Current backtester skips sessions where regular-session bar count is not 390. This is temporary. A proper official market calendar should be added later.

## Session / ORB Definition

Regular session:
- 09:30 to 16:00 America/New_York

Opening range:
- first 5 one-minute candles
- 09:30 through 09:34
- breakout evaluation starts at 09:35

ORB is represented by:
- OR open
- OR close
- OR high
- OR low
- OR range
- OR volume

Current signal definition:
- LONG when a candle CLOSE is above OR high
- SHORT when a candle CLOSE is below OR low
- entry is at the NEXT candle OPEN to avoid look-ahead
- one trade per ticker per day

## Previous-Day Levels

`daily_levels.py` calculates regular-session:
- daily high
- daily low
- previous-day high (`pdh`)
- previous-day low (`pdl`)

Example already verified:
For AAPL:
- 2024-01-02 high = 188.44
- 2024-01-02 low = 183.885
- 2024-01-03 PDH = 188.44
- 2024-01-03 PDL = 183.885

## Baseline Trade / Exit Logic

`ORB_BASELINE_2R`:
- all first confirmed ORB breakouts are eligible
- fixed 2R target
- stop is the opposite OR boundary
- one trade per ticker per day
- if neither stop nor target is reached, close at regular-session close
- if both stop and target are touched in the same candle, current conservative rule assumes stop first

Current risk convention:
- `risk` is the per-share price distance between entry and stop
- current `pnl` is therefore per-share P&L, NOT account-dollar P&L
- account sizing and dollar P&L are deferred until the strategy edge is validated

Do not change these definitions when comparing new strategies unless explicitly requested.

## Backtest Trade Schema

Current table:

```sql
CREATE TABLE IF NOT EXISTS backtest_trades (
    id BIGSERIAL PRIMARY KEY,
    strategy_version VARCHAR(50) NOT NULL,
    ticker VARCHAR(10) NOT NULL,
    trade_date DATE NOT NULL,
    direction VARCHAR(10) NOT NULL,
    signal_time TIMESTAMPTZ NOT NULL,
    entry_time TIMESTAMPTZ NOT NULL,
    exit_time TIMESTAMPTZ,
    entry_price NUMERIC(20, 8) NOT NULL,
    stop_price NUMERIC(20, 8) NOT NULL,
    target_price NUMERIC(20, 8) NOT NULL,
    exit_price NUMERIC(20, 8),
    risk_amount NUMERIC(20, 8),
    pnl NUMERIC(20, 8),
    r_multiple NUMERIC(20, 8),
    outcome VARCHAR(20)
);
```

There is a uniqueness rule:

```sql
UNIQUE (strategy_version, ticker, trade_date)
```

Storage uses upsert behavior so rerunning a strategy refreshes the row rather than creating duplicates.

## Bugs Already Fixed

### 1. Missing signal_time
`backtest_trades.signal_time` was added to the database.

### 2. Duplicate trade append
A bug had caused duplicate in-memory trade execution counts even though the DB uniqueness constraint kept one row per day. The duplicate append was removed.

### 3. Breakout counter
Breakouts must be counted immediately after a breakout is detected and BEFORE optional filters such as early-breakout windows are applied.

Correct ordering:

```python
if breakout is None:
    continue

breakouts += 1

# optional filters after this point
```

### 4. MAE/MFE timing bug
MAE/MFE originally examined candles after the trade had already exited, creating impossible excursion values.

`calculate_excursion` was changed to accept both:
- `entry_time`
- `exit_time`

and restrict measurement to:

```text
entry_time <= candle timestamp <= exit_time
```

### 5. Backtest heading
`run_backtest.py` should print the actual strategy version:

```python
print("=" * 60)
print(f"{STRATEGY_VERSION} BACKTEST")
print("=" * 60)
```

### 6. Drawdown authority
SQL currently reports the authoritative full-year AAPL 2024 maximum drawdown of:

`-17.39442940R`

Python drawdown ordering should match SQL using:
- trade_date
- entry_time

or another deterministic tie-breaker that is consistent with storage. Reconcile discrepancies before trusting Python metrics.

## Validated AAPL 2024 Baseline Results

Strategy:
`ORB_BASELINE_2R`

Trades:
`247`

Total R:
`+2.43602023R`

Profit factor:
`1.0217625`

Maximum drawdown:
`-17.39442940R`

The strategy is NOT considered production-ready. The small positive full-year return combined with very large drawdown and strong regime changes means the baseline is a research control, not a deployable strategy.

## Full-Year Direction Split

AAPL 2024:

### LONG
- trades: 122
- total R: +11.6588R
- average R: +0.09556R
- positive trades: 56
- target hits: 17
- stop hits: 42

### SHORT
- trades: 125
- total R: -9.2228R
- average R: -0.07378R
- positive trades: 49
- target hits: 19
- stop hits: 55

This is an important observed pattern, NOT permission to hard-code a long-only or short-only rule. It is in-sample evidence and must be tested out-of-sample.

## H1 / H2 Direction Results

H1 2024:
- LONG: 56 trades, +0.47957343R, avg +0.00856R
- SHORT: 67 trades, +4.31206459R, avg +0.06436R

H2 2024:
- LONG: 66 trades, +11.17924422R, avg +0.16938R
- SHORT: 58 trades, -13.53486201R, avg -0.23336R

The directional behavior therefore changed substantially.

## H1 / H2 Breakout Window Results

H1:
- 09:35-09:45: 93 trades, +5.25499506R, avg +0.05651R
- 09:45-10:00: 19 trades, +0.91910954R, avg +0.04837R
- 10:00-10:30: 7 trades, +0.60031167R, avg +0.08576R
- 10:30+: 4 trades, -1.98277825R, avg -0.49569R

H2:
- 09:35-09:45: 88 trades, -6.55186638R, avg -0.07445R
- 09:45-10:00: 19 trades, +4.95890130R, avg +0.26099R
- 10:00-10:30: 11 trades, -1.70973041R, avg -0.15543R
- 10:30+: 6 trades, +0.94707770R, avg +0.15785R

Do not simply choose the 09:45-10:00 window from these results because that would be in-sample optimization.

## Monthly AAPL 2024 Results

- Jan: +4.4523R
- Feb: +4.4753R
- Mar: -5.7462R
- Apr: -1.3886R
- May: -1.7882R
- Jun: +4.7870R
- Jul: +8.5145R
- Aug: +2.4898R
- Sep: -3.9347R
- Oct: -3.5969R
- Nov: -4.6951R
- Dec: -1.1332R

Largest positive month:
- Jul +8.5145R

Largest negative month:
- Mar -5.7462R

## Equity-Curve Observation

The SQL equity curve reached a running peak of approximately:

`+17.83044963R`

The maximum drawdown reached:

`-17.39442940R`

The drawdown trough occurred on:

`2024-12-30`

with cumulative R around:

`+0.43602023R`

The final trade on 2024-12-31 finished +2R, leaving the year around +2.436R.

This strongly suggests regime instability rather than a stable universal ORB edge.

## Individual Trade Dataset

A complete AAPL 2024 `ORB_BASELINE_2R` trade list was generated and reviewed. It contains:
- 247 trades
- trade_date
- direction
- signal_time
- r_multiple
- outcome

The latest handoff file contains the complete exported list if needed.

## Previously Tested Variants

### ORB_V0
PDH/PDL target with minimum 2R eligibility.
January 2024:
- 7 trades
- +0.5436R

### ORB_V1_BE_1R
Same as V0 with breakeven after +1R.
January 2024:
- same result as V0

### ORB_V2_TP_1R
Same filtered entries, fixed 1R target.
January 2024:
-7 trades
- -1.5832R

### ORB_BASELINE
All raw ORB breakouts, fixed 1R.
January 2024:
-20 trades
- -0.1854R

### ORB_BASELINE_1_5R
January:
-20 trades
- +2.6829R

### ORB_BASELINE_2R
January:
-20 trades
- +4.4523R

### ORB_BASELINE_3R
January:
-20 trades
- +2.2564R

### ORB_BASELINE_2R_EARLY
January only:
-12 trades
- +3.7797R

This should NOT be treated as a robust finding because the early window was discovered from the same sample.

### ORB_BASELINE_PDH
January:
-13 trades
- -2.5106R

This is not an apples-to-apples exit comparison and remains only a context/filter candidate.

## Next Strategy: ORB_RETEST_2R

Implement this as a separate strategy version.

Core sequence:

1. Calculate 5-minute OR.
2. Wait for a confirmed breakout:
   - LONG: candle close > OR high
   - SHORT: candle close < OR low
3. Do NOT enter immediately.
4. Wait for price to pull back toward the broken OR boundary.
5. Detect a valid retest.
6. Require confirmation of rejection/continuation.
7. Enter on the next candle open.
8. Use the same 2R target framework initially.
9. Preserve one-trade-per-day.
10. Keep the original baseline untouched.

Initial retest concept:

### LONG
- breakout close is above OR high
- subsequent price returns to OR high area
- retest should not invalidate the setup by decisively closing back below OR high
- confirmation candle should close bullish / reclaim or hold the boundary
- enter next candle open

### SHORT
- breakout close is below OR low
- subsequent price returns to OR low area
- retest should not invalidate by decisively closing back above OR low
- confirmation candle should close bearish / reject or hold the boundary
- enter next candle open

These definitions are initial research hypotheses. Before coding, inspect current `signals.py`, `trade_setup.py`, `backtest/engine.py`, and `run_backtest.py` so implementation matches existing interfaces.

Do NOT add PDH/PDL sweep, VWAP, volume filters, news, ATR, or ML in the first retest experiment. One major variable at a time.

## Retest Research Controls

When implementing `ORB_RETEST_2R`, explicitly define and record:
- maximum bars allowed between breakout and retest
- acceptable retest tolerance around OR boundary
- invalidation rule
- confirmation candle rule
- entry timing
- stop placement
- target placement

Avoid hidden assumptions.

A good first experiment should use a simple, deterministic tolerance and timeout, then test sensitivity later rather than optimizing dozens of parameters.

## Validation Philosophy

Never select a rule only because it improves 2024 results.

Preferred progression:
1. Develop deterministic logic.
2. Run on a development sample.
3. Freeze major parameters.
4. Validate on unseen data.
5. Prefer walk-forward validation.
6. Include realistic transaction costs and slippage later.
7. Test across multiple liquid symbols.
8. Paper trade before live deployment.

Longer-term split can be:
- 2024 development
- 2025 validation
- 2026 out-of-sample

Or use rolling walk-forward windows.

Do not call an in-sample improvement a proven edge.

## Future Strategy Roadmap

After `ORB_RETEST_2R`:

`ORB_LIQUIDITY_RETEST_2R`
- previous-day high/low interaction or sweep
- ORB breakout
- retest
- confirmation
- entry

Then potentially add, one at a time:
- VWAP
- volume relative to baseline
- gap context
- ATR / volatility regime
- market trend/context
- news/event regime

For event research:
- Rockstar Games itself is not publicly traded.
- Its public parent is Take-Two Interactive (`TTWO`).
- Do not hard-code a bullish event bias.
- Verify event dates/current facts from authoritative sources when implementing event features.

ML comes only after a substantial clean trade dataset exists and deterministic features are stable.

## Engineering Rules

- Preserve backward compatibility with existing strategies.
- Prefer new strategy versions over mutating old versions.
- Avoid look-ahead bias.
- Use timezone-aware timestamps.
- Keep database writes idempotent.
- Make experiments reproducible.
- Log strategy version and important parameters.
- Run focused tests after edits.
- Run the existing baseline after major engine changes to confirm it has not changed.
- Use Git commits as checkpoints.
- Do not expose secrets.
- Do not add unnecessary dependencies.
- Do not silently change the definition of R.

## Immediate Task

The immediate task is NOT to rewrite the repository blindly.

First inspect:
- `strategy/signals.py`
- `strategy/trade_setup.py`
- `backtest/engine.py`
- `backtest/metrics.py`
- `backtest/storage.py`
- `scripts/run_backtest.py`

Then summarize the implementation and identify the minimal files needed to add `ORB_RETEST_2R`.

Only after that should implementation begin.
