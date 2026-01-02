# Trading System Workflows

**Date:** January 1, 2026  
**Version:** 1.0

---

## Table of Contents

1. [Daily Trading Workflow](#daily-trading-workflow)
2. [Pre-Flight Check Workflow](#pre-flight-check-workflow)
3. [Signal Generation & Execution Workflow](#signal-generation--execution-workflow)
4. [P&L Attribution Workflow](#pnl-attribution-workflow)
5. [Safety Systems Workflow](#safety-systems-workflow)
6. [Email Notification Workflow](#email-notification-workflow)

---

## Daily Trading Workflow

```
┌─────────────────────────────────────────────────────────────┐
│                    GitHub Actions Trigger                    │
│              (1:15 PM PST / 4:15 PM EST Daily)              │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    Pre-Flight Checks                         │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ 1. Market Open? (weekday, not holiday)              │  │
│  │ 2. Data Fresh? (< 96 hours old)                     │  │
│  │ 3. Database Accessible?                             │  │
│  │ 4. Safety Systems OK?                               │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────┘
                         │
                    ┌────┴────┐
                    │  Pass?  │
                    └────┬────┘
                         │
            ┌────────────┼────────────┐
            │ NO                      │ YES
            ▼                         ▼
    ┌───────────────┐        ┌────────────────┐
    │ Skip Trading  │        │ Update Data    │
    │ Exit 0        │        │ (if needed)    │
    └───────────────┘        └────────┬───────┘
                                      │
                                      ▼
                             ┌─────────────────┐
                             │ Execute Trading │
                             └────────┬────────┘
                                      │
                                      ▼
                             ┌─────────────────┐
                             │ Generate Email  │
                             └────────┬────────┘
                                      │
                                      ▼
                             ┌─────────────────┐
                             │   Send Email    │
                             └────────┬────────┘
                                      │
                                      ▼
                             ┌─────────────────┐
                             │ Upload Artifacts│
                             └─────────────────┘
```

---

## Pre-Flight Check Workflow

```
┌─────────────────────────────────────────────────────────────┐
│                    Pre-Flight Check Start                    │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
                ┌─────────────────┐
                │ Check Market    │
                │ Open Status     │
                └────────┬────────┘
                         │
                    ┌────┴────┐
                    │Weekend? │
                    └────┬────┘
                         │
            ┌────────────┼────────────┐
            │ YES                     │ NO
            ▼                         ▼
    ┌───────────────┐        ┌────────────────┐
    │ Exit: Weekend │        │ Check Holiday  │
    └───────────────┘        └────────┬───────┘
                                      │
                                 ┌────┴────┐
                                 │Holiday? │
                                 └────┬────┘
                                      │
                         ┌────────────┼────────────┐
                         │ YES                     │ NO
                         ▼                         ▼
                 ┌───────────────┐        ┌────────────────┐
                 │ Exit: Holiday │        │ Check Data Age │
                 └───────────────┘        └────────┬───────┘
                                                   │
                                              ┌────┴────┐
                                              │ Stale?  │
                                              └────┬────┘
                                                   │
                                      ┌────────────┼────────────┐
                                      │ YES                     │ NO
                                      ▼                         ▼
                              ┌───────────────┐        ┌────────────────┐
                              │ Try Update    │        │ Check Database │
                              └────────┬──────┘        └────────┬───────┘
                                       │                        │
                                  ┌────┴────┐              ┌────┴────┐
                                  │Success? │              │  OK?    │
                                  └────┬────┘              └────┬────┘
                                       │                        │
                          ┌────────────┼──────────┐            │
                          │ NO         │ YES      │            │
                          ▼            ▼          │            ▼
                  ┌──────────┐  ┌──────────┐     │    ┌──────────────┐
                  │Exit: Fail│  │Continue  │     │    │Check Safety  │
                  └──────────┘  └────┬─────┘     │    │   Systems    │
                                     │            │    └──────┬───────┘
                                     └────────────┘           │
                                                         ┌────┴────┐
                                                         │  OK?    │
                                                         └────┬────┘
                                                              │
                                                 ┌────────────┼────────────┐
                                                 │ NO                      │ YES
                                                 ▼                         ▼
                                         ┌──────────────┐         ┌──────────────┐
                                         │ Exit: Safety │         │ Proceed to   │
                                         │   Failed     │         │   Trading    │
                                         └──────────────┘         └──────────────┘
```

---

## Signal Generation & Execution Workflow

```
┌─────────────────────────────────────────────────────────────┐
│                    Execution Engine Start                    │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
                ┌─────────────────┐
                │ Check Kill      │
                │ Switches        │
                └────────┬────────┘
                         │
                    ┌────┴────┐
                    │Active?  │
                    └────┬────┘
                         │
            ┌────────────┼────────────┐
            │ YES                     │ NO
            ▼                         ▼
    ┌───────────────┐        ┌────────────────────┐
    │ HALT Trading  │        │ Check Drawdown     │
    │ Send Alert    │        │ Stop Status        │
    └───────────────┘        └────────┬───────────┘
                                      │
                                      ▼
                             ┌─────────────────────┐
                             │ State: NORMAL?      │
                             │ RAMPUP? HALT?       │
                             └────────┬────────────┘
                                      │
                         ┌────────────┼────────────┐
                         │ HALT                    │ NORMAL/RAMPUP
                         ▼                         ▼
                 ┌───────────────┐        ┌────────────────┐
                 │ Skip Trading  │        │ Check Data     │
                 └───────────────┘        │ Quality        │
                                          └────────┬───────┘
                                                   │
                                                   ▼
                                          ┌─────────────────┐
                                          │ For Each        │
                                          │ Strategy        │
                                          └────────┬────────┘
                                                   │
                                                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│                         Strategy Loop                                 │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │ 1. Generate Raw Signals                                        │ │
│  │    └─> Record in funnel: "raw_signals"                        │ │
│  │                                                                 │ │
│  │ 2. Regime Filter                                               │ │
│  │    └─> Record in funnel: "after_regime"                       │ │
│  │                                                                 │ │
│  │ 3. Correlation Filter (reject if corr > 0.7)                  │ │
│  │    └─> Record in funnel: "after_correlation"                  │ │
│  │                                                                 │ │
│  │ 4. Risk Filter (portfolio heat, daily loss limit)             │ │
│  │    └─> Record in funnel: "after_risk"                         │ │
│  │                                                                 │ │
│  │ 5. Apply Sizing Multipliers                                   │ │
│  │    ├─> Correlation multiplier                                 │ │
│  │    └─> Drawdown multiplier (1.0, 0.5, or 0.0)                │ │
│  │                                                                 │ │
│  │ 6. Execute Top 3 Signals                                       │ │
│  │    ├─> Calculate execution costs                              │ │
│  │    ├─> Submit order (or DRY_RUN simulate)                     │ │
│  │    ├─> Calculate P&L (FIFO lot tracking)                      │ │
│  │    ├─> Log trade to database with P&L                         │ │
│  │    └─> Record in funnel: "executed"                           │ │
│  └────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────┬───────────────────────────────────────┘
                               │
                               ▼
                      ┌─────────────────┐
                      │ Generate        │
                      │ Artifacts       │
                      └────────┬────────┘
                               │
                               ▼
                      ┌─────────────────┐
                      │ Update Health   │
                      │ Scores          │
                      └─────────────────┘
```

---

## P&L Attribution Workflow

```
┌─────────────────────────────────────────────────────────────┐
│                    Trade Execution                           │
└────────────────────────┬────────────────────────────────────┘
                         │
                    ┌────┴────┐
                    │ Action? │
                    └────┬────┘
                         │
            ┌────────────┼────────────┐
            │ BUY                     │ SELL
            ▼                         ▼
┌─────────────────────────┐  ┌─────────────────────────┐
│    BUY Workflow         │  │    SELL Workflow        │
│                         │  │                         │
│ 1. Add to Open Lots     │  │ 1. Match Against Lots   │
│    ┌──────────────┐     │  │    (FIFO)               │
│    │ Strategy: 1  │     │  │    ┌──────────────┐     │
│    │ Symbol: AAPL │     │  │    │ Lot 1: 10@185│     │
│    │ Lot: 10@185  │     │  │    │ Lot 2: 5@190 │     │
│    └──────────────┘     │  │    └──────────────┘     │
│                         │  │                         │
│ 2. Calculate P&L        │  │ 2. Calculate P&L        │
│    P&L = $0             │  │    Sell 12 @ $192:      │
│    (opening position)   │  │    - 10 from Lot 1:     │
│                         │  │      10×(192-185)=$70   │
│ 3. Log to Database      │  │    - 2 from Lot 2:      │
│    ├─> trades table     │  │      2×(192-190)=$4     │
│    │    pnl = 0.0       │  │    Total: $74 - costs   │
│    └─> positions table  │  │                         │
│                         │  │ 3. Update Lots          │
│                         │  │    - Remove Lot 1       │
│                         │  │    - Lot 2: 3@190 left  │
│                         │  │                         │
│                         │  │ 4. Log to Database      │
│                         │  │    ├─> trades table     │
│                         │  │    │    pnl = 74.0      │
│                         │  │    └─> positions table  │
└─────────────────────────┘  └─────────────────────────┘
                         │
                         ▼
                ┌─────────────────┐
                │ P&L Attributed  │
                │ to Strategy     │
                └─────────────────┘
```

---

## Safety Systems Workflow

```
┌─────────────────────────────────────────────────────────────┐
│                    Safety Systems Check                      │
└────────────────────────┬────────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┬────────────────┐
        │                │                │                │
        ▼                ▼                ▼                ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ Kill Switch  │ │  Drawdown    │ │ Data Quality │ │ Stop Losses  │
│   Service    │ │ Stop Manager │ │   Checker    │ │   Manager    │
└──────┬───────┘ └──────┬───────┘ └──────┬───────┘ └──────┬───────┘
       │                │                │                │
       ▼                ▼                ▼                ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ Check for    │ │ Calculate    │ │ Check each   │ │ Check each   │
│ active kill  │ │ current      │ │ symbol for:  │ │ position vs  │
│ switches in  │ │ drawdown vs  │ │ - Staleness  │ │ 3×ATR stop   │
│ database     │ │ peak value   │ │ - Gaps       │ │ price        │
└──────┬───────┘ └──────┬───────┘ │ - Outliers   │ └──────┬───────┘
       │                │         └──────┬───────┘        │
       │                │                │                │
       ▼                ▼                ▼                ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ Active?      │ │ State:       │ │ Block bad    │ │ Trigger sell │
│ └─YES: HALT  │ │ - NORMAL     │ │ symbols      │ │ if breached  │
│ └─NO: OK     │ │ - RAMPUP(50%)│ │ └─Blocked:   │ │ └─Catastrophe│
└──────────────┘ │ - HALT(0%)   │ │    Skip      │ │    protection│
                 │ - PANIC(0%)  │ └──────────────┘ └──────────────┘
                 └──────────────┘
                         │
                         ▼
                ┌─────────────────┐
                │ Apply sizing    │
                │ multiplier to   │
                │ all trades      │
                └─────────────────┘

Drawdown States:
┌─────────────────────────────────────────────────────────────┐
│ NORMAL (0-8% drawdown)                                      │
│ └─> Sizing multiplier: 1.0 (100%)                          │
│                                                             │
│ HALT (8-10% drawdown)                                       │
│ └─> Sizing multiplier: 0.0 (0% - no trading)               │
│ └─> Cooldown: 5 days                                        │
│ └─> After cooldown: RAMPUP                                  │
│                                                             │
│ RAMPUP (recovering from HALT)                               │
│ └─> Sizing multiplier: 0.5 (50%)                           │
│ └─> Duration: 5 days                                        │
│ └─> After rampup: NORMAL                                    │
│                                                             │
│ PANIC (>10% drawdown)                                       │
│ └─> Sizing multiplier: 0.0 (0% - no trading)               │
│ └─> Email alert sent                                        │
│ └─> Manual intervention required                            │
└─────────────────────────────────────────────────────────────┘
```

---

## Email Notification Workflow

```
┌─────────────────────────────────────────────────────────────┐
│                    Trading Complete                          │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
                ┌─────────────────┐
                │ Load Artifact   │
                │ (JSON)          │
                └────────┬────────┘
                         │
                         ▼
        ┌────────────────┴────────────────┐
        │                                 │
        ▼                                 ▼
┌──────────────────┐            ┌──────────────────┐
│ Query Database   │            │ Load Artifacts   │
│ - Strategy P&L   │            │ - Drawdown state │
│ - Trade details  │            │ - Data quality   │
│ - Positions      │            │ - Signal funnel  │
│ - Performance    │            │ - Health scores  │
└────────┬─────────┘            └────────┬─────────┘
         │                               │
         └───────────────┬───────────────┘
                         │
                         ▼
                ┌─────────────────┐
                │ Generate HTML   │
                │ Email Body      │
                └────────┬────────┘
                         │
                         ▼
        ┌────────────────────────────────┐
        │     Email Sections:            │
        │ 1. Safety Systems Status       │
        │ 2. Daily Insights              │
        │ 3. Portfolio Metrics           │
        │ 4. Trades Executed             │
        │ 5. Strategy Performance        │
        │ 6. Strategy Health Scores      │
        │ 7. Current Positions           │
        └────────────────┬───────────────┘
                         │
                         ▼
                ┌─────────────────┐
                │ Send via SMTP   │
                │ (Gmail)         │
                └────────┬────────┘
                         │
                         ▼
                ┌─────────────────┐
                │ Email Delivered │
                │ to Inbox        │
                └─────────────────┘
```

---

## Data Flow Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Data Sources                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ Alpha Vantage│  │    Alpaca    │  │   Database   │     │
│  │ (Market Data)│  │  (Broker API)│  │  (SQLite)    │     │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘     │
└─────────┼──────────────────┼──────────────────┼─────────────┘
          │                  │                  │
          ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────────┐
│                    Processing Layer                          │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Data Validator → Regime Detector → Strategy Engines │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                     Risk Management                          │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Correlation Filter → Portfolio Risk → Cash Manager  │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    Safety Systems                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Kill Switch → Drawdown Stop → Data Quality → Stops  │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    Execution Layer                           │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Cost Model → Order Submission → P&L Calculator      │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    Persistence Layer                         │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Database (trades, positions, signals, state)        │  │
│  │ Artifacts (JSON reports, funnel, health)            │  │
│  │ Logs (execution logs, errors)                       │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    Notification Layer                        │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Email Generator → SMTP → User Inbox                 │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## Module Dependencies

```
execution_engine.py (Main Orchestrator)
    ├─> kill_switch_service.py
    ├─> drawdown_stop_manager.py
    ├─> data_quality_checker.py
    ├─> data_validator.py
    ├─> regime_detector.py
    ├─> correlation_filter.py
    ├─> portfolio_risk_manager.py
    ├─> cash_manager.py
    ├─> dynamic_allocator.py
    ├─> execution_cost_model.py
    ├─> pnl_calculator.py ← NEW
    ├─> stop_loss_manager.py
    ├─> signal_funnel_tracker.py
    ├─> strategy_health_scorer.py
    ├─> broker_reconciler.py
    ├─> email_notifier.py
    ├─> database.py
    └─> Strategies:
        ├─> rsi_mean_reversion.py
        ├─> ml_momentum_strategy.py
        ├─> ma_crossover_strategy.py
        └─> news_sentiment_strategy.py
```

---

## Summary

The trading system follows a **layered architecture** with clear separation of concerns:

1. **Pre-Flight Layer** - Validates conditions before trading
2. **Data Layer** - Fetches and validates market data
3. **Strategy Layer** - Generates trading signals
4. **Risk Layer** - Filters and sizes positions
5. **Safety Layer** - Enforces safety constraints
6. **Execution Layer** - Submits orders and tracks P&L
7. **Persistence Layer** - Stores all data
8. **Notification Layer** - Reports results

Each layer has specific responsibilities and can be tested independently.
