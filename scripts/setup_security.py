#!/usr/bin/env python3
"""
Security Setup Script
Initialize security system and create first user
"""
import sys
from pathlib import Path
import getpass

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from security import get_security_manager

print("=" * 80)
print("SECURITY SETUP - TRADING SYSTEM")
print("=" * 80)

try:
    # Initialize security manager
    print("\n🔒 Initializing security system...")
    security = get_security_manager()
    print("✅ Security system initialized")
    print("   - Database tables created")
    print("   - Encryption key generated")
    print("   - Audit logging enabled")
    
    # Create first user
    print("\n👤 Create Administrator Account")
    print("-" * 80)
    
    username = input("Username: ").strip()
    email = input("Email: ").strip()
    
    while True:
        password = getpass.getpass("Password (min 12 chars): ")
        if len(password) < 12:
            print("❌ Password must be at least 12 characters")
            continue
        
        password_confirm = getpass.getpass("Confirm password: ")
        if password != password_confirm:
            print("❌ Passwords don't match")
            continue
        
        break
    
    # Create user
    print("\n🔄 Creating user account...")
    success = security.create_user(username, password, email)
    
    if success:
        print("✅ User account created successfully!")
        print(f"   Username: {username}")
        print(f"   Email: {email}")
        
        # Authenticate to verify
        print("\n🔐 Verifying authentication...")
        user_id = security.authenticate_user(username, password)
        
        if user_id:
            print("✅ Authentication verified")
            
            # Create session
            session_token = security.create_session(user_id, duration_hours=24)
            print(f"✅ Session token created (expires in 24 hours)")
            print(f"   Token: {session_token[:16]}...")
            
            # Show audit log
            print("\n📋 Recent Activity:")
            logs = security.get_audit_log(user_id=user_id, limit=5)
            for log in logs:
                print(f"   {log['timestamp']}: {log['action']}")
            
            print("\n" + "=" * 80)
            print("✅ SECURITY SETUP COMPLETE")
            print("=" * 80)
            print("\nYour trading system is now secured with:")
            print("  ✅ Password hashing (PBKDF2-SHA256)")
            print("  ✅ API key encryption (Fernet)")
            print("  ✅ Session management")
            print("  ✅ Audit logging")
            print("  ✅ One-time approval tokens")
            print("\nNext steps:")
            print("  1. Keep your password secure")
            print("  2. Never commit .env or encryption key to git")
            print("  3. Review docs/SECURITY.md for best practices")
            print("  4. Check audit logs regularly")
            
        else:
            print("❌ Authentication verification failed")
    else:
        print("❌ Failed to create user (username may already exist)")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    print(traceback.format_exc())
    sys.exit(1)
