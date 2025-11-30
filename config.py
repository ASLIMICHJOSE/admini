#!/usr/bin/env python3
"""
JARVIS Configuration Management

Centralized configuration with dataclasses for type safety,
environment variable loading, and platform detection.
"""

import os
import logging
import platform
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict, Any

import yaml
from dotenv import load_dotenv


@dataclass
class AudioConfig:
    """Audio configuration settings."""
    wake_word_enabled: bool = True
    wake_word: str = "Hey JARVIS"
    hotkey_combination: str = "ctrl+space"
    microphone_device: Optional[str] = None
    speaker_device: Optional[str] = None
    sensitivity: float = 0.5
    timeout_seconds: int = 5
    sample_rate: int = 16000
    channels: int = 1


@dataclass
class AIConfig:
    """AI and NLP configuration settings."""
    use_openai: bool = True
    openai_model: str = "gpt-4-turbo-preview"
    max_tokens: int = 500
    temperature: float = 0.7
    cache_responses: bool = True
    cache_ttl_hours: int = 1
    offline_fallback: bool = True


@dataclass
class SystemConfig:
    """System control configuration settings."""
    allowed_applications: List[str] = field(default_factory=lambda: [
        "Chrome", "Firefox", "Safari", "Edge", "VS Code", "Visual Studio Code",
        "Spotify", "Discord", "Slack", "Zoom", "VLC", "Notepad", "TextEdit"
    ])
    confirmation_required: List[str] = field(default_factory=lambda: [
        "shutdown", "restart", "delete_files", "send_email", "install"
    ])
    sensitive_commands_hotkey_only: bool = True


@dataclass
class WebConfig:
    """Web automation configuration settings."""
    default_browser: str = "chrome"
    headless_mode: bool = False
    search_results_count: int = 10
    ad_blocker_enabled: bool = True
    user_agent: Optional[str] = None


@dataclass
class MediaConfig:
    """Media and entertainment configuration settings."""
    music_directories: List[str] = field(default_factory=lambda: [
        "~/Music", "~/Documents/Music"
    ])
    default_volume: int = 70
    supported_formats: List[str] = field(default_factory=lambda: [
        "mp3", "flac", "wav", "m4a", "ogg"
    ])


@dataclass
class NotificationConfig:
    """Notification system configuration settings."""
    desktop_notifications: bool = True
    voice_announcements: bool = True
    mobile_notifications: bool = False
    sms_gateway_email: Optional[str] = None


@dataclass
class PrivacyConfig:
    """Privacy and security configuration settings."""
    log_sensitive_commands: bool = False
    cache_sensitive_data: bool = False
    require_hotkey_for_sensitive: bool = True
    data_retention_days: int = 30


@dataclass
class APIKeys:
    """API keys and authentication configuration."""
    openai_api_key: str = ""
    weather_api_key: str = ""
    news_api_key: str = ""
    email_username: str = ""
    email_password: str = ""
    email_smtp_server: str = "smtp.gmail.com"
    email_smtp_port: int = 587


@dataclass
class Config:
    """Main configuration container."""
    audio: AudioConfig = field(default_factory=AudioConfig)
    ai: AIConfig = field(default_factory=AIConfig)
    system: SystemConfig = field(default_factory=SystemConfig)
    web: WebConfig = field(default_factory=WebConfig)
    media: MediaConfig = field(default_factory=MediaConfig)
    notifications: NotificationConfig = field(default_factory=NotificationConfig)
    privacy: PrivacyConfig = field(default_factory=PrivacyConfig)
    api_keys: APIKeys = field(default_factory=APIKeys)

    # Runtime settings
    log_level: str = "INFO"
    log_file: str = "jarvis.log"

    def __post_init__(self):
        """Initialize platform-specific settings."""
        # Detect platform and adjust defaults
        system = platform.system().lower()
        if system == "windows":
            self.audio.microphone_device = None
            self.audio.speaker_device = None
            self.web.default_browser = "chrome"
        elif system == "darwin":  # macOS
            self.web.default_browser = "safari"
            self.media.music_directories.append("~/Music/iTunes")
        elif system == "linux":
            self.web.default_browser = "firefox"

    @classmethod
    def load_from_file(cls, config_path: str) -> "Config":
        """Load configuration from YAML file."""
        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        try:
            with open(config_file, 'r') as f:
                config_data = yaml.safe_load(f)

            # Create nested config objects
            config = cls()

            if "audio" in config_data:
                config.audio = AudioConfig(**config_data["audio"])
            if "ai" in config_data:
                config.ai = AIConfig(**config_data["ai"])
            if "system" in config_data:
                config.system = SystemConfig(**config_data["system"])
            if "web" in config_data:
                config.web = WebConfig(**config_data["web"])
            if "media" in config_data:
                config.media = MediaConfig(**config_data["media"])
            if "notifications" in config_data:
                config.notifications = NotificationConfig(**config_data["notifications"])
            if "privacy" in config_data:
                config.privacy = PrivacyConfig(**config_data["privacy"])
            if "log_level" in config_data:
                config.log_level = config_data["log_level"]
            if "log_file" in config_data:
                config.log_file = config_data["log_file"]

            return config

        except Exception as e:
            raise ValueError(f"Error loading configuration: {e}")

    def save_to_file(self, config_path: str):
        """Save configuration to YAML file."""
        config_data = {
            "audio": self.audio.__dict__,
            "ai": self.ai.__dict__,
            "system": self.system.__dict__,
            "web": self.web.__dict__,
            "media": self.media.__dict__,
            "notifications": self.notifications.__dict__,
            "privacy": self.privacy.__dict__,
            "log_level": self.log_level,
            "log_file": self.log_file
        }

        config_file = Path(config_path)
        config_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(config_file, 'w') as f:
                yaml.dump(config_data, f, default_flow_style=False, indent=2)
        except Exception as e:
            raise ValueError(f"Error saving configuration: {e}")

    def load_environment_variables(self):
        """Load configuration from environment variables."""
        # Load .env file if it exists
        load_dotenv()

        # Audio settings
        self.audio.wake_word_enabled = os.getenv("WAKE_WORD_ENABLED", "").lower() in ("true", "1", "yes")
        self.audio.wake_word = os.getenv("WAKE_WORD", self.audio.wake_word)
        self.audio.hotkey_combination = os.getenv("HOTKEY_COMBINATION", self.audio.hotkey_combination)

        # AI settings
        self.ai.use_openai = os.getenv("USE_OPENAI", "").lower() in ("true", "1", "yes")
        self.ai.openai_model = os.getenv("OPENAI_MODEL", self.ai.openai_model)
        self.ai.cache_responses = os.getenv("CACHE_RESPONSES", "").lower() in ("true", "1", "yes")

        # API keys
        self.api_keys.openai_api_key = os.getenv("OPENAI_API_KEY", "")
        self.api_keys.weather_api_key = os.getenv("WEATHER_API_KEY", "")
        self.api_keys.news_api_key = os.getenv("NEWS_API_KEY", "")

        # Email settings
        self.api_keys.email_username = os.getenv("EMAIL_USERNAME", "")
        self.api_keys.email_password = os.getenv("EMAIL_PASSWORD", "")
        self.api_keys.email_smtp_server = os.getenv("EMAIL_SMTP_SERVER", self.api_keys.email_smtp_server)
        self.api_keys.email_smtp_port = int(os.getenv("EMAIL_SMTP_PORT", str(self.api_keys.email_smtp_port)))

        # Privacy settings
        self.privacy.sensitive_commands_hotkey_only = os.getenv(
            "SENSITIVE_COMMANDS_HOTKEY_ONLY", ""
        ).lower() in ("true", "1", "yes")

        # Logging
        self.log_level = os.getenv("LOG_LEVEL", self.log_level)
        self.log_file = os.getenv("LOG_FILE", self.log_file)

    def validate(self) -> List[str]:
        """Validate configuration and return list of issues."""
        issues = []

        # Check required API keys
        if self.ai.use_openai and not self.api_keys.openai_api_key:
            issues.append("OpenAI API key required when USE_OPENAI=true")

        if self.api_keys.weather_api_key:
            # Could validate weather API key format here
            pass

        if self.api_keys.news_api_key:
            # Could validate news API key format here
            pass

        # Check audio settings
        if not 0.0 <= self.audio.sensitivity <= 1.0:
            issues.append("Audio sensitivity must be between 0.0 and 1.0")

        if self.audio.timeout_seconds < 1:
            issues.append("Audio timeout must be at least 1 second")

        # Check media settings
        if not 0 <= self.media.default_volume <= 100:
            issues.append("Default volume must be between 0 and 100")

        # Check privacy settings
        if self.privacy.data_retention_days < 1:
            issues.append("Data retention days must be at least 1")

        return issues


def setup_logging(config: Config) -> logging.Logger:
    """Setup logging configuration for JARVIS."""
    logger = logging.getLogger("jarvis")
    logger.setLevel(getattr(logging, config.log_level.upper()))

    # Clear existing handlers
    logger.handlers.clear()

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler
    try:
        log_file = Path(config.log_file)
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(getattr(logging, config.log_level.upper()))
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        logger.warning(f"Could not create log file: {e}")

    return logger


def get_config_directory() -> Path:
    """Get platform-specific configuration directory."""
    system = platform.system().lower()

    if system == "windows":
        config_dir = Path(os.environ.get("APPDATA", "")) / "JARVIS"
    elif system == "darwin":
        config_dir = Path.home() / "Library" / "Application Support" / "JARVIS"
    else:  # Linux and others
        config_dir = Path.home() / ".config" / "jarvis"

    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_default_config_path() -> Path:
    """Get default configuration file path."""
    config_dir = get_config_directory()
    return config_dir / "config.yaml"


def ensure_config_exists() -> Path:
    """Ensure configuration file exists, create from defaults if not."""
    config_path = get_default_config_path()

    if not config_path.exists():
        # Create default configuration
        default_config = Config()
        default_config.load_environment_variables()
        default_config.save_to_file(str(config_path))

        print(f"Created default configuration at: {config_path}")

    return config_path


# Platform-specific imports and utilities
def get_platform_info() -> Dict[str, Any]:
    """Get platform-specific information."""
    return {
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
    }


def check_dependencies() -> Dict[str, bool]:
    """Check for required dependencies."""
    deps = {}

    try:
        import speech_recognition
        deps["speech_recognition"] = True
    except ImportError:
        deps["speech_recognition"] = False

    try:
        import pyttsx3
        deps["pyttsx3"] = True
    except ImportError:
        deps["pyttsx3"] = False

    try:
        import pyaudio
        deps["pyaudio"] = True
    except ImportError:
        deps["pyaudio"] = False

    try:
        import openai
        deps["openai"] = True
    except ImportError:
        deps["openai"] = False

    try:
        import yaml
        deps["yaml"] = True
    except ImportError:
        deps["yaml"] = False

    try:
        import selenium
        deps["selenium"] = True
    except ImportError:
        deps["selenium"] = False

    try:
        import requests
        deps["requests"] = True
    except ImportError:
        deps["requests"] = False

    return deps
