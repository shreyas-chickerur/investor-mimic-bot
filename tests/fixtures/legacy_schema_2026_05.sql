CREATE TABLE strategies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                description TEXT,
                capital_allocation REAL NOT NULL,
                initial_capital REAL NOT NULL,
                status TEXT DEFAULT 'active',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
CREATE TABLE signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                strategy_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                signal_type TEXT NOT NULL,
                confidence REAL,
                reasoning TEXT,
                asof_date TEXT NOT NULL,
                generated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                terminal_state TEXT,
                terminal_reason TEXT,
                terminal_at TEXT,
                FOREIGN KEY (strategy_id) REFERENCES strategies(id)
            );
CREATE INDEX idx_signals_run_id ON signals(run_id);
CREATE INDEX idx_signals_symbol ON signals(symbol);
CREATE INDEX idx_signals_terminal_state ON signals(terminal_state);
CREATE INDEX idx_signals_generated_at ON signals(generated_at);
CREATE INDEX idx_signals_strategy_date ON signals(strategy_id, generated_at);
CREATE TABLE trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                strategy_id INTEGER NOT NULL,
                signal_id INTEGER,
                symbol TEXT NOT NULL,
                action TEXT NOT NULL,
                shares REAL NOT NULL,
                requested_price REAL NOT NULL,
                exec_price REAL NOT NULL,
                slippage_cost REAL DEFAULT 0,
                commission_cost REAL DEFAULT 0,
                total_cost REAL DEFAULT 0,
                notional REAL NOT NULL,
                order_id TEXT,
                executed_at TEXT NOT NULL,
                pnl REAL,
                FOREIGN KEY (strategy_id) REFERENCES strategies(id),
                FOREIGN KEY (signal_id) REFERENCES signals(id)
            );
CREATE INDEX idx_trades_run_id ON trades(run_id);
CREATE INDEX idx_trades_strategy_date ON trades(strategy_id, executed_at);
CREATE TABLE positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                shares REAL NOT NULL,
                avg_price REAL NOT NULL,
                current_price REAL,
                market_value REAL,
                unrealized_pnl REAL,
                entry_price REAL,
                entry_date TEXT,
                atr REAL,
                stop_loss_price REAL,
                last_updated TEXT NOT NULL,
                FOREIGN KEY (strategy_id) REFERENCES strategies(id),
                UNIQUE(strategy_id, symbol)
            );
CREATE TABLE broker_state (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                snapshot_date TEXT NOT NULL,
                snapshot_type TEXT NOT NULL,
                cash REAL NOT NULL,
                portfolio_value REAL NOT NULL,
                buying_power REAL NOT NULL,
                positions_json TEXT,
                reconciliation_status TEXT,
                discrepancies_json TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
CREATE INDEX idx_broker_state_run_id ON broker_state(run_id);
CREATE TABLE system_state (
                key TEXT PRIMARY KEY,
                value TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            );
CREATE TABLE signal_funnel (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                strategy_id INTEGER NOT NULL,
                strategy_name TEXT NOT NULL,
                raw_signals_count INTEGER DEFAULT 0,
                after_regime_count INTEGER DEFAULT 0,
                after_correlation_count INTEGER DEFAULT 0,
                after_risk_count INTEGER DEFAULT 0,
                executed_count INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (strategy_id) REFERENCES strategies(id)
            );
CREATE TABLE signal_rejections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                signal_id INTEGER,
                strategy_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                stage TEXT NOT NULL,
                reason_code TEXT NOT NULL,
                details_json TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (signal_id) REFERENCES signals(id),
                FOREIGN KEY (strategy_id) REFERENCES strategies(id)
            );
CREATE TABLE order_intents (
                intent_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                strategy_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                target_qty REAL NOT NULL,
                status TEXT NOT NULL,
                broker_order_id TEXT,
                error_code TEXT,
                error_message TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                submitted_at TEXT,
                acked_at TEXT,
                filled_at TEXT,
                FOREIGN KEY (strategy_id) REFERENCES strategies(id)
            );
CREATE INDEX idx_signal_funnel_run_id ON signal_funnel(run_id);
CREATE INDEX idx_signal_rejections_run_id ON signal_rejections(run_id);
CREATE INDEX idx_signal_rejections_stage ON signal_rejections(stage);
CREATE INDEX idx_rejections_strategy_date ON signal_rejections(strategy_id, created_at);
CREATE INDEX idx_order_intents_run_id ON order_intents(run_id);
CREATE INDEX idx_order_intents_status ON order_intents(status);
CREATE TABLE strategy_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                strategy_id INTEGER NOT NULL,
                snapshot_date TEXT NOT NULL,
                portfolio_value REAL NOT NULL,
                cash REAL NOT NULL,
                positions_value REAL NOT NULL,
                total_return_pct REAL NOT NULL,
                num_positions INTEGER DEFAULT 0,
                num_trades INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (strategy_id) REFERENCES strategies(id)
            );
CREATE INDEX idx_strategy_perf_strat ON strategy_performance(strategy_id);
CREATE INDEX idx_strategy_perf_date ON strategy_performance(snapshot_date);
CREATE TABLE daily_portfolio_snapshot (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                snapshot_date TEXT NOT NULL,
                portfolio_value REAL NOT NULL,
                cash REAL NOT NULL,
                positions_value REAL NOT NULL,
                heat_pct REAL,
                daily_pnl REAL,
                daily_pnl_pct REAL,
                cumulative_pnl REAL,
                drawdown_pct REAL,
                peak_value REAL,
                num_open_positions INTEGER DEFAULT 0,
                vix REAL,
                regime TEXT,
                allocation_json TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(snapshot_date)
            );
CREATE INDEX idx_daily_snap_date ON daily_portfolio_snapshot(snapshot_date);
CREATE TABLE trade_pnl_detail (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_id INTEGER NOT NULL,
                strategy_name TEXT,
                symbol TEXT NOT NULL,
                buy_run_id TEXT,
                sell_run_id TEXT NOT NULL,
                entry_date TEXT,
                exit_date TEXT NOT NULL,
                entry_price REAL NOT NULL,
                exit_price REAL NOT NULL,
                shares REAL NOT NULL,
                gross_pnl REAL NOT NULL,
                gross_pnl_pct REAL NOT NULL,
                hold_days INTEGER,
                exit_reason TEXT,
                is_winner INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (strategy_id) REFERENCES strategies(id)
            );
CREATE INDEX idx_trade_pnl_strategy ON trade_pnl_detail(strategy_id);
CREATE INDEX idx_trade_pnl_exit ON trade_pnl_detail(exit_date);
CREATE TABLE run_state (
                run_id TEXT PRIMARY KEY,
                stage TEXT NOT NULL,
                status TEXT NOT NULL,
                error_message TEXT,
                metadata_json TEXT,
                started_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                completed_at TEXT
            );
CREATE INDEX idx_run_state_status ON run_state(status);
CREATE INDEX idx_run_state_updated_at ON run_state(updated_at);
CREATE TABLE notification_outbox (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT,
                channel TEXT NOT NULL,
                category TEXT NOT NULL,
                subject TEXT NOT NULL,
                body TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDING',
                attempts INTEGER NOT NULL DEFAULT 0,
                last_error TEXT,
                created_at TEXT NOT NULL,
                sent_at TEXT
            );
CREATE INDEX idx_notification_outbox_status ON notification_outbox(status);
CREATE INDEX idx_notification_outbox_run_id ON notification_outbox(run_id);
CREATE TABLE run_slo_metrics (
                run_id TEXT PRIMARY KEY,
                metrics_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
CREATE TABLE pending_signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                signal_data_json TEXT NOT NULL,
                blocked_reason TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                retry_count INTEGER DEFAULT 0,
                last_retry_at TEXT,
                status TEXT DEFAULT 'PENDING',
                FOREIGN KEY (strategy_id) REFERENCES strategies(id)
            );
CREATE INDEX idx_pending_signals_status ON pending_signals(status);
CREATE INDEX idx_pending_signals_expires ON pending_signals(expires_at);
CREATE TABLE fill_quality (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                strategy_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                action TEXT NOT NULL,
                expected_price REAL NOT NULL,
                fill_price REAL NOT NULL,
                shares REAL NOT NULL,
                deviation_bps INTEGER NOT NULL,
                recorded_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (strategy_id) REFERENCES strategies(id)
            );
CREATE INDEX idx_fill_quality_run ON fill_quality(run_id);
CREATE TABLE stop_loss_state (
                    symbol TEXT PRIMARY KEY,
                    stop_price REAL NOT NULL,
                    entry_price REAL NOT NULL,
                    entry_atr REAL NOT NULL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
