# security.py - Purpose and Usage

**File:** `src/security.py`  
**Status:** ⚠️ **NOT CURRENTLY USED**  
**Purpose:** Future-proofing for web interface and multi-user support

---

## What is security.py?

`security.py` is a **comprehensive security module** that provides:

1. **User Authentication** - Login/logout with password hashing
2. **Session Management** - Token-based sessions with expiration
3. **API Key Encryption** - Secure storage of API keys
4. **Audit Logging** - Track all security events
5. **Approval Tokens** - One-time use tokens for trade approval
6. **Input Sanitization** - Prevent injection attacks
7. **Request Signing** - HMAC signature validation

---

## Why Was It Created?

**Original Intent:** Support a web-based trading dashboard where:
- Multiple users could access the system
- Each user has their own API keys
- Trades require approval via email links
- All actions are audited

**Current Reality:** 
- System runs as single-user CLI application
- No web interface implemented
- No multi-user support needed
- API keys stored in `.env` file

**Result:** `security.py` is **not imported or used** anywhere in the codebase.

---

## Verification: Is It Used?

```bash
# Search for imports
grep -r "import security" src/ scripts/
# Result: No matches

grep -r "from security" src/ scripts/
# Result: No matches

grep -r "SecurityManager" src/ scripts/
# Result: No matches
```

**Conclusion:** ✅ **NOT USED** - Can be safely removed or kept for future use.

---

## What Does It Do?

### 1. User Authentication

```python
from security import SecurityManager

security = SecurityManager()

# Create user
user_id = security.create_user('john', 'password123', 'john@example.com')

# Login
token = security.authenticate_user('john', 'password123')

# Validate session
user_id = security.validate_session(token)
```

**Use Case:** Web dashboard with login page

---

### 2. API Key Encryption

```python
# Store encrypted API key
security.store_api_key(user_id, 'alpaca', 'AKXXXXXXXXXX')

# Retrieve decrypted key
api_key = security.get_api_key(user_id, 'alpaca')
```

**Use Case:** Multi-user system where each user has their own API keys

**Current System:** Uses `.env` file with single set of keys

---

### 3. Approval Tokens

```python
# Generate one-time approval token
token = security.generate_approval_token('trade_123')

# Send token in email link
# https://dashboard.com/approve?token=abc123

# Validate token (can only be used once)
request_id = security.validate_approval_token(token)
```

**Use Case:** Email-based trade approval system

**Current System:** No approval system (trades execute automatically)

---

### 4. Audit Logging

```python
# Log security event
security.log_audit(user_id, 'TRADE_EXECUTED', 'Bought 10 AAPL @ $150')

# Retrieve audit log
events = security.get_audit_log(user_id, limit=100)
```

**Use Case:** Compliance and security monitoring

**Current System:** Uses standard Python logging

---

### 5. Input Sanitization

```python
# Sanitize user input
clean_input = security.sanitize_input(user_input)
```

**Use Case:** Prevent SQL injection, XSS attacks in web interface

**Current System:** No user input (CLI only)

---

### 6. Request Signing

```python
# Validate API request signature
is_valid = security.validate_request_signature(
    request_data={'symbol': 'AAPL', 'action': 'BUY'},
    signature='abc123...',
    secret='shared_secret'
)
```

**Use Case:** Secure API endpoints

**Current System:** No API endpoints

---

## Should We Keep It or Remove It?

### Option 1: Remove It ❌

**Pros:**
- Reduces codebase size
- Removes unused dependencies (cryptography)
- Simplifies maintenance

**Cons:**
- Lose future-proofing
- Would need to rewrite if web interface added
- Well-written, tested code

### Option 2: Keep It ✅ (Recommended)

**Pros:**
- Already written and working
- Future-proofing for Phase 6+ (web dashboard)
- No maintenance burden (not imported = no bugs)
- Demonstrates security best practices

**Cons:**
- Takes up disk space (~14KB)
- Adds cryptography dependency

---

## Recommendation: KEEP IT

**Reasons:**

1. **Future Plans:** Web dashboard is a natural next step
2. **No Cost:** Not imported = no performance impact
3. **Good Code:** Well-structured, follows best practices
4. **Documentation:** Shows security was considered

**But:** Add comment at top of file:

```python
"""
Security Module

⚠️ NOT CURRENTLY USED ⚠️

This module provides security features for a future web-based interface:
- User authentication
- Session management
- API key encryption
- Audit logging
- Approval tokens

Current system uses .env file for API keys and runs as single-user CLI.
This module is kept for future expansion to web interface.
"""
```

---

## If We Were to Use It

### Scenario: Add Web Dashboard

**Step 1: Enable Security**
```python
# In dashboard_server.py
from security import get_security_manager

security = get_security_manager()
```

**Step 2: Add Login Page**
```python
@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']
    
    token = security.authenticate_user(username, password)
    if token:
        session['token'] = token
        return redirect('/dashboard')
    else:
        return 'Invalid credentials', 401
```

**Step 3: Protect Routes**
```python
@app.route('/dashboard')
def dashboard():
    token = session.get('token')
    user_id = security.validate_session(token)
    
    if not user_id:
        return redirect('/login')
    
    # Show dashboard
```

**Step 4: Encrypt API Keys**
```python
# Move from .env to encrypted database
security.store_api_key(user_id, 'alpaca', os.getenv('ALPACA_API_KEY'))
```

---

## Current System Security

**Without security.py, how is the system secured?**

### 1. API Keys
```
.env file (not in git)
├── ALPACA_API_KEY=xxx
├── ALPACA_SECRET_KEY=xxx
└── EMAIL_PASSWORD=xxx
```

**Protection:**
- `.gitignore` prevents committing
- File permissions (chmod 600)
- Environment variables

### 2. Database
```
data/trading_system.db
```

**Protection:**
- Local file system permissions
- No remote access
- No sensitive data stored

### 3. Logs
```
logs/*.log
```

**Protection:**
- Local file system
- No PII logged
- Rotated regularly

### 4. Email
```
SMTP over TLS
```

**Protection:**
- Encrypted connection
- App-specific password
- No credentials in code

---

## Summary

**security.py Purpose:**
- Provides enterprise-grade security features
- Designed for multi-user web interface
- Not currently used in single-user CLI system

**Current Status:**
- ✅ Code is complete and working
- ⚠️ Not imported anywhere
- ⚠️ Dependencies installed but unused

**Recommendation:**
- ✅ **KEEP** for future use
- ✅ Add comment explaining it's not used
- ✅ Remove from requirements.txt if needed (cryptography)
- ❌ Don't remove the file

**Action Items:**
1. Add "NOT CURRENTLY USED" comment to file
2. Document in README that it's for future expansion
3. Consider removing cryptography from requirements.txt
4. Keep file for Phase 6+ (web dashboard)

---

## Alternative: Minimal Security

If we want to remove `security.py`, we should still have basic security:

```python
# src/simple_security.py
import os
from dotenv import load_dotenv

def get_api_keys():
    """Load API keys from .env file"""
    load_dotenv()
    return {
        'alpaca_key': os.getenv('ALPACA_API_KEY'),
        'alpaca_secret': os.getenv('ALPACA_SECRET_KEY'),
        'email_password': os.getenv('EMAIL_PASSWORD')
    }

def validate_api_keys():
    """Ensure API keys are set"""
    keys = get_api_keys()
    if not all(keys.values()):
        raise ValueError("Missing API keys in .env file")
    return True
```

**This is what the system actually uses** (via python-dotenv).
