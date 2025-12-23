"""
Configuration Management for ChronosProxy
Loads settings from YAML config file with environment variable substitution
"""

import os
import re
import yaml
from typing import Any, Dict, Optional
from pathlib import Path
from dotenv import load_dotenv


class ConfigError(Exception):
    """Configuration error"""
    pass


class Settings:
    """Application configuration manager"""

    def __init__(self, config_file: Optional[str] = None):
        """
        Initialize settings from config file

        Args:
            config_file: Path to YAML config file (default: config/config.yaml)
        """
        # Load environment variables from .env
        load_dotenv()

        # Determine config file path
        if config_file is None:
            config_file = os.getenv('CONFIG_FILE', 'config/config.yaml')

        self.config_file = Path(config_file)
        if not self.config_file.exists():
            raise ConfigError(f"Configuration file not found: {self.config_file}")

        # Load and parse config
        self._config = self._load_config()

        # Parse sections
        self.proxy = self._config.get('proxy', {})
        self.backend = self._config.get('backend', {})
        self.capabilities = self._config.get('capabilities', {})
        self.transformations = self._config.get('transformations', {})
        self.business_rules = self._config.get('business_rules', {})
        self.security = self._config.get('security', {})
        self.logging = self._config.get('logging', {})

    def _load_config(self) -> Dict[str, Any]:
        """Load YAML config file with environment variable substitution"""
        with open(self.config_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Substitute environment variables (${VAR_NAME} format)
        content = self._substitute_env_vars(content)

        # Parse YAML
        try:
            config = yaml.safe_load(content)
            if config is None:
                raise ConfigError("Config file is empty")
            return config
        except yaml.YAMLError as e:
            raise ConfigError(f"Failed to parse config file: {e}")

    def _substitute_env_vars(self, content: str) -> str:
        """
        Replace ${VAR_NAME} with environment variable values

        Args:
            content: YAML content with ${VAR} placeholders

        Returns:
            Content with environment variables substituted
        """
        pattern = r'\$\{([^}]+)\}'

        def replace(match):
            var_name = match.group(1)
            value = os.getenv(var_name)
            if value is None:
                # Check if it's a password field - allow empty for no password
                if var_name.endswith('PASSWORD'):
                    return ''  # Empty password
                raise ConfigError(
                    f"Environment variable '{var_name}' not found. "
                    f"Please set it in .env file or environment."
                )
            return value

        return re.sub(pattern, replace, content)

    def get_odbc_connection_string(self) -> str:
        """
        Build ODBC connection string from config

        Returns:
            ODBC connection string
        """
        odbc_config = self.backend.get('odbc', {})

        # Check if full connection string is provided
        if 'connection_string' in odbc_config:
            return odbc_config['connection_string']

        # Build from individual parameters
        params = {
            'DRIVER': odbc_config.get('driver', 'MySQL ODBC 8.0 Driver'),
            'SERVER': odbc_config.get('server', 'localhost'),
            'PORT': odbc_config.get('port', 3306),
            'DATABASE': odbc_config.get('database', ''),
            'USER': odbc_config.get('user', 'root'),
            'PASSWORD': odbc_config.get('password', ''),
        }

        # Optional parameters
        if 'options' in odbc_config:
            params['OPTION'] = odbc_config['options']
        if 'charset' in odbc_config:
            params['CHARSET'] = odbc_config['charset']

        # Build connection string
        conn_str = ';'.join([f"{k}={{{v}}}" if k == 'DRIVER' else f"{k}={v}"
                            for k, v in params.items()])
        conn_str += ';'

        return conn_str

    def get_native_connection_params(self) -> Dict[str, Any]:
        """
        Get native MySQL connection parameters

        Returns:
            Dictionary of connection parameters
        """
        native_config = self.backend.get('native', {})

        return {
            'host': native_config.get('host', 'localhost'),
            'port': native_config.get('port', 3306),
            'database': native_config.get('database', ''),
            'user': native_config.get('user', 'root'),
            'password': native_config.get('password', ''),
            'charset': native_config.get('charset', 'utf8mb4'),
            'connect_timeout': native_config.get('connect_timeout', 30),
        }

    def is_write_operation(self, keyword: str) -> bool:
        """
        Check if SQL keyword is a write operation

        Args:
            keyword: SQL keyword (first word of query)

        Returns:
            True if write operation
        """
        write_ops = self.security.get('write_operations', [])
        return keyword.upper() in [op.upper() for op in write_ops]

    def is_unsupported_feature(self, feature: str) -> bool:
        """
        Check if feature is unsupported

        Args:
            feature: Feature name (e.g., 'joins', 'unions')

        Returns:
            True if unsupported
        """
        unsupported = self.capabilities.get('unsupported_features', [])
        return feature.lower() in [f.lower() for f in unsupported]

    def is_unsupported_function(self, function: str) -> bool:
        """
        Check if function is unsupported

        Args:
            function: Function name (e.g., 'COUNT')

        Returns:
            True if unsupported
        """
        unsupported = self.capabilities.get('unsupported_functions', [])
        return function.upper() in [f.upper() for f in unsupported]

    def is_database_allowed(self, database: str) -> bool:
        """
        Check if database access is allowed

        Args:
            database: Database name

        Returns:
            True if allowed
        """
        allowed = self.business_rules.get('allowed_databases', [])
        blocked = self.business_rules.get('blocked_databases', [])

        # Check blocked list first
        if database.lower() in [db.lower() for db in blocked]:
            return False

        # If allowed list is empty, all are allowed (except blocked)
        if not allowed:
            return True

        # Check if in allowed list
        return database.lower() in [db.lower() for db in allowed]

    def __repr__(self) -> str:
        return f"Settings(config_file={self.config_file})"


# Global settings instance
_settings: Optional[Settings] = None


def get_settings(config_file: Optional[str] = None) -> Settings:
    """
    Get global settings instance (singleton pattern)

    Args:
        config_file: Path to config file (only used on first call)

    Returns:
        Settings instance
    """
    global _settings
    if _settings is None:
        _settings = Settings(config_file)
    return _settings


def reload_settings(config_file: Optional[str] = None) -> Settings:
    """
    Reload settings (useful for testing or config changes)

    Args:
        config_file: Path to config file

    Returns:
        New settings instance
    """
    global _settings
    _settings = Settings(config_file)
    return _settings
