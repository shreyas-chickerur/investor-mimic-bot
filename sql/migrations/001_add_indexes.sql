-- Add performance indexes to database tables

-- Holdings table indexes
CREATE INDEX IF NOT EXISTS idx_holdings_investor_id ON holdings(investor_id);
CREATE INDEX IF NOT EXISTS idx_holdings_ticker ON holdings(ticker);
CREATE INDEX IF NOT EXISTS idx_holdings_filing_date ON holdings(filing_date);
CREATE INDEX IF NOT EXISTS idx_holdings_investor_ticker ON holdings(investor_id, ticker);

-- Investors table indexes
CREATE INDEX IF NOT EXISTS idx_investors_name ON investors(name);

-- Composite indexes for common queries
CREATE INDEX IF NOT EXISTS idx_holdings_recent ON holdings(filing_date DESC, investor_id);
CREATE INDEX IF NOT EXISTS idx_holdings_ticker_date ON holdings(ticker, filing_date DESC);

-- Add missing tables if they don't exist

-- Price history table
CREATE TABLE IF NOT EXISTS price_history (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    date DATE NOT NULL,
    open DECIMAL(10, 2),
    high DECIMAL(10, 2),
    low DECIMAL(10, 2),
    close DECIMAL(10, 2) NOT NULL,
    volume BIGINT,
    adjusted_close DECIMAL(10, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ticker, date)
);

CREATE INDEX IF NOT EXISTS idx_price_history_ticker ON price_history(ticker);
CREATE INDEX IF NOT EXISTS idx_price_history_date ON price_history(date);
CREATE INDEX IF NOT EXISTS idx_price_history_ticker_date ON price_history(ticker, date DESC);

-- Factor scores table
CREATE TABLE IF NOT EXISTS factor_scores (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    date DATE NOT NULL,
    conviction_score DECIMAL(5, 4),
    news_score DECIMAL(5, 4),
    insider_score DECIMAL(5, 4),
    technical_score DECIMAL(5, 4),
    moving_avg_score DECIMAL(5, 4),
    volume_score DECIMAL(5, 4),
    relative_strength_score DECIMAL(5, 4),
    earnings_score DECIMAL(5, 4),
    composite_score DECIMAL(5, 4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ticker, date)
);

CREATE INDEX IF NOT EXISTS idx_factor_scores_ticker ON factor_scores(ticker);
CREATE INDEX IF NOT EXISTS idx_factor_scores_date ON factor_scores(date);
CREATE INDEX IF NOT EXISTS idx_factor_scores_composite ON factor_scores(composite_score DESC);

-- Market regime table
CREATE TABLE IF NOT EXISTS market_regime (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL UNIQUE,
    regime VARCHAR(20) NOT NULL,
    spy_close DECIMAL(10, 2),
    vix_close DECIMAL(10, 2),
    ma_50 DECIMAL(10, 2),
    ma_200 DECIMAL(10, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_market_regime_date ON market_regime(date DESC);
CREATE INDEX IF NOT EXISTS idx_market_regime_regime ON market_regime(regime);

-- Trade history table
CREATE TABLE IF NOT EXISTS trade_history (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    action VARCHAR(10) NOT NULL,
    quantity DECIMAL(10, 4) NOT NULL,
    price DECIMAL(10, 2) NOT NULL,
    total_value DECIMAL(12, 2) NOT NULL,
    commission DECIMAL(8, 2) DEFAULT 0,
    trade_date TIMESTAMP NOT NULL,
    approval_id VARCHAR(50),
    status VARCHAR(20) DEFAULT 'pending',
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_trade_history_ticker ON trade_history(ticker);
CREATE INDEX IF NOT EXISTS idx_trade_history_date ON trade_history(trade_date DESC);
CREATE INDEX IF NOT EXISTS idx_trade_history_status ON trade_history(status);

-- Portfolio positions table
CREATE TABLE IF NOT EXISTS portfolio_positions (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL UNIQUE,
    quantity DECIMAL(10, 4) NOT NULL,
    avg_cost DECIMAL(10, 2) NOT NULL,
    current_price DECIMAL(10, 2),
    market_value DECIMAL(12, 2),
    unrealized_pnl DECIMAL(12, 2),
    stop_loss_price DECIMAL(10, 2),
    take_profit_price DECIMAL(10, 2),
    entry_date TIMESTAMP NOT NULL,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_portfolio_positions_ticker ON portfolio_positions(ticker);
CREATE INDEX IF NOT EXISTS idx_portfolio_positions_updated ON portfolio_positions(last_updated DESC);

-- Performance metrics table
CREATE TABLE IF NOT EXISTS performance_metrics (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL UNIQUE,
    portfolio_value DECIMAL(12, 2) NOT NULL,
    cash_balance DECIMAL(12, 2) NOT NULL,
    total_value DECIMAL(12, 2) NOT NULL,
    daily_return DECIMAL(8, 6),
    cumulative_return DECIMAL(8, 6),
    spy_return DECIMAL(8, 6),
    alpha DECIMAL(8, 6),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_performance_metrics_date ON performance_metrics(date DESC);

-- News sentiment table
CREATE TABLE IF NOT EXISTS news_sentiment (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    date DATE NOT NULL,
    headline TEXT,
    source VARCHAR(100),
    sentiment_score DECIMAL(5, 4),
    relevance_score DECIMAL(5, 4),
    url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_news_sentiment_ticker ON news_sentiment(ticker);
CREATE INDEX IF NOT EXISTS idx_news_sentiment_date ON news_sentiment(date DESC);
CREATE INDEX IF NOT EXISTS idx_news_sentiment_ticker_date ON news_sentiment(ticker, date DESC);

-- Insider trades table
CREATE TABLE IF NOT EXISTS insider_trades (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    insider_name VARCHAR(200),
    insider_title VARCHAR(200),
    transaction_type VARCHAR(50),
    shares BIGINT,
    price DECIMAL(10, 2),
    value DECIMAL(12, 2),
    filing_date DATE NOT NULL,
    transaction_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_insider_trades_ticker ON insider_trades(ticker);
CREATE INDEX IF NOT EXISTS idx_insider_trades_date ON insider_trades(filing_date DESC);
CREATE INDEX IF NOT EXISTS idx_insider_trades_ticker_date ON insider_trades(ticker, filing_date DESC);

-- System logs table
CREATE TABLE IF NOT EXISTS system_logs (
    id SERIAL PRIMARY KEY,
    level VARCHAR(20) NOT NULL,
    message TEXT NOT NULL,
    module VARCHAR(100),
    function VARCHAR(100),
    error_details TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_system_logs_level ON system_logs(level);
CREATE INDEX IF NOT EXISTS idx_system_logs_created ON system_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_system_logs_module ON system_logs(module);
