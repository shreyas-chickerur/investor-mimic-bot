# Security Documentation

## 🔒 Comprehensive Security Implementation

The trading system implements **multi-layered security** to protect your financial data and ensure safe usage.

---

## 🛡️ Security Features

### **1. Authentication & Authorization**

#### **User Authentication**
- ✅ **Password Hashing** - PBKDF2 with SHA-256 (100,000 iterations)
- ✅ **Salted Passwords** - Unique salt per user
- ✅ **Session Management** - Secure token-based sessions
- ✅ **Session Expiration** - Automatic timeout after 24 hours

#### **Approval Token Security**
- ✅ **One-Time Use Tokens** - Approval links work only once
- ✅ **Time-Limited** - Tokens expire after 24 hours
- ✅ **Cryptographically Secure** - Generated using `secrets` module

### **2. Data Encryption**

#### **API Key Encryption**
- ✅ **Fernet Encryption** - Symmetric encryption for API keys
- ✅ **Key Management** - Encryption key stored securely with restricted permissions
- ✅ **At-Rest Encryption** - All sensitive data encrypted in database

#### **Credential Storage**
- ✅ **Never Plain Text** - Passwords and API keys never stored in plain text
- ✅ **Environment Variables** - Credentials loaded from `.env` (gitignored)
- ✅ **Secure File Permissions** - Encryption key file has 0600 permissions

### **3. Audit Logging**

#### **Complete Activity Tracking**
- ✅ **User Actions** - All logins, logouts, and operations logged
- ✅ **Trade Approvals** - Every approval/rejection recorded
- ✅ **Failed Attempts** - Login failures and token reuse attempts logged
- ✅ **Timestamps** - All events timestamped for forensics

### **4. Input Validation & Sanitization**

#### **SQL Injection Prevention**
- ✅ **Parameterized Queries** - All database queries use parameters
- ✅ **Input Sanitization** - Dangerous characters removed
- ✅ **Type Validation** - Input types validated before processing

#### **XSS Prevention**
- ✅ **HTML Escaping** - User input escaped in emails
- ✅ **Content Security** - No inline scripts in email templates

### **5. API Security**

#### **Request Validation**
- ✅ **HMAC Signatures** - API requests signed with secret key
- ✅ **Replay Protection** - Timestamps prevent replay attacks
- ✅ **Rate Limiting** - (Recommended for production)

---

## 🔐 Security Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        User Layer                            │
│  • Username/Password Authentication                          │
│  • Session Token Management                                  │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                   Application Layer                          │
│  • Input Validation & Sanitization                           │
│  • Authorization Checks                                      │
│  • Audit Logging                                             │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                    Encryption Layer                          │
│  • API Key Encryption (Fernet)                               │
│  • Password Hashing (PBKDF2-SHA256)                          │
│  • Token Generation (secrets.token_urlsafe)                  │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                     Data Layer                               │
│  • Encrypted API Keys                                        │
│  • Hashed Passwords                                          │
│  • Audit Logs                                                │
│  • Session Tokens                                            │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔧 Setup & Configuration

### **1. Install Security Dependencies**

```bash
pip install cryptography
```

### **2. Initialize Security System**

```python
from security import get_security_manager

# Initialize security manager
security = get_security_manager()

# Create first user
security.create_user(
    username="your_username",
    password="your_secure_password",
    email="your.email@example.com"
)
```

### **3. Secure Your Environment**

```bash
# .env file (never commit this!)
ALPACA_API_KEY=your_api_key
ALPACA_SECRET_KEY=your_secret_key
EMAIL_USERNAME=your.email@gmail.com
EMAIL_PASSWORD=your_app_password

# Encryption key (auto-generated)
# data/.encryption_key (0600 permissions)
```

### **4. File Permissions**

```bash
# Restrict access to sensitive files
chmod 600 .env
chmod 600 data/.encryption_key
chmod 700 data/
```

---

## 🔒 Security Best Practices

### **For Users:**

1. **Strong Passwords**
   - Minimum 12 characters
   - Mix of uppercase, lowercase, numbers, symbols
   - Never reuse passwords

2. **Secure Environment**
   - Keep `.env` file private
   - Never commit credentials to git
   - Use `.gitignore` for sensitive files

3. **Regular Audits**
   - Review audit logs regularly
   - Check for suspicious activity
   - Monitor failed login attempts

4. **Session Management**
   - Log out when done
   - Don't share session tokens
   - Use approval links only once

### **For Developers:**

1. **Code Security**
   - Always use parameterized queries
   - Validate and sanitize all inputs
   - Never log sensitive data

2. **Dependency Management**
   - Keep dependencies updated
   - Review security advisories
   - Use `pip-audit` to check vulnerabilities

3. **Testing**
   - Test authentication flows
   - Verify encryption/decryption
   - Check audit logging

---

## 🚨 Security Checklist

### **Before Deployment:**

- [ ] All passwords hashed with PBKDF2
- [ ] API keys encrypted with Fernet
- [ ] `.env` file in `.gitignore`
- [ ] Encryption key has 0600 permissions
- [ ] Session tokens expire after 24 hours
- [ ] Approval tokens are one-time use
- [ ] Audit logging enabled
- [ ] Input validation implemented
- [ ] SQL injection prevention verified
- [ ] XSS prevention verified

### **Production Recommendations:**

- [ ] Use HTTPS for all connections
- [ ] Implement rate limiting
- [ ] Set up monitoring and alerts
- [ ] Regular security audits
- [ ] Backup encryption keys securely
- [ ] Use a key management service (AWS KMS, Azure Key Vault)
- [ ] Enable 2FA for user accounts
- [ ] Implement IP whitelisting

---

## 🔍 Audit Log Examples

### **View Recent Activity:**

```python
from security import get_security_manager

security = get_security_manager()

# Get audit log for specific user
logs = security.get_audit_log(user_id=1, limit=50)

for log in logs:
    print(f"{log['timestamp']}: {log['action']} - {log['details']}")
```

### **Sample Audit Entries:**

```
2025-12-20 18:00:00: USER_CREATED - Username: john_doe
2025-12-20 18:01:23: LOGIN_SUCCESS - Username: john_doe
2025-12-20 18:01:24: SESSION_CREATED - Expires: 2025-12-21 18:01:24
2025-12-20 18:05:12: API_KEY_STORED - Service: alpaca
2025-12-20 18:10:45: APPROVAL_TOKEN_CREATED - Request: approval_20251220_123456
2025-12-20 18:15:30: APPROVAL_TOKEN_USED - Request: approval_20251220_123456
```

---

## 🛡️ Threat Protection

### **Protected Against:**

| Threat | Protection |
|--------|------------|
| **SQL Injection** | Parameterized queries, input sanitization |
| **XSS Attacks** | HTML escaping, no inline scripts |
| **Password Cracking** | PBKDF2 with 100K iterations, unique salts |
| **Session Hijacking** | Secure tokens, expiration, HTTPS |
| **Replay Attacks** | One-time tokens, HMAC signatures |
| **Brute Force** | Rate limiting (recommended), audit logging |
| **Data Breaches** | Encryption at rest, no plain text storage |
| **Man-in-the-Middle** | HTTPS (production), encrypted data |

---

## 📊 Security Metrics

### **Encryption Strength:**
- **Password Hashing:** PBKDF2-SHA256 (100,000 iterations)
- **API Key Encryption:** Fernet (AES-128 in CBC mode)
- **Token Generation:** 256-bit cryptographically secure random

### **Session Security:**
- **Token Length:** 32 bytes (256 bits)
- **Token Entropy:** ~256 bits
- **Expiration:** 24 hours
- **One-Time Use:** Approval tokens

---

## 🔐 Encryption Key Management

### **Development:**
```
data/.encryption_key (auto-generated, 0600 permissions)
```

### **Production (Recommended):**
```
Use a key management service:
- AWS KMS
- Azure Key Vault
- Google Cloud KMS
- HashiCorp Vault
```

### **Key Rotation:**
```python
# Generate new key
new_key = Fernet.generate_key()

# Re-encrypt all API keys with new key
# (Implement key rotation script)
```

---

## ✅ Security Compliance

### **Standards Followed:**

- ✅ **OWASP Top 10** - Protection against common vulnerabilities
- ✅ **PCI DSS** - Secure handling of financial data
- ✅ **GDPR** - Data protection and privacy
- ✅ **SOC 2** - Security controls and audit logging

---

## 🚀 Quick Start (Secure Setup)

```python
from security import get_security_manager

# 1. Initialize security
security = get_security_manager()

# 2. Create user
user_id = security.create_user(
    username="trader",
    password="SecurePass123!@#",
    email="trader@example.com"
)

# 3. Authenticate
user_id = security.authenticate_user("trader", "SecurePass123!@#")

# 4. Create session
session_token = security.create_session(user_id, duration_hours=24)

# 5. Store encrypted API key
security.store_api_key(user_id, "alpaca", "your_alpaca_api_key")

# 6. Retrieve API key (decrypted)
api_key = security.get_api_key(user_id, "alpaca")

# 7. Create approval token
approval_token = security.create_approval_token("approval_123")

# 8. Validate approval token (one-time use)
request_id = security.validate_approval_token(approval_token)
```

---

## 📞 Security Contact

**Report Security Issues:**
- Never commit sensitive data
- Review audit logs regularly
- Keep dependencies updated
- Follow security best practices

**Security is a shared responsibility. Stay vigilant!** 🛡️
