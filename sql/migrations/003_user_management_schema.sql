-- User Management and Dashboard Schema
-- Adds user authentication, settings, activity tracking, and performance analytics

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    last_login TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    is_verified BOOLEAN DEFAULT FALSE,
    verification_token VARCHAR(255),
    reset_token VARCHAR(255),
    reset_token_expires TIMESTAMP,
    role VARCHAR(50) DEFAULT 'user'
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_active ON users(is_active);

-- User settings
CREATE TABLE IF NOT EXISTS user_settings (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    alpaca_api_key_encrypted TEXT,
    alpaca_secret_key_encrypted TEXT,
    alpaca_paper_trading BOOLEAN DEFAULT TRUE,
    risk_tolerance VARCHAR(50) DEFAULT 'moderate',
    email_notifications BOOLEAN DEFAULT TRUE,
    trade_notifications BOOLEAN DEFAULT TRUE,
    daily_digest BOOLEAN DEFAULT TRUE,
    max_position_size DECIMAL DEFAULT 0.10,
    max_portfolio_allocation DECIMAL DEFAULT 0.20,
    auto_execute_trades BOOLEAN DEFAULT FALSE,
    stop_loss_enabled BOOLEAN DEFAULT TRUE,
    take_profit_enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- User sessions
CREATE TABLE IF NOT EXISTS user_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(255) UNIQUE NOT NULL,
    refresh_token_hash VARCHAR(255),
    expires_at TIMESTAMP NOT NULL,
    ip_address VARCHAR(50),
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    last_activity TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_sessions_user ON user_sessions(user_id);
CREATE INDEX idx_sessions_token ON user_sessions(token_hash);
CREATE INDEX idx_sessions_expires ON user_sessions(expires_at);

-- User activity tracking
CREATE TABLE IF NOT EXISTS user_activity (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    activity_type VARCHAR(100) NOT NULL,
    activity_data JSONB,
    page_url VARCHAR(500),
    ip_address VARCHAR(50),
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_activity_user ON user_activity(user_id);
CREATE INDEX idx_activity_type ON user_activity(activity_type);
CREATE INDEX idx_activity_created ON user_activity(created_at);

-- Trade performance tracking
CREATE TABLE IF NOT EXISTS trade_performance (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    ticker VARCHAR(10) NOT NULL,
    action VARCHAR(10) NOT NULL,
    entry_date DATE NOT NULL,
    entry_price DECIMAL NOT NULL,
    exit_date DATE,
    exit_price DECIMAL,
    quantity DECIMAL NOT NULL,
    profit_loss DECIMAL,
    profit_loss_pct DECIMAL,
    strategy_used VARCHAR(100),
    signal_score DECIMAL,
    recommendation_id VARCHAR(100),
    is_closed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_trade_perf_user ON trade_performance(user_id);
CREATE INDEX idx_trade_perf_ticker ON trade_performance(ticker);
CREATE INDEX idx_trade_perf_closed ON trade_performance(is_closed);
CREATE INDEX idx_trade_perf_entry_date ON trade_performance(entry_date);

-- User portfolio snapshots (daily)
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    snapshot_date DATE NOT NULL,
    total_value DECIMAL NOT NULL,
    cash_balance DECIMAL NOT NULL,
    positions_value DECIMAL NOT NULL,
    day_pnl DECIMAL,
    day_pnl_pct DECIMAL,
    total_pnl DECIMAL,
    total_pnl_pct DECIMAL,
    num_positions INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, snapshot_date)
);

CREATE INDEX idx_snapshots_user ON portfolio_snapshots(user_id);
CREATE INDEX idx_snapshots_date ON portfolio_snapshots(snapshot_date);

-- Strategy performance by user
CREATE TABLE IF NOT EXISTS strategy_performance (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    strategy_name VARCHAR(100) NOT NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    total_trades INTEGER DEFAULT 0,
    winning_trades INTEGER DEFAULT 0,
    losing_trades INTEGER DEFAULT 0,
    win_rate DECIMAL,
    avg_profit DECIMAL,
    avg_loss DECIMAL,
    total_pnl DECIMAL,
    sharpe_ratio DECIMAL,
    max_drawdown DECIMAL,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, strategy_name, period_start, period_end)
);

CREATE INDEX idx_strategy_perf_user ON strategy_performance(user_id);
CREATE INDEX idx_strategy_perf_name ON strategy_performance(strategy_name);

-- User notifications
CREATE TABLE IF NOT EXISTS user_notifications (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    notification_type VARCHAR(100) NOT NULL,
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    data JSONB,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_notifications_user ON user_notifications(user_id);
CREATE INDEX idx_notifications_read ON user_notifications(is_read);
CREATE INDEX idx_notifications_created ON user_notifications(created_at);

-- API usage tracking
CREATE TABLE IF NOT EXISTS api_usage (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    endpoint VARCHAR(255) NOT NULL,
    method VARCHAR(10) NOT NULL,
    status_code INTEGER,
    response_time_ms INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_api_usage_user ON api_usage(user_id);
CREATE INDEX idx_api_usage_endpoint ON api_usage(endpoint);
CREATE INDEX idx_api_usage_created ON api_usage(created_at);

-- User preferences
CREATE TABLE IF NOT EXISTS user_preferences (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    theme VARCHAR(20) DEFAULT 'light',
    language VARCHAR(10) DEFAULT 'en',
    timezone VARCHAR(50) DEFAULT 'America/New_York',
    currency VARCHAR(10) DEFAULT 'USD',
    chart_type VARCHAR(20) DEFAULT 'line',
    default_view VARCHAR(50) DEFAULT 'dashboard',
    notifications_sound BOOLEAN DEFAULT TRUE,
    compact_mode BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Watchlists
CREATE TABLE IF NOT EXISTS user_watchlists (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_watchlists_user ON user_watchlists(user_id);

-- Watchlist items
CREATE TABLE IF NOT EXISTS watchlist_items (
    id SERIAL PRIMARY KEY,
    watchlist_id INTEGER REFERENCES user_watchlists(id) ON DELETE CASCADE,
    ticker VARCHAR(10) NOT NULL,
    added_at TIMESTAMP DEFAULT NOW(),
    notes TEXT,
    UNIQUE(watchlist_id, ticker)
);

CREATE INDEX idx_watchlist_items_list ON watchlist_items(watchlist_id);
CREATE INDEX idx_watchlist_items_ticker ON watchlist_items(ticker);

-- User feedback
CREATE TABLE IF NOT EXISTS user_feedback (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    feedback_type VARCHAR(50) NOT NULL,
    rating INTEGER CHECK (rating >= 1 AND rating <= 5),
    message TEXT,
    page_url VARCHAR(500),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_feedback_user ON user_feedback(user_id);
CREATE INDEX idx_feedback_type ON user_feedback(feedback_type);

-- System announcements
CREATE TABLE IF NOT EXISTS system_announcements (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    announcement_type VARCHAR(50) NOT NULL,
    priority VARCHAR(20) DEFAULT 'normal',
    is_active BOOLEAN DEFAULT TRUE,
    start_date TIMESTAMP,
    end_date TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_announcements_active ON system_announcements(is_active);
CREATE INDEX idx_announcements_dates ON system_announcements(start_date, end_date);
