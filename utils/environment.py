"""
Environment Configuration Manager

Handles loading environment-specific configurations.
"""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


class Environment:
    """Environment configuration manager."""

    def __init__(self):
        self.env = os.getenv("ENVIRONMENT", "development")
        self._load_env_file()

    def _load_env_file(self):
        """Load environment-specific .env file."""
        base_dir = Path(__file__).parent.parent
        env_file = base_dir / f".env.{self.env}"

        if not env_file.exists():
            raise FileNotFoundError(f"Environment file not found: {env_file}")
        else:
            load_dotenv(env_file)
            print(f"✓ Loaded {self.env} environment configuration")
            # Fall back to default .env
            default_env = base_dir / ".env"
            if default_env.exists():
                load_dotenv(default_env)
                print("✓ Loaded default environment configuration")

    @property
    def is_development(self) -> bool:
        """Check if running in development."""
        return self.env == "development"

    @property
    def is_staging(self) -> bool:
        """Check if running in staging."""
        return self.env == "staging"

    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.env == "production"

    @property
    def database_url(self) -> str:
        """Get database URL."""
        return os.getenv("DATABASE_URL", "postgresql://postgres@localhost:5432/investorbot_dev")

    @property
    def log_level(self) -> str:
        """Get log level."""
        return os.getenv("LOG_LEVEL", "INFO")

    @property
    def enable_real_trading(self) -> bool:
        """Check if real trading is enabled."""
        return os.getenv("ENABLE_REAL_TRADING", "False").lower() == "true"

    @property
    def api_rate_limit(self) -> int:
        """Get API rate limit."""
        return int(os.getenv("API_RATE_LIMIT", "100"))

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get environment variable."""
        return os.getenv(key, default)


# Global environment instance
env = Environment()
