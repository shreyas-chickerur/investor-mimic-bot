"""
Authentication System

JWT-based authentication with user management.
"""

import jwt
import bcrypt
from datetime import datetime, timedelta
from typing import Optional, Dict
from fastapi import HTTPException, status
from utils.enhanced_logging import get_logger
from utils.environment import env
from db.connection_pool import get_db_session

logger = get_logger(__name__)

SECRET_KEY = env.get("JWT_SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
REFRESH_TOKEN_EXPIRE_DAYS = 30


class AuthService:
    """Authentication service for user management."""

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password using bcrypt."""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode(), salt).decode()

    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        """Verify password against hash."""
        return bcrypt.checkpw(password.encode(), hashed.encode())

    @staticmethod
    def create_access_token(data: Dict, expires_delta: Optional[timedelta] = None) -> str:
        """Create JWT access token."""
        to_encode = data.copy()
        expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
        to_encode.update({"exp": expire, "type": "access"})
        return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    @staticmethod
    def create_refresh_token(data: Dict) -> str:
        """Create JWT refresh token."""
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        to_encode.update({"exp": expire, "type": "refresh"})
        return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    @staticmethod
    def decode_token(token: str) -> Dict:
        """Decode and verify JWT token."""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired")
        except jwt.JWTError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    @staticmethod
    def verify_token(token: str) -> Dict:
        """Verify JWT token and return payload. Alias for decode_token."""
        return AuthService.decode_token(token)

    @staticmethod
    def register_user(email: str, password: str, full_name: str) -> Dict:
        """Register a new user."""
        with get_db_session() as session:
            # Check if user exists
            result = session.execute("SELECT id FROM users WHERE email = :email", {"email": email})
            if result.fetchone():
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

            # Hash password
            password_hash = AuthService.hash_password(password)

            # Create user
            result = session.execute(
                """
                INSERT INTO users (email, password_hash, full_name)
                VALUES (:email, :password_hash, :full_name)
                RETURNING id, email, full_name, created_at
                """,
                {"email": email, "password_hash": password_hash, "full_name": full_name},
            )

            user = result.fetchone()

            # Create default settings
            session.execute(
                """
                INSERT INTO user_settings (user_id)
                VALUES (:user_id)
                """,
                {"user_id": user[0]},
            )

            # Create default preferences
            session.execute(
                """
                INSERT INTO user_preferences (user_id)
                VALUES (:user_id)
                """,
                {"user_id": user[0]},
            )

            logger.info(f"New user registered: {email}")

            return {
                "id": user[0],
                "email": user[1],
                "full_name": user[2],
                "created_at": user[3],
            }

    @staticmethod
    def login_user(email: str, password: str) -> Dict:
        """Login user and return tokens."""
        with get_db_session() as session:
            result = session.execute(
                """
                SELECT id, email, password_hash, full_name, is_active, is_verified, role
                FROM users
                WHERE email = :email
                """,
                {"email": email},
            )

            user = result.fetchone()

            if not user:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

            if not AuthService.verify_password(password, user[2]):
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

            if not user[4]:  # is_active
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")

            # Update last login
            session.execute("UPDATE users SET last_login = NOW() WHERE id = :user_id", {"user_id": user[0]})

            # Create tokens
            token_data = {"sub": str(user[0]), "email": user[1], "role": user[6]}
            access_token = AuthService.create_access_token(token_data)
            refresh_token = AuthService.create_refresh_token(token_data)

            # Store session
            token_hash = AuthService.hash_password(access_token)[:255]
            refresh_hash = AuthService.hash_password(refresh_token)[:255]

            session.execute(
                """
                INSERT INTO user_sessions (user_id, token_hash, refresh_token_hash, expires_at)
                VALUES (:user_id, :token_hash, :refresh_hash, :expires_at)
                """,
                {
                    "user_id": user[0],
                    "token_hash": token_hash,
                    "refresh_hash": refresh_hash,
                    "expires_at": datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
                },
            )

            logger.info(f"User logged in: {email}")

            return {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer",
                "user": {
                    "id": user[0],
                    "email": user[1],
                    "full_name": user[3],
                    "role": user[6],
                },
            }

    @staticmethod
    def get_current_user(token: str) -> Dict:
        """Get current user from token."""
        payload = AuthService.decode_token(token)
        user_id = payload.get("sub")

        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

        with get_db_session() as session:
            result = session.execute(
                """
                SELECT id, email, full_name, role, is_active
                FROM users
                WHERE id = :user_id
                """,
                {"user_id": int(user_id)},
            )

            user = result.fetchone()

            if not user:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

            if not user[4]:  # is_active
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")

            return {"id": user[0], "email": user[1], "full_name": user[2], "role": user[3]}

    @staticmethod
    def logout_user(token: str):
        """Logout user and invalidate token."""
        payload = AuthService.decode_token(token)
        user_id = payload.get("sub")

        with get_db_session() as session:
            token_hash = AuthService.hash_password(token)[:255]
            session.execute(
                """
                DELETE FROM user_sessions
                WHERE user_id = :user_id AND token_hash = :token_hash
                """,
                {"user_id": int(user_id), "token_hash": token_hash},
            )

        logger.info(f"User logged out: {user_id}")

    @staticmethod
    def track_activity(user_id: int, activity_type: str, activity_data: Dict = None):
        """Track user activity."""
        with get_db_session() as session:
            session.execute(
                """
                INSERT INTO user_activity (user_id, activity_type, activity_data)
                VALUES (:user_id, :activity_type, :activity_data)
                """,
                {
                    "user_id": user_id,
                    "activity_type": activity_type,
                    "activity_data": activity_data,
                },
            )
