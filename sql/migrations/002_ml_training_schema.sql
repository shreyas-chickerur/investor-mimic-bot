-- ML Training Data Schema Enhancement
-- Adds comprehensive tables for model training and continuous learning

-- Historical 13F performance tracking
CREATE TABLE IF NOT EXISTS investor_performance (
    investor_id VARCHAR(50),
    quarter DATE,
    total_holdings_value DECIMAL,
    num_positions INTEGER,
    new_positions INTEGER,
    closed_positions INTEGER,
    avg_position_size DECIMAL,
    sector_concentration JSONB,
    quarterly_return DECIMAL,
    cumulative_return DECIMAL,
    sharpe_ratio DECIMAL,
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (investor_id, quarter)
);

CREATE INDEX idx_investor_perf_quarter ON investor_performance(quarter);
CREATE INDEX idx_investor_perf_return ON investor_performance(quarterly_return);

-- Comprehensive news sentiment
CREATE TABLE IF NOT EXISTS news_articles (
    article_id SERIAL PRIMARY KEY,
    ticker VARCHAR(10),
    source VARCHAR(50),
    title TEXT,
    content TEXT,
    sentiment_score DECIMAL,
    sentiment_label VARCHAR(20),
    published_at TIMESTAMP,
    relevance_score DECIMAL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_news_ticker ON news_articles(ticker);
CREATE INDEX idx_news_published ON news_articles(published_at);
CREATE INDEX idx_news_sentiment ON news_articles(sentiment_score);

-- Social media sentiment
CREATE TABLE IF NOT EXISTS social_sentiment (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10),
    platform VARCHAR(20),
    mention_count INTEGER,
    positive_mentions INTEGER,
    negative_mentions INTEGER,
    neutral_mentions INTEGER,
    sentiment_score DECIMAL,
    trending_score DECIMAL,
    date DATE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_social_ticker ON social_sentiment(ticker);
CREATE INDEX idx_social_date ON social_sentiment(date);
CREATE INDEX idx_social_platform ON social_sentiment(platform);

-- Fundamental data
CREATE TABLE IF NOT EXISTS fundamentals (
    ticker VARCHAR(10),
    quarter DATE,
    revenue DECIMAL,
    net_income DECIMAL,
    eps DECIMAL,
    revenue_growth DECIMAL,
    earnings_growth DECIMAL,
    profit_margin DECIMAL,
    roe DECIMAL,
    debt_to_equity DECIMAL,
    pe_ratio DECIMAL,
    pb_ratio DECIMAL,
    ps_ratio DECIMAL,
    peg_ratio DECIMAL,
    dividend_yield DECIMAL,
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (ticker, quarter)
);

CREATE INDEX idx_fundamentals_ticker ON fundamentals(ticker);
CREATE INDEX idx_fundamentals_quarter ON fundamentals(quarter);

-- Technical indicators (extended)
CREATE TABLE IF NOT EXISTS technical_indicators (
    ticker VARCHAR(10),
    date DATE,
    rsi_14 DECIMAL,
    macd DECIMAL,
    macd_signal DECIMAL,
    bollinger_upper DECIMAL,
    bollinger_lower DECIMAL,
    bollinger_width DECIMAL,
    atr_14 DECIMAL,
    adx_14 DECIMAL,
    stochastic_k DECIMAL,
    stochastic_d DECIMAL,
    obv BIGINT,
    vwap DECIMAL,
    volume_ratio DECIMAL,
    momentum_10 DECIMAL,
    momentum_20 DECIMAL,
    roc_10 DECIMAL,
    roc_20 DECIMAL,
    williams_r DECIMAL,
    cci DECIMAL,
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (ticker, date)
);

CREATE INDEX idx_tech_ticker ON technical_indicators(ticker);
CREATE INDEX idx_tech_date ON technical_indicators(date);

-- Model training data
CREATE TABLE IF NOT EXISTS training_data (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10),
    date DATE,
    features JSONB,
    target_return_1d DECIMAL,
    target_return_5d DECIMAL,
    target_return_10d DECIMAL,
    target_return_20d DECIMAL,
    actual_return_1d DECIMAL,
    actual_return_5d DECIMAL,
    actual_return_10d DECIMAL,
    actual_return_20d DECIMAL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_training_ticker ON training_data(ticker);
CREATE INDEX idx_training_date ON training_data(date);
CREATE INDEX idx_training_created ON training_data(created_at);

-- Model predictions tracking
CREATE TABLE IF NOT EXISTS model_predictions (
    id SERIAL PRIMARY KEY,
    model_version VARCHAR(50),
    ticker VARCHAR(10),
    prediction_date DATE,
    predicted_return DECIMAL,
    confidence_score DECIMAL,
    actual_return DECIMAL,
    prediction_error DECIMAL,
    features_used JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_pred_model ON model_predictions(model_version);
CREATE INDEX idx_pred_ticker ON model_predictions(ticker);
CREATE INDEX idx_pred_date ON model_predictions(prediction_date);
CREATE INDEX idx_pred_error ON model_predictions(prediction_error);

-- Model performance metrics
CREATE TABLE IF NOT EXISTS model_metrics (
    id SERIAL PRIMARY KEY,
    model_version VARCHAR(50) UNIQUE,
    training_date TIMESTAMP,
    validation_sharpe DECIMAL,
    validation_accuracy DECIMAL,
    validation_mse DECIMAL,
    validation_mae DECIMAL,
    test_sharpe DECIMAL,
    test_accuracy DECIMAL,
    test_mse DECIMAL,
    test_mae DECIMAL,
    feature_importance JSONB,
    hyperparameters JSONB,
    training_samples INTEGER,
    is_production BOOLEAN DEFAULT FALSE,
    deployed_at TIMESTAMP,
    retired_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_metrics_version ON model_metrics(model_version);
CREATE INDEX idx_metrics_production ON model_metrics(is_production);
CREATE INDEX idx_metrics_sharpe ON model_metrics(test_sharpe);

-- Data collection status tracking
CREATE TABLE IF NOT EXISTS data_collection_status (
    id SERIAL PRIMARY KEY,
    data_source VARCHAR(50),
    last_collection_time TIMESTAMP,
    records_collected INTEGER,
    status VARCHAR(20),
    error_message TEXT,
    next_collection_time TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_collection_source ON data_collection_status(data_source);
CREATE INDEX idx_collection_time ON data_collection_status(last_collection_time);

-- Model retraining schedule
CREATE TABLE IF NOT EXISTS model_retraining_schedule (
    id SERIAL PRIMARY KEY,
    scheduled_time TIMESTAMP,
    status VARCHAR(20),
    model_version VARCHAR(50),
    training_duration_seconds INTEGER,
    samples_used INTEGER,
    performance_improvement DECIMAL,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_retrain_time ON model_retraining_schedule(scheduled_time);
CREATE INDEX idx_retrain_status ON model_retraining_schedule(status);
