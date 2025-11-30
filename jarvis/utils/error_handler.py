#!/usr/bin/env python3
"""
JARVIS Error Handler

Centralized error handling and recovery mechanisms.
"""

import logging
import traceback
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
from dataclasses import dataclass, field


class ErrorSeverity(Enum):
    """Error severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Error categories for classification."""
    AUDIO = "audio"
    NETWORK = "network"
    FILE_SYSTEM = "file_system"
    API = "api"
    SYSTEM = "system"
    CONFIGURATION = "configuration"
    USER_INPUT = "user_input"
    PERMISSION = "permission"
    HARDWARE = "hardware"
    DEPENDENCY = "dependency"


@dataclass
class ErrorReport:
    """Detailed error report."""
    error_id: str
    timestamp: datetime
    category: ErrorCategory
    severity: ErrorSeverity
    message: str
    exception_type: str
    traceback_text: str
    context: Dict[str, Any] = field(default_factory=dict)
    user_message: Optional[str] = None
    recovery_suggested: bool = False
    recovered: bool = False


class ErrorRecoveryStrategy:
    """Error recovery strategy."""

    def __init__(self, name: str, can_retry: bool = True, max_retries: int = 3):
        self.name = name
        self.can_retry = can_retry
        self.max_retries = max_retries
        self.current_retries = 0

    def execute(self, error: Exception, context: Dict[str, Any]) -> bool:
        """Execute recovery strategy. Return True if successful."""
        return False

    def can_retry_again(self) -> bool:
        """Check if we can retry this recovery strategy."""
        return self.can_retry and self.current_retries < self.max_retries

    def increment_retry(self):
        """Increment retry count."""
        self.current_retries += 1

    def reset(self):
        """Reset retry count."""
        self.current_retries = 0


class AudioErrorRecovery(ErrorRecoveryStrategy):
    """Recovery strategy for audio-related errors."""

    def execute(self, error: Exception, context: Dict[str, Any]) -> bool:
        """Handle audio errors."""
        try:
            error_str = str(error).lower()
            
            if "microphone" in error_str or "no audio input" in error_str:
                # Try to reset microphone
                if "speech_engine" in context:
                    speech_engine = context["speech_engine"]
                    try:
                        speech_engine.initialize()
                        return True
                    except Exception:
                        pass
                
                # Suggest user actions
                context["user_suggestion"] = "Check microphone connection and permissions"
                
            elif "speaker" in error_str or "audio output" in error_str:
                # Try to reset audio output
                if "speech_engine" in context:
                    speech_engine = context["speech_engine"]
                    try:
                        if hasattr(speech_engine, 'tts_engine') and speech_engine.tts_engine:
                            speech_engine._configure_tts()
                            return True
                    except Exception:
                        pass
                
                context["user_suggestion"] = "Check speaker connection and volume settings"
                
            return False

        except Exception as e:
            context["recovery_error"] = str(e)
            return False


class NetworkErrorRecovery(ErrorRecoveryStrategy):
    """Recovery strategy for network-related errors."""

    def execute(self, error: Exception, context: Dict[str, Any]) -> bool:
        """Handle network errors."""
        try:
            error_str = str(error).lower()
            
            if "timeout" in error_str or "connection" in error_str:
                # Check if we have internet connectivity
                try:
                    import requests
                    response = requests.get("https://www.google.com", timeout=5)
                    if response.status_code == 200:
                        # Internet is working, might be API-specific issue
                        context["user_suggestion"] = "API service may be temporarily unavailable"
                        return False
                except Exception:
                    pass
                
                # Try using offline/fallback mode
                if "config" in context:
                    config = context["config"]
                    if hasattr(config.ai, 'offline_fallback') and config.ai.offline_fallback:
                        context["fallback_mode"] = True
                        context["user_suggestion"] = "Using offline mode until network is available"
                        return True
                
            elif "rate limit" in error_str or "quota" in error_str:
                # Suggest waiting or reducing usage
                context["user_suggestion"] = "API rate limit reached, please try again later"
                context["retry_after"] = 60  # Suggest 60 second delay
                
            return False

        except Exception as e:
            context["recovery_error"] = str(e)
            return False


class APIErrorRecovery(ErrorRecoveryStrategy):
    """Recovery strategy for API-related errors."""

    def execute(self, error: Exception, context: Dict[str, Any]) -> bool:
        """Handle API errors."""
        try:
            error_str = str(error).lower()
            
            if "authentication" in error_str or "unauthorized" in error_str:
                context["user_suggestion"] = "Check API key configuration and permissions"
                return False
                
            elif "not found" in error_str or "invalid request" in error_str:
                context["user_suggestion"] = "API request format may be incorrect"
                return False
                
            elif "service unavailable" in error_str:
                # Try fallback service if available
                context["fallback_service"] = True
                context["user_suggestion"] = "Primary API unavailable, trying alternative"
                return True
                
            return False

        except Exception as e:
            context["recovery_error"] = str(e)
            return False


class ErrorHandler:
    """Centralized error handling with recovery strategies."""

    def __init__(self, logger: logging.Logger):
        self.logger = logger
        
        # Error tracking
        self.error_reports: List[ErrorReport] = []
        self.max_error_history = 100
        
        # Recovery strategies
        self.recovery_strategies: Dict[ErrorCategory, List[ErrorRecoveryStrategy]] = {
            ErrorCategory.AUDIO: [AudioErrorRecovery("audio_reset")],
            ErrorCategory.NETWORK: [NetworkErrorRecovery("network_fallback")],
            ErrorCategory.API: [APIErrorRecovery("api_fallback"), NetworkErrorRecovery("network_fallback")],
            ErrorCategory.FILE_SYSTEM: [ErrorRecoveryStrategy("file_check", can_retry=False)],
            ErrorCategory.SYSTEM: [ErrorRecoveryStrategy("system_restart", can_retry=False)],
            ErrorCategory.CONFIGURATION: [ErrorRecoveryStrategy("config_fix", can_retry=False)],
            ErrorCategory.USER_INPUT: [ErrorRecoveryStrategy("input_correction", can_retry=True)],
            ErrorCategory.PERMISSION: [ErrorRecoveryStrategy("permission_request", can_retry=False)],
            ErrorCategory.HARDWARE: [ErrorRecoveryStrategy("hardware_check", can_retry=False)],
            ErrorCategory.DEPENDENCY: [ErrorRecoveryStrategy("dependency_check", can_retry=False)]
        }
        
        # Error statistics
        self.error_counts: Dict[str, int] = {}
        self.error_recovery_counts: Dict[str, int] = {}

    def handle_error(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        category: Optional[ErrorCategory] = None,
        user_message: Optional[str] = None
    ) -> ErrorReport:
        """Handle an error with recovery attempts."""
        
        # Create error report
        error_report = self._create_error_report(error, context, severity, category, user_message)
        
        # Log the error
        self._log_error(error_report)
        
        # Attempt recovery
        if category:
            recovery_result = self._attempt_recovery(error, category, context or {})
            error_report.recovery_suggested = True
            error_report.recovered = recovery_result
        
        # Track statistics
        self._update_error_statistics(error_report)
        
        # Store error report
        self._store_error_report(error_report)
        
        return error_report

    def _create_error_report(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]],
        severity: ErrorSeverity,
        category: Optional[ErrorCategory],
        user_message: Optional[str]
    ) -> ErrorReport:
        """Create a detailed error report."""
        
        # Generate error ID
        error_id = f"ERR_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{id(error) % 10000:04d}"
        
        # Auto-categorize error if not provided
        if not category:
            category = self._categorize_error(error)
        
        # Generate user-friendly message if not provided
        if not user_message:
            user_message = self._generate_user_message(error, category)
        
        return ErrorReport(
            error_id=error_id,
            timestamp=datetime.now(),
            category=category,
            severity=severity,
            message=str(error),
            exception_type=type(error).__name__,
            traceback_text=traceback.format_exc(),
            context=context or {},
            user_message=user_message
        )

    def _categorize_error(self, error: Exception) -> ErrorCategory:
        """Automatically categorize an error."""
        error_str = str(error).lower()
        error_type = type(error).__name__.lower()
        
        # Audio-related errors
        if any(term in error_str for term in ["microphone", "speaker", "audio", "recognition", "tts", "pyaudio"]):
            return ErrorCategory.AUDIO
        
        # Network-related errors
        if any(term in error_str for term in ["network", "connection", "timeout", "dns", "wifi", "internet"]):
            return ErrorCategory.NETWORK
        
        # API-related errors
        if any(term in error_str for term in ["api", "openai", "weather", "news", "wikipedia", "request"]):
            return ErrorCategory.API
        
        # File system errors
        if any(term in error_str for term in ["file", "directory", "path", "permission denied", "not found", "disk"]):
            return ErrorCategory.FILE_SYSTEM
        
        # Permission errors
        if any(term in error_str for term in ["permission", "access denied", "unauthorized", "forbidden"]):
            return ErrorCategory.PERMISSION
        
        # System errors
        if any(term in error_str for term in ["system", "process", "memory", "cpu", "operating system"]):
            return ErrorCategory.SYSTEM
        
        # Configuration errors
        if any(term in error_str for term in ["config", "setting", "api key", "yaml", "environment"]):
            return ErrorCategory.CONFIGURATION
        
        # User input errors
        if any(term in error_str for term in ["input", "command", "speech", "recognition", "parse"]):
            return ErrorCategory.USER_INPUT
        
        # Default to system errors
        return ErrorCategory.SYSTEM

    def _generate_user_message(self, error: Exception, category: ErrorCategory) -> str:
        """Generate a user-friendly error message."""
        
        if category == ErrorCategory.AUDIO:
            return "I'm having trouble with audio. Please check your microphone and speakers."
        
        elif category == ErrorCategory.NETWORK:
            return "I can't connect to the internet. Please check your network connection."
        
        elif category == ErrorCategory.API:
            return "One of my services is temporarily unavailable. Please try again in a moment."
        
        elif category == ErrorCategory.FILE_SYSTEM:
            return "I'm having trouble accessing files. Please check your file permissions."
        
        elif category == ErrorCategory.PERMISSION:
            return "I don't have the necessary permissions to complete that task."
        
        elif category == ErrorCategory.SYSTEM:
            return "There's a system issue preventing me from completing that task."
        
        elif category == ErrorCategory.CONFIGURATION:
            return "There's an issue with my configuration. Please check your settings."
        
        elif category == ErrorCategory.USER_INPUT:
            return "I didn't understand that command. Could you please rephrase it?"
        
        else:
            return "Something went wrong. Please try again or check the logs for details."

    def _log_error(self, error_report: ErrorReport):
        """Log the error with appropriate level."""
        
        log_message = f"[{error_report.error_id}] {error_report.category.value.upper()}: {error_report.message}"
        
        if error_report.severity == ErrorSeverity.CRITICAL:
            self.logger.critical(f"{log_message}\n{error_report.traceback_text}")
        elif error_report.severity == ErrorSeverity.HIGH:
            self.logger.error(f"{log_message}\n{error_report.traceback_text}")
        elif error_report.severity == ErrorSeverity.MEDIUM:
            self.logger.warning(f"{log_message}\n{error_report.context}")
        else:
            self.logger.info(f"{log_message}")

    def _attempt_recovery(self, error: Exception, category: ErrorCategory, context: Dict[str, Any]) -> bool:
        """Attempt to recover from the error using available strategies."""
        
        strategies = self.recovery_strategies.get(category, [])
        
        for strategy in strategies:
            try:
                if strategy.can_retry_again():
                    strategy.increment_retry()
                    
                    self.logger.info(f"Attempting recovery: {strategy.name} (attempt {strategy.current_retries})")
                    
                    if strategy.execute(error, context):
                        self.logger.info(f"Recovery successful: {strategy.name}")
                        self.error_recovery_counts[strategy.name] = self.error_recovery_counts.get(strategy.name, 0) + 1
                        strategy.reset()
                        return True
                    else:
                        self.logger.warning(f"Recovery failed: {strategy.name}")
                        
            except Exception as recovery_error:
                self.logger.error(f"Recovery strategy error: {strategy.name} - {recovery_error}")
                context["recovery_error"] = str(recovery_error)
        
        # Suggest user actions based on context
        if "user_suggestion" in context:
            self.logger.info(f"User suggestion: {context['user_suggestion']}")
        
        return False

    def _update_error_statistics(self, error_report: ErrorReport):
        """Update error statistics."""
        error_key = f"{error_report.category.value}_{error_report.exception_type}"
        self.error_counts[error_key] = self.error_counts.get(error_key, 0) + 1

    def _store_error_report(self, error_report: ErrorReport):
        """Store error report in history."""
        self.error_reports.append(error_report)
        
        # Limit error history
        if len(self.error_reports) > self.max_error_history:
            self.error_reports = self.error_reports[-self.max_error_history:]

    def get_error_summary(self) -> Dict[str, Any]:
        """Get a summary of recent errors."""
        
        if not self.error_reports:
            return {
                "total_errors": 0,
                "recent_errors": [],
                "error_categories": {},
                "error_severities": {},
                "recovery_success_rate": 0.0
            }
        
        # Count categories and severities
        categories = {}
        severities = {}
        
        for report in self.error_reports:
            cat_key = report.category.value
            sev_key = report.severity.value
            
            categories[cat_key] = categories.get(cat_key, 0) + 1
            severities[sev_key] = severities.get(sev_key, 0) + 1
        
        # Calculate recovery success rate
        total_recovery_attempts = len([r for r in self.error_reports if r.recovery_suggested])
        successful_recoveries = len([r for r in self.error_reports if r.recovered])
        recovery_rate = successful_recoveries / max(1, total_recovery_attempts)
        
        # Get recent errors (last 10)
        recent_errors = self.error_reports[-10:]
        
        return {
            "total_errors": len(self.error_reports),
            "recent_errors": [
                {
                    "error_id": report.error_id,
                    "timestamp": report.timestamp.isoformat(),
                    "category": report.category.value,
                    "severity": report.severity.value,
                    "message": report.message,
                    "recovered": report.recovered
                }
                for report in recent_errors
            ],
            "error_categories": categories,
            "error_severities": severities,
            "recovery_success_rate": recovery_rate,
            "recovery_statistics": self.error_recovery_counts
        }

    def clear_error_history(self):
        """Clear error history."""
        self.error_reports.clear()
        self.error_counts.clear()
        self.error_recovery_counts.clear()
        self.logger.info("Error history cleared")

    def get_user_friendly_message(self, error: Exception) -> str:
        """Get a user-friendly message for an error."""
        category = self._categorize_error(error)
        return self._generate_user_message(error, category)

    def should_retry(self, error: Exception) -> bool:
        """Determine if an operation should be retried."""
        category = self._categorize_error(error)
        strategies = self.recovery_strategies.get(category, [])
        
        return any(strategy.can_retry_again() for strategy in strategies)

    def get_retry_delay(self, error: Exception, attempt: int) -> float:
        """Get suggested retry delay in seconds."""
        category = self._categorize_error(error)
        
        # Base delays by category
        base_delays = {
            ErrorCategory.NETWORK: 2.0,      # Network errors - short delay
            ErrorCategory.API: 1.0,           # API errors - very short delay
            ErrorCategory.AUDIO: 0.5,         # Audio errors - immediate
            ErrorCategory.SYSTEM: 5.0,         # System errors - longer delay
            ErrorCategory.FILE_SYSTEM: 1.0,    # File system errors - short delay
        }
        
        base_delay = base_delays.get(category, 2.0)
        
        # Exponential backoff
        return base_delay * (2 ** min(attempt - 1, 4))

    def log_warning(self, message: str, context: Optional[Dict[str, Any]] = None):
        """Log a warning with context."""
        if context:
            self.logger.warning(f"{message} | Context: {context}")
        else:
            self.logger.warning(message)

    def log_info(self, message: str, context: Optional[Dict[str, Any]] = None):
        """Log info with context."""
        if context:
            self.logger.info(f"{message} | Context: {context}")
        else:
            self.logger.info(message)

    def log_debug(self, message: str, context: Optional[Dict[str, Any]] = None):
        """Log debug message with context."""
        if context:
            self.logger.debug(f"{message} | Context: {context}")
        else:
            self.logger.debug(message)

    def shutdown(self):
        """Cleanup error handler resources."""
        self.logger.info("Shutting down error handler...")
        
        # Log final error summary
        summary = self.get_error_summary()
        self.logger.info(f"Final error summary: {summary['total_errors']} errors, "
                        f"recovery success rate: {summary['recovery_success_rate']:.2%}")
        
        self.logger.info("Error handler shutdown complete")
