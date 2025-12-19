-- Create the database if it doesn't exist
CREATE DATABASE investorbot;

-- Connect to the new database
\c investorbot

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Investors table
CREATE TABLE investors (
    investor_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    cik VARCHAR(10) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Securities table
CREATE TABLE securities (
    security_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticker VARCHAR(20),
    cusip VARCHAR(9),
    isin VARCHAR(12),
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT unique_security_identifier 
        CHECK (ticker IS NOT NULL OR cusip IS NOT NULL OR isin IS NOT NULL)
);

-- Filings table
CREATE TABLE filings (
    filing_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    investor_id UUID NOT NULL REFERENCES investors(investor_id),
    filing_date DATE NOT NULL,
    accession_number VARCHAR(20) NOT NULL,
    filing_url TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (investor_id, filing_date)
);

-- Holdings table
CREATE TABLE holdings (
    holding_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    filing_id UUID NOT NULL REFERENCES filings(filing_id) ON DELETE CASCADE,
    security_id UUID NOT NULL REFERENCES securities(security_id),
    shares BIGINT NOT NULL,
    value_usd NUMERIC(20, 2) NOT NULL,
    weight_in_portfolio NUMERIC(10, 6) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (filing_id, security_id)
);

-- Create indexes for performance
CREATE INDEX idx_securities_ticker ON securities(ticker) WHERE ticker IS NOT NULL;
CREATE INDEX idx_securities_cusip ON securities(cusip) WHERE cusip IS NOT NULL;
CREATE INDEX idx_securities_isin ON securities(isin) WHERE isin IS NOT NULL;
CREATE INDEX idx_filings_filing_date ON filings(filing_date);
CREATE INDEX idx_holdings_filing_id ON holdings(filing_id);
CREATE INDEX idx_holdings_security_id ON holdings(security_id);

-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_modified_column() 
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW; 
END;
$$ LANGUAGE plpgsql;

-- Create triggers to update timestamps
CREATE TRIGGER update_investors_modtime
BEFORE UPDATE ON investors
FOR EACH ROW EXECUTE FUNCTION update_modified_column();

CREATE TRIGGER update_securities_modtime
BEFORE UPDATE ON securities
FOR EACH ROW EXECUTE FUNCTION update_modified_column();

CREATE TRIGGER update_filings_modtime
BEFORE UPDATE ON filings
FOR EACH ROW EXECUTE FUNCTION update_modified_column();

CREATE TRIGGER update_holdings_modtime
BEFORE UPDATE ON holdings
FOR EACH ROW EXECUTE FUNCTION update_modified_column();
