#!/usr/bin/env python3
"""
YAML Configuration Loader
Loads trading system configuration from YAML file
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


class ConfigLoader:
    """Load and manage YAML configuration"""

    def __init__(self, config_path: str | None = None):
        """
        Initialize config loader

        Args:
            config_path: Path to YAML config file (default: config/trading_config.yaml)
        """
        if config_path is None:
            # Default to config/trading_config.yaml relative to project root
            project_root = Path(__file__).parent.parent.parent
            self.config_path = project_root / "config" / "trading_config.yaml"
        else:
            self.config_path = Path(config_path)
        self._config: dict[str, Any] = self._load_config()

    def _load_config(self) -> dict[str, Any]:
        """Load configuration from YAML file"""
        try:
            with open(self.config_path) as f:
                config: dict[str, Any] = yaml.safe_load(f) or {}
            logger.info(f"Loaded configuration from {self.config_path}")
            return config
        except FileNotFoundError:
            logger.error(f"Configuration file not found: {self.config_path}")
            raise
        except yaml.YAMLError as e:
            logger.error(f"Error parsing YAML configuration: {e}")
            raise

    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation

        Args:
            key_path: Dot-separated path (e.g., 'risk.max_portfolio_heat')
            default: Default value if key not found

        Returns:
            Configuration value
        """
        keys = key_path.split(".")
        value = self._config

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default

        return value

    def get_section(self, section: str) -> dict[str, Any]:
        """
        Get entire configuration section

        Args:
            section: Section name (e.g., 'risk', 'execution')

        Returns:
            Dictionary of section configuration
        """
        section_cfg: dict[str, Any] = self._config.get(section, {}) or {}
        return section_cfg

    def set_override(self, key_path: str, value: Any) -> None:
        """Set a config value in-memory using dot notation.

        Used by research tooling (run_backtest.py --set) for parameter-plateau
        sweeps — never persisted back to the YAML file.
        """
        keys = key_path.split(".")
        node = self._config
        for key in keys[:-1]:
            node = node.setdefault(key, {})
        node[keys[-1]] = value
        logger.info(f"Config override: {key_path} = {value!r}")

    def reload(self):
        """Reload configuration from file"""
        self._config = self._load_config()
        logger.info("Configuration reloaded")

    @property
    def config(self) -> dict[str, Any]:
        """Get full configuration dictionary"""
        return self._config


# Global config instance
_global_config = None


def get_config(config_path: str | None = None) -> ConfigLoader:
    """
    Get global configuration instance (singleton pattern)

    Args:
        config_path: Optional path to config file (only used on first call)

    Returns:
        ConfigLoader instance
    """
    global _global_config
    if _global_config is None:
        _global_config = ConfigLoader(config_path)
    return _global_config


def reload_config():
    """Reload global configuration"""
    global _global_config
    if _global_config is not None:
        _global_config.reload()
