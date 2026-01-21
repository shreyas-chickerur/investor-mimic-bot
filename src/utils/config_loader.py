#!/usr/bin/env python3
"""
YAML Configuration Loader
Loads trading system configuration from YAML file
"""
import yaml
from pathlib import Path
from typing import Any, Dict
import logging

logger = logging.getLogger(__name__)


class ConfigLoader:
    """Load and manage YAML configuration"""
    
    def __init__(self, config_path: str = None):
        """
        Initialize config loader
        
        Args:
            config_path: Path to YAML config file (default: config/trading_config.yaml)
        """
        if config_path is None:
            # Default to config/trading_config.yaml relative to project root
            project_root = Path(__file__).parent.parent.parent
            config_path = project_root / 'config' / 'trading_config.yaml'
        
        self.config_path = Path(config_path)
        self._config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
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
        keys = key_path.split('.')
        value = self._config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value
    
    def get_section(self, section: str) -> Dict[str, Any]:
        """
        Get entire configuration section
        
        Args:
            section: Section name (e.g., 'risk', 'execution')
            
        Returns:
            Dictionary of section configuration
        """
        return self._config.get(section, {})
    
    def reload(self):
        """Reload configuration from file"""
        self._config = self._load_config()
        logger.info("Configuration reloaded")
    
    @property
    def config(self) -> Dict[str, Any]:
        """Get full configuration dictionary"""
        return self._config


# Global config instance
_global_config = None


def get_config(config_path: str = None) -> ConfigLoader:
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
