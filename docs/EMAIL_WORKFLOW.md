# Email Workflow - Real-Time Data Population

## ✅ YES - Automatic Real-Time Population is Built

The system **automatically** fetches real-time data from Alpaca API and populates the email dynamically.

---

## 🔄 How It Works

### **When Manual Approval is Triggered:**

```python
# 1. Trading signals are generated
signals = system.generate_signals(stock_data)

# 2. System checks if AUTO_TRADE is enabled
if config.is_manual_approval_required():
    
    # 3. Automatically fetch ALL data from Alpaca API
    email_data = populate_approval_email_data(
        proposed_trades=signals,
        use_alpaca=True  # Default: fetch from Alpaca
    )
    
    # 4. Email data now contains:
    # - Current positions from Alpaca (real-time)
    # - Portfolio value from Alpaca (real-time)
    # - Cash balance from Alpaca (real-time)
    # - Market indices (real-time via ETF proxies)
    # - News about holdings (from database)
    # - Causal chains (from database or generated)
    
    # 5. Generate and send email
    email_html = generate_professional_approval_email(**email_data)
    send_approval_email(email_html)
```

---

## 📊 What Gets Populated Automatically

### **From Alpaca API (Real-Time):**

| Data | Source | Update Frequency |
|------|--------|------------------|
| **Current Positions** | `trading_client.get_all_positions()` | Real-time |
| **Portfolio Value** | `account.portfolio_value` | Real-time |
| **Cash Balance** | `account.cash` | Real-time |
| **Current Prices** | `data_client.get_stock_latest_quote()` | Real-time |
| **Unrealized P/L** | `position.unrealized_pl` | Real-time |
| **Market Indices** | ETF proxies (SPY, QQQ, DIA) | Real-time |

### **From Database:**

| Data | Source | Update Frequency |
|------|--------|------------------|
| **Holdings News** | `stock_news` table | As populated |
| **Causal Chains** | `causal_chains` table | Generated once per trade |
| **Historical Market Data** | `market_data` table | Daily |

---

## 🎯 Complete Workflow

### **Step 1: Signal Generation (10 AM ET)**
```
Daily workflow runs → Generates buy signals → Checks AUTO_TRADE config
```

### **Step 2: Data Fetching (Automatic)**
```python
fetcher = AlpacaDataFetcher()

# Fetch current positions
positions = fetcher.get_current_positions()
# Returns: [
#   {'symbol': 'TSLA', 'shares': 12, 'avg_price': 245.00, 
#    'current_price': 252.30, 'unrealized_plpc': 2.98},
#   ...
# ]

# Fetch account info
account = fetcher.get_account_info()
# Returns: {
#   'portfolio_value': 50000.00,
#   'cash': 40556.75,
#   'equity': 50000.00,
#   'buying_power': 81113.50
# }

# Fetch market data
market = fetcher.get_market_indices()
# Returns: {
#   'S&P 500': {'value': '4,783.45', 'change': 23.45, 'change_pct': 0.49},
#   ...
# }
```

### **Step 3: Email Generation (Automatic)**
```python
email_html = generate_professional_approval_email(
    trades=proposed_trades,
    portfolio_value=account['portfolio_value'],  # From Alpaca
    cash=account['cash'],                        # From Alpaca
    market_data=market,                          # From Alpaca
    current_holdings=positions,                  # From Alpaca
    holdings_news=news,                          # From Database
    approval_url=config.APPROVAL_BASE_URL,
    request_id=request_id
)
```

### **Step 4: Email Sent (Automatic)**
```
Email sent to EMAIL_TO → You receive notification → Click "Review Trades"
```

---

## 🔧 Configuration

### **Enable Manual Approval Mode:**

```bash
# .env file
AUTO_TRADE=false  # Set to false for manual approval

# Email configuration (required for manual mode)
EMAIL_USERNAME=your.email@gmail.com
EMAIL_PASSWORD=your_16_char_app_password
EMAIL_TO=your.email@gmail.com
APPROVAL_BASE_URL=http://localhost:8000
```

### **Alpaca Credentials (Required):**

```bash
ALPACA_API_KEY=your_api_key
ALPACA_SECRET_KEY=your_secret_key
ALPACA_BASE_URL=https://paper-api.alpaca.markets
```

---

## 📧 Email Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    Trading Signal Generated                  │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              Check: AUTO_TRADE = false?                      │
└────────────────────┬────────────────────────────────────────┘
                     │ YES
                     ▼
┌─────────────────────────────────────────────────────────────┐
│           Fetch Real-Time Data from Alpaca API               │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ • Current Positions (TSLA, AMD, META, etc.)           │  │
│  │ • Portfolio Value ($50,000)                           │  │
│  │ • Cash Balance ($40,556.75)                           │  │
│  │ • Current Prices (real-time quotes)                   │  │
│  │ • Unrealized P/L for each position                    │  │
│  │ • Market Indices (S&P, NASDAQ, DOW)                   │  │
│  └───────────────────────────────────────────────────────┘  │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              Fetch Additional Data from Database             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ • News about your holdings                            │  │
│  │ • Causal chains for proposed trades                   │  │
│  │ • Historical market data (if needed)                  │  │
│  └───────────────────────────────────────────────────────┘  │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              Generate Professional Email HTML                │
│  • Executive Summary (4 metrics)                             │
│  • Market Overview (3 indices)                               │
│  • Current Holdings (from Alpaca)                            │
│  • News About Holdings                                       │
│  • Proposed Trades with Causal Flowcharts                    │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                    Send Email via SMTP                       │
│              (Gmail with app password)                       │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              You Receive Email in Inbox                      │
│        Click "Review Trades" → Approval Page                 │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 Usage Example

### **Manual Approval Workflow:**

```python
from config import TradingConfig
from email_data_populator import populate_approval_email_data
from email_template_enhanced import generate_professional_approval_email
from approval_handler import ApprovalHandler

# Check if manual approval is required
if TradingConfig.is_manual_approval_required():
    
    # Proposed trades from signal generation
    proposed_trades = [
        {'symbol': 'AAPL', 'shares': 10, 'price': 185.50, 'value': 1855.00},
        {'symbol': 'MSFT', 'shares': 8, 'price': 375.25, 'value': 3002.00},
    ]
    
    # Automatically fetch ALL data from Alpaca (real-time)
    email_data = populate_approval_email_data(
        proposed_trades=proposed_trades,
        use_alpaca=True  # Fetches from Alpaca API
    )
    
    # Data now contains:
    # - email_data['portfolio_value'] = 50000.00 (from Alpaca)
    # - email_data['cash'] = 40556.75 (from Alpaca)
    # - email_data['current_holdings'] = [TSLA, AMD, META] (from Alpaca)
    # - email_data['market_data'] = {S&P, NASDAQ, DOW} (from Alpaca)
    # - email_data['holdings_news'] = [...] (from database)
    # - email_data['trades'] = [...] (with causal chains)
    
    # Generate email HTML
    email_html = generate_professional_approval_email(
        approval_url=TradingConfig.APPROVAL_BASE_URL,
        request_id="approval_20251220_123456",
        **email_data
    )
    
    # Send email
    handler = ApprovalHandler()
    handler.send_approval_email(
        request_id="approval_20251220_123456",
        trades=email_data['trades'],
        portfolio_value=email_data['portfolio_value'],
        cash=email_data['cash']
    )
    
    print("✅ Approval email sent with real-time Alpaca data!")
```

---

## ✅ Summary

**YES, the system is built to automatically:**

1. ✅ **Fetch current positions from Alpaca** (real-time)
2. ✅ **Get portfolio value and cash** (real-time)
3. ✅ **Pull market data** (real-time via ETF proxies)
4. ✅ **Retrieve news and causal chains** (from database)
5. ✅ **Generate professional email** (with all data)
6. ✅ **Send email notification** (via SMTP)

**All of this happens automatically when a trade signal is generated and `AUTO_TRADE=false`.**

No manual intervention needed - the system fetches everything in real-time from Alpaca API and populates the email dynamically!
