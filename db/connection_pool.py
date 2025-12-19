"""
Database Connection Pooling

Implements efficient connection pooling for PostgreSQL database operations.
"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager
from typing import Generator
from utils.environment import env
from utils.enhanced_logging import get_logger

logger = get_logger(__name__)


class DatabasePool:
    """Database connection pool manager."""
    
    def __init__(self):
        self.engine = None
        self.session_factory = None
        self._initialize_pool()
    
    def _initialize_pool(self):
        """Initialize connection pool with optimal settings."""
        database_url = env.database_url
        
        # Pool configuration
        pool_config = {
            'poolclass': QueuePool,
            'pool_size': 10,              # Number of connections to maintain
            'max_overflow': 20,           # Additional connections when pool is full
            'pool_timeout': 30,           # Timeout for getting connection
            'pool_recycle': 3600,         # Recycle connections after 1 hour
            'pool_pre_ping': True,        # Verify connections before using
            'echo': env.is_development,   # Log SQL in development
        }
        
        try:
            self.engine = create_engine(database_url, **pool_config)
            
            # Add connection event listeners
            @event.listens_for(self.engine, "connect")
            def receive_connect(dbapi_conn, connection_record):
                logger.debug("Database connection established")
            
            @event.listens_for(self.engine, "checkout")
            def receive_checkout(dbapi_conn, connection_record, connection_proxy):
                logger.debug("Connection checked out from pool")
            
            @event.listens_for(self.engine, "checkin")
            def receive_checkin(dbapi_conn, connection_record):
                logger.debug("Connection returned to pool")
            
            # Create session factory
            self.session_factory = scoped_session(
                sessionmaker(
                    bind=self.engine,
                    autocommit=False,
                    autoflush=False,
                    expire_on_commit=False
                )
            )
            
            logger.info("Database connection pool initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize database pool: {e}", error=e)
            raise
    
    @contextmanager
    def get_session(self) -> Generator:
        """
        Get database session from pool.
        
        Usage:
            with db_pool.get_session() as session:
                session.query(...)
        """
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {e}", error=e)
            raise
        finally:
            session.close()
    
    def execute_query(self, query: str, params: dict = None):
        """Execute a raw SQL query."""
        with self.get_session() as session:
            result = session.execute(query, params or {})
            return result.fetchall()
    
    def get_pool_status(self) -> dict:
        """Get current pool status for monitoring."""
        pool = self.engine.pool
        return {
            'size': pool.size(),
            'checked_in': pool.checkedin(),
            'checked_out': pool.checkedout(),
            'overflow': pool.overflow(),
            'total_connections': pool.size() + pool.overflow()
        }
    
    def dispose(self):
        """Dispose of all connections in pool."""
        if self.engine:
            self.engine.dispose()
            logger.info("Database connection pool disposed")


# Global database pool instance
_db_pool = None


def get_db_pool() -> DatabasePool:
    """Get global database pool instance."""
    global _db_pool
    if _db_pool is None:
        _db_pool = DatabasePool()
    return _db_pool


@contextmanager
def get_db_session():
    """
    Convenience function to get database session.
    
    Usage:
        from db.connection_pool import get_db_session
        
        with get_db_session() as session:
            results = session.query(Holdings).all()
    """
    pool = get_db_pool()
    with pool.get_session() as session:
        yield session


def execute_sql(query: str, params: dict = None):
    """
    Execute raw SQL query.
    
    Usage:
        from db.connection_pool import execute_sql
        
        results = execute_sql(
            "SELECT * FROM holdings WHERE ticker = :ticker",
            {"ticker": "AAPL"}
        )
    """
    pool = get_db_pool()
    return pool.execute_query(query, params)


def get_pool_metrics() -> dict:
    """Get connection pool metrics for monitoring."""
    pool = get_db_pool()
    return pool.get_pool_status()
