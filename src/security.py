#!/usr/bin/env python3
"""
Security Module
Implements authentication, encryption, and data protection
"""
import os
import hashlib
import secrets
import hmac
from datetime import datetime, timedelta
from typing import Optional, Dict
import sqlite3
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
import base64


class SecurityManager:
    """Manages security for the trading system"""
    
    def __init__(self, db_path='data/trading_system.db'):
        self.db_path = db_path
        self._setup_security_tables()
        self._ensure_encryption_key()
    
    def _setup_security_tables(self):
        """Create security-related tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # User authentication table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                email TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                last_login TEXT
            )
        ''')
        
        # Session tokens table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token TEXT UNIQUE NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # API keys table (encrypted)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS api_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                service_name TEXT NOT NULL,
                encrypted_key TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # Audit log table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT NOT NULL,
                details TEXT,
                ip_address TEXT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Approval tokens table (one-time use)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS approval_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id TEXT NOT NULL,
                token TEXT UNIQUE NOT NULL,
                used BOOLEAN DEFAULT 0,
                expires_at TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def _ensure_encryption_key(self):
        """Ensure encryption key exists"""
        key_file = 'data/.encryption_key'
        
        if not os.path.exists(key_file):
            # Generate new encryption key
            key = Fernet.generate_key()
            
            # Save securely (in production, use key management service)
            os.makedirs('data', exist_ok=True)
            with open(key_file, 'wb') as f:
                f.write(key)
            
            # Restrict permissions
            os.chmod(key_file, 0o600)
        
        # Load key
        with open(key_file, 'rb') as f:
            self.encryption_key = f.read()
        
        self.cipher = Fernet(self.encryption_key)
    
    def hash_password(self, password: str, salt: Optional[bytes] = None) -> tuple:
        """
        Hash password with salt using PBKDF2
        Returns (hash, salt)
        """
        if salt is None:
            salt = secrets.token_bytes(32)
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        
        password_hash = base64.b64encode(kdf.derive(password.encode())).decode()
        salt_b64 = base64.b64encode(salt).decode()
        
        return password_hash, salt_b64
    
    def verify_password(self, password: str, password_hash: str, salt_b64: str) -> bool:
        """Verify password against hash"""
        salt = base64.b64decode(salt_b64)
        computed_hash, _ = self.hash_password(password, salt)
        return hmac.compare_digest(computed_hash, password_hash)
    
    def create_user(self, username: str, password: str, email: str) -> bool:
        """Create new user with hashed password"""
        try:
            password_hash, salt = self.hash_password(password)
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO users (username, password_hash, salt, email)
                VALUES (?, ?, ?, ?)
            ''', (username, password_hash, salt, email))
            
            conn.commit()
            conn.close()
            
            self.log_audit(None, 'USER_CREATED', f'Username: {username}')
            return True
        
        except sqlite3.IntegrityError:
            return False
    
    def authenticate_user(self, username: str, password: str) -> Optional[int]:
        """Authenticate user and return user_id if successful"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, password_hash, salt FROM users WHERE username = ?
        ''', (username,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            self.log_audit(None, 'LOGIN_FAILED', f'Username: {username}')
            return None
        
        user_id, password_hash, salt = row
        
        if self.verify_password(password, password_hash, salt):
            # Update last login
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE users SET last_login = ? WHERE id = ?
            ''', (datetime.now().isoformat(), user_id))
            conn.commit()
            conn.close()
            
            self.log_audit(user_id, 'LOGIN_SUCCESS', f'Username: {username}')
            return user_id
        
        self.log_audit(None, 'LOGIN_FAILED', f'Username: {username}')
        return None
    
    def create_session(self, user_id: int, duration_hours: int = 24) -> str:
        """Create session token for user"""
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(hours=duration_hours)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO sessions (user_id, token, expires_at)
            VALUES (?, ?, ?)
        ''', (user_id, token, expires_at.isoformat()))
        
        conn.commit()
        conn.close()
        
        self.log_audit(user_id, 'SESSION_CREATED', f'Expires: {expires_at}')
        return token
    
    def validate_session(self, token: str) -> Optional[int]:
        """Validate session token and return user_id"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT user_id, expires_at FROM sessions 
            WHERE token = ?
        ''', (token,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        user_id, expires_at = row
        
        if datetime.fromisoformat(expires_at) < datetime.now():
            self.log_audit(user_id, 'SESSION_EXPIRED', f'Token: {token[:8]}...')
            return None
        
        return user_id
    
    def encrypt_api_key(self, api_key: str) -> str:
        """Encrypt API key"""
        return self.cipher.encrypt(api_key.encode()).decode()
    
    def decrypt_api_key(self, encrypted_key: str) -> str:
        """Decrypt API key"""
        return self.cipher.decrypt(encrypted_key.encode()).decode()
    
    def store_api_key(self, user_id: int, service_name: str, api_key: str):
        """Store encrypted API key"""
        encrypted = self.encrypt_api_key(api_key)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO api_keys (user_id, service_name, encrypted_key)
            VALUES (?, ?, ?)
        ''', (user_id, service_name, encrypted))
        
        conn.commit()
        conn.close()
        
        self.log_audit(user_id, 'API_KEY_STORED', f'Service: {service_name}')
    
    def get_api_key(self, user_id: int, service_name: str) -> Optional[str]:
        """Retrieve and decrypt API key"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT encrypted_key FROM api_keys 
            WHERE user_id = ? AND service_name = ?
            ORDER BY created_at DESC LIMIT 1
        ''', (user_id, service_name))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return self.decrypt_api_key(row[0])
    
    def create_approval_token(self, request_id: str, duration_hours: int = 24) -> str:
        """Create one-time approval token"""
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(hours=duration_hours)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO approval_tokens (request_id, token, expires_at)
            VALUES (?, ?, ?)
        ''', (request_id, token, expires_at.isoformat()))
        
        conn.commit()
        conn.close()
        
        self.log_audit(None, 'APPROVAL_TOKEN_CREATED', f'Request: {request_id}')
        return token
    
    def validate_approval_token(self, token: str) -> Optional[str]:
        """
        Validate approval token (one-time use)
        Returns request_id if valid, None otherwise
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT request_id, used, expires_at FROM approval_tokens 
            WHERE token = ?
        ''', (token,))
        
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return None
        
        request_id, used, expires_at = row
        
        # Check if already used
        if used:
            conn.close()
            self.log_audit(None, 'APPROVAL_TOKEN_REUSE_ATTEMPT', f'Token: {token[:8]}...')
            return None
        
        # Check if expired
        if datetime.fromisoformat(expires_at) < datetime.now():
            conn.close()
            self.log_audit(None, 'APPROVAL_TOKEN_EXPIRED', f'Token: {token[:8]}...')
            return None
        
        # Mark as used
        cursor.execute('''
            UPDATE approval_tokens SET used = 1 WHERE token = ?
        ''', (token,))
        
        conn.commit()
        conn.close()
        
        self.log_audit(None, 'APPROVAL_TOKEN_USED', f'Request: {request_id}')
        return request_id
    
    def log_audit(self, user_id: Optional[int], action: str, details: str, ip_address: Optional[str] = None):
        """Log security audit event"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO audit_log (user_id, action, details, ip_address)
            VALUES (?, ?, ?, ?)
        ''', (user_id, action, details, ip_address))
        
        conn.commit()
        conn.close()
    
    def get_audit_log(self, user_id: Optional[int] = None, limit: int = 100) -> list:
        """Retrieve audit log"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if user_id:
            cursor.execute('''
                SELECT timestamp, action, details, ip_address
                FROM audit_log
                WHERE user_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (user_id, limit))
        else:
            cursor.execute('''
                SELECT timestamp, action, details, ip_address
                FROM audit_log
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [
            {
                'timestamp': row[0],
                'action': row[1],
                'details': row[2],
                'ip_address': row[3]
            }
            for row in rows
        ]
    
    def sanitize_input(self, input_str: str) -> str:
        """Sanitize user input to prevent injection attacks"""
        # Remove potentially dangerous characters
        dangerous_chars = ['<', '>', '"', "'", '&', ';', '|', '`', '$']
        sanitized = input_str
        for char in dangerous_chars:
            sanitized = sanitized.replace(char, '')
        return sanitized.strip()
    
    def validate_request_signature(self, request_data: Dict, signature: str, secret: str) -> bool:
        """Validate HMAC signature for API requests"""
        message = ''.join(f"{k}={v}" for k, v in sorted(request_data.items()))
        expected_signature = hmac.new(
            secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_signature)


# Global security manager instance
_security_manager = None

def get_security_manager():
    """Get or create global security manager instance"""
    global _security_manager
    if _security_manager is None:
        _security_manager = SecurityManager()
    return _security_manager
