"""
Configuration module for TachyonAI.
This module provides configuration settings for the application.
"""
import os
import logging
from enum import Enum
from typing import Dict, Any, Optional, Union, List

# Initialize logger
logger = logging.getLogger(__name__)


class ConfigSettingEnum(str, Enum):
    """
    Enum for configuration settings.

    Attributes:
        DEBUG: Debug mode
        ENVIRONMENT: Application environment
        LOG_LEVEL: Logging level
        DATABASE_URL: Database connection URL
        SECRET_KEY: Secret key for JWT token generation
        ACCESS_TOKEN_EXPIRE_MINUTES: JWT token expiration time in minutes
        CORS_ORIGINS: CORS allowed origins
        STATIC_DIR: Static files directory
        TEMPLATES_DIR: Templates directory
        UPLOAD_DIR: Upload directory for user files
        MAX_UPLOAD_SIZE: Maximum upload size in bytes
        ALLOWED_EXTENSIONS: Allowed file extensions for uploads
    """
    DEBUG = "DEBUG"
    ENVIRONMENT = "ENVIRONMENT"
    LOG_LEVEL = "LOG_LEVEL"
    DATABASE_URL = "DATABASE_URL"
    SECRET_KEY = "SECRET_KEY"
    ACCESS_TOKEN_EXPIRE_MINUTES = "ACCESS_TOKEN_EXPIRE_MINUTES"
    CORS_ORIGINS = "CORS_ORIGINS"
    STATIC_DIR = "STATIC_DIR"
    TEMPLATES_DIR = "TEMPLATES_DIR"
    UPLOAD_DIR = "UPLOAD_DIR"
    MAX_UPLOAD_SIZE = "MAX_UPLOAD_SIZE"
    ALLOWED_EXTENSIONS = "ALLOWED_EXTENSIONS"


class EnvironmentEnum(str, Enum):
    """
    Enum for application environments.

    Attributes:
        DEVELOPMENT: Development environment
        TESTING: Testing environment
        STAGING: Staging environment
        PRODUCTION: Production environment
    """
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


class LogLevelEnum(str, Enum):
    """
    Enum for logging levels.

    Attributes:
        DEBUG: Debug level
        INFO: Info level
        WARNING: Warning level
        ERROR: Error level
        CRITICAL: Critical level
    """
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class Config:
    """
    Configuration class for the application.
    """
    # Default configuration
    _defaults = {
        ConfigSettingEnum.DEBUG: True,
        ConfigSettingEnum.ENVIRONMENT: EnvironmentEnum.DEVELOPMENT,
        ConfigSettingEnum.LOG_LEVEL: LogLevelEnum.INFO,
        ConfigSettingEnum.DATABASE_URL: "sqlite:///tachyonai.db",
        ConfigSettingEnum.SECRET_KEY: "your-secret-key",
        ConfigSettingEnum.ACCESS_TOKEN_EXPIRE_MINUTES: 30,
        ConfigSettingEnum.CORS_ORIGINS: ["*"],
        ConfigSettingEnum.STATIC_DIR: "frontend/static",
        ConfigSettingEnum.TEMPLATES_DIR: "frontend/templates",
        ConfigSettingEnum.UPLOAD_DIR: "uploads",
        ConfigSettingEnum.MAX_UPLOAD_SIZE: 10 * 1024 * 1024,  # 10 MB
        ConfigSettingEnum.ALLOWED_EXTENSIONS: ["jpg", "jpeg", "png", "gif"],
    }

    # Environment variable prefix
    _env_prefix = "TACHYONAI_"

    # Configuration values
    _config: Dict[ConfigSettingEnum, Any] = {}

    @classmethod
    def load(cls) -> None:
        """
        Load configuration from environment variables and defaults.
        """
        # Start with defaults
        cls._config = cls._defaults.copy()

        # Override with environment variables
        for setting in ConfigSettingEnum:
            env_var = f"{cls._env_prefix}{setting.value}"
            if env_var in os.environ:
                cls._config[setting] = cls._parse_env_value(setting, os.environ[env_var])

        # Log configuration
        logger.info(f"Loaded configuration: {cls._config}")

    @classmethod
    def _parse_env_value(cls, setting: ConfigSettingEnum, value: str) -> Any:
        """
        Parse environment variable value based on the setting type.

        Args:
            setting: Configuration setting
            value: Environment variable value

        Returns:
            Parsed value
        """
        # Get the default value to determine the type
        default_value = cls._defaults.get(setting)

        # Parse based on the default value type
        if isinstance(default_value, bool):
            return value.lower() in ("true", "1", "yes", "y")
        elif isinstance(default_value, int):
            return int(value)
        elif isinstance(default_value, float):
            return float(value)
        elif isinstance(default_value, list):
            return value.split(",")
        elif isinstance(default_value, dict):
            # Parse JSON string
            import json
            return json.loads(value)
        elif isinstance(default_value, Enum):
            # Parse enum value
            return type(default_value)(value)
        else:
            # Return as string
            return value

    @classmethod
    def get(cls, setting: ConfigSettingEnum) -> Any:
        """
        Get a configuration setting.

        Args:
            setting: Configuration setting

        Returns:
            Configuration value
        """
        if not cls._config:
            cls.load()
        return cls._config.get(setting, cls._defaults.get(setting))

    @classmethod
    def set(cls, setting: ConfigSettingEnum, value: Any) -> None:
        """
        Set a configuration setting.

        Args:
            setting: Configuration setting
            value: Configuration value
        """
        if not cls._config:
            cls.load()
        cls._config[setting] = value
        logger.info(f"Updated configuration: {setting} = {value}")

    @classmethod
    def is_debug(cls) -> bool:
        """
        Check if debug mode is enabled.

        Returns:
            True if debug mode is enabled, False otherwise
        """
        return cls.get(ConfigSettingEnum.DEBUG)

    @classmethod
    def get_environment(cls) -> EnvironmentEnum:
        """
        Get the application environment.

        Returns:
            Application environment
        """
        return cls.get(ConfigSettingEnum.ENVIRONMENT)

    @classmethod
    def is_production(cls) -> bool:
        """
        Check if the application is running in production.

        Returns:
            True if in production, False otherwise
        """
        return cls.get_environment() == EnvironmentEnum.PRODUCTION

    @classmethod
    def get_log_level(cls) -> LogLevelEnum:
        """
        Get the logging level.

        Returns:
            Logging level
        """
        return cls.get(ConfigSettingEnum.LOG_LEVEL)

    @classmethod
    def get_database_url(cls) -> str:
        """
        Get the database connection URL.

        Returns:
            Database connection URL
        """
        return cls.get(ConfigSettingEnum.DATABASE_URL)

    @classmethod
    def get_secret_key(cls) -> str:
        """
        Get the secret key for JWT token generation.

        Returns:
            Secret key
        """
        return cls.get(ConfigSettingEnum.SECRET_KEY)

    @classmethod
    def get_access_token_expire_minutes(cls) -> int:
        """
        Get the JWT token expiration time in minutes.

        Returns:
            JWT token expiration time in minutes
        """
        return cls.get(ConfigSettingEnum.ACCESS_TOKEN_EXPIRE_MINUTES)

    @classmethod
    def get_cors_origins(cls) -> List[str]:
        """
        Get the CORS allowed origins.

        Returns:
            CORS allowed origins
        """
        return cls.get(ConfigSettingEnum.CORS_ORIGINS)

    @classmethod
    def get_static_dir(cls) -> str:
        """
        Get the static files directory.

        Returns:
            Static files directory
        """
        return cls.get(ConfigSettingEnum.STATIC_DIR)

    @classmethod
    def get_templates_dir(cls) -> str:
        """
        Get the templates directory.

        Returns:
            Templates directory
        """
        return cls.get(ConfigSettingEnum.TEMPLATES_DIR)

    @classmethod
    def get_upload_dir(cls) -> str:
        """
        Get the upload directory for user files.

        Returns:
            Upload directory
        """
        return cls.get(ConfigSettingEnum.UPLOAD_DIR)

    @classmethod
    def get_max_upload_size(cls) -> int:
        """
        Get the maximum upload size in bytes.

        Returns:
            Maximum upload size in bytes
        """
        return cls.get(ConfigSettingEnum.MAX_UPLOAD_SIZE)

    @classmethod
    def get_allowed_extensions(cls) -> List[str]:
        """
        Get the allowed file extensions for uploads.

        Returns:
            Allowed file extensions
        """
        return cls.get(ConfigSettingEnum.ALLOWED_EXTENSIONS)
