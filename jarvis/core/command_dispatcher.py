#!/usr/bin/env python3
"""
JARVIS Command Dispatcher

Routes parsed commands to appropriate handlers with validation,
error handling, and command history management.
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any

from jarvis.core.nlp_processor import CommandResult
from jarvis.commands.system_control import SystemControl
from jarvis.commands.web_automation import WebAutomation
from jarvis.commands.information import InformationProvider
from jarvis.commands.communication import CommunicationHandler
from jarvis.commands.entertainment import EntertainmentController
from jarvis.commands.personal import PersonalAssistant


@dataclass
class ExecutionResult:
    """Result of command execution."""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_time: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class CommandHistory:
    """Entry in command history."""
    command: CommandResult
    result: ExecutionResult
    timestamp: datetime = field(default_factory=datetime.now)


class CommandValidator:
    """Validates commands before execution."""

    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def validate_command(self, command: CommandResult) -> tuple[bool, Optional[str]]:
        """Validate a command for safety and permissions."""
        if command.confidence < 0.3:
            return False, "Command confidence too low"

        if command.intent == "unknown":
            return False, "Unknown command intent"

        # Validate specific intents
        if command.intent == "open_app":
            return self._validate_open_app(command)
        elif command.intent == "close_app":
            return self._validate_close_app(command)
        elif command.intent == "send_email":
            return self._validate_send_email(command)
        elif command.intent in ["shutdown_system", "restart_system"]:
            return self._validate_system_command(command)
        elif command.intent == "set_timer":
            return self._validate_timer_command(command)
        elif command.intent in ["search_web", "search_youtube", "search_wikipedia"]:
            return self._validate_search_command(command)
        else:
            return True, None

    def _validate_open_app(self, command: CommandResult) -> tuple[bool, Optional[str]]:
        """Validate application opening commands."""
        app_name = command.entities.get("app_name", "").strip()
        
        if not app_name:
            return False, "Application name required"

        # Basic security check - prevent opening dangerous apps
        dangerous_apps = ["regedit", "cmd", "powershell", "terminal", "taskmgr"]
        if app_name.lower() in [app.lower() for app in dangerous_apps]:
            return False, f"Cannot open {app_name} for security reasons"

        return True, None

    def _validate_close_app(self, command: CommandResult) -> tuple[bool, Optional[str]]:
        """Validate application closing commands."""
        app_name = command.entities.get("app_name", "").strip()
        
        if not app_name:
            return False, "Application name required"

        # Allow closing most apps (safer than opening)
        return True, None

    def _validate_send_email(self, command: CommandResult) -> tuple[bool, Optional[str]]:
        """Validate email sending commands."""
        recipient = command.entities.get("recipient", "").strip()
        message = command.entities.get("message", "").strip()

        if not recipient:
            return False, "Email recipient required"

        if not message:
            return False, "Email message required"

        # Basic email validation
        if "@" not in recipient or "." not in recipient.split("@")[-1]:
            return False, "Invalid email address"

        return True, None

    def _validate_system_command(self, command: CommandResult) -> tuple[bool, Optional[str]]:
        """Validate system commands."""
        # These always require confirmation
        if not command.requires_confirmation:
            return False, "System commands require confirmation"

        return True, None

    def _validate_timer_command(self, command: CommandResult) -> tuple[bool, Optional[str]]:
        """Validate timer commands."""
        time_value = command.entities.get("time_value")
        time_unit = command.entities.get("time_unit", "")

        if not time_value or not isinstance(time_value, (int, float)):
            return False, "Invalid time value"

        if time_value <= 0:
            return False, "Time must be positive"

        if "minute" in time_unit.lower():
            if time_value > 1440:  # 24 hours in minutes
                return False, "Timer cannot exceed 24 hours"
        elif "hour" in time_unit.lower():
            if time_value > 24:
                return False, "Timer cannot exceed 24 hours"

        return True, None

    def _validate_search_command(self, command: CommandResult) -> tuple[bool, Optional[str]]:
        """Validate search commands."""
        query = command.entities.get("query", "").strip()

        if not query:
            return False, "Search query required"

        # Basic content validation
        if len(query) > 1000:
            return False, "Search query too long"

        return True, None


class CommandDispatcher:
    """Main command dispatcher with handler management."""

    def __init__(self, config, logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.validator = CommandValidator(logger)

        # Command handlers
        self.system_control = None
        self.web_automation = None
        self.information_provider = None
        self.communication_handler = None
        self.entertainment_controller = None
        self.personal_assistant = None

        # Command history
        self.command_history: List[CommandHistory] = []
        self.max_history_size = 100

        # Execution statistics
        self.commands_executed = 0
        self.commands_failed = 0
        self.last_command_time: Optional[datetime] = None

        # Thread safety
        self.history_lock = threading.Lock()

        # Command timeout
        self.default_timeout = 30  # seconds

    def initialize(self) -> bool:
        """Initialize all command handlers."""
        try:
            self.logger.info("Initializing command dispatcher...")

            # Initialize command handlers
            self.system_control = SystemControl(self.config, self.logger)
            self.web_automation = WebAutomation(self.config, self.logger)
            self.information_provider = InformationProvider(self.config, self.logger)
            self.communication_handler = CommunicationHandler(self.config, self.logger)
            self.entertainment_controller = EntertainmentController(self.config, self.logger)
            self.personal_assistant = PersonalAssistant(self.config, self.logger)

            # Initialize each handler
            handlers = [
                self.system_control,
                self.web_automation,
                self.information_provider,
                self.communication_handler,
                self.entertainment_controller,
                self.personal_assistant
            ]

            for handler in handlers:
                if handler and not handler.initialize():
                    self.logger.error(f"Failed to initialize {handler.__class__.__name__}")
                    return False

            self.logger.info("Command dispatcher initialized successfully")
            return True

        except Exception as e:
            self.logger.error(f"Failed to initialize command dispatcher: {e}")
            return False

    def get_command_handlers(self) -> Dict[str, Callable]:
        """Get mapping of intents to handler functions."""
        return {
            "open_app": self.system_control.open_application if self.system_control else None,
            "close_app": self.system_control.close_application if self.system_control else None,
            "get_weather": self.information_provider.get_weather if self.information_provider else None,
            "get_news": self.information_provider.get_news if self.information_provider else None,
            "search_web": self.web_automation.search_google if self.web_automation else None,
            "search_youtube": self.web_automation.search_youtube if self.web_automation else None,
            "search_wikipedia": self.information_provider.get_wikipedia_summary if self.information_provider else None,
            "send_email": self.communication_handler.send_email if self.communication_handler else None,
            "play_music": self.entertainment_controller.play_music if self.entertainment_controller else None,
            "pause_resume_music": self.entertainment_controller.pause_resume_music if self.entertainment_controller else None,
            "next_track": self.entertainment_controller.next_track if self.entertainment_controller else None,
            "previous_track": self.entertainment_controller.previous_track if self.entertainment_controller else None,
            "set_reminder": self.personal_assistant.set_reminder if self.personal_assistant else None,
            "set_timer": self.personal_assistant.set_timer if self.personal_assistant else None,
            "get_time": self.information_provider.get_current_time if self.information_provider else None,
            "get_date": self.information_provider.get_current_date if self.information_provider else None,
            "shutdown_system": self.system_control.shutdown_system if self.system_control else None,
            "restart_system": self.system_control.restart_system if self.system_control else None,
            "get_system_info": self.system_control.get_system_info if self.system_control else None,
            "adjust_volume": self.system_control.set_volume if self.system_control else None,
            "general_query": self.information_provider.answer_general_question if self.information_provider else None,
        }

    def dispatch_command(self, command: CommandResult) -> ExecutionResult:
        """Dispatch a command to the appropriate handler."""
        start_time = time.time()

        try:
            self.logger.info(f"Dispatching command: {command.intent} - {command.raw_text}")

            # Validate command
            is_valid, error_message = self.validator.validate_command(command)
            if not is_valid:
                return ExecutionResult(
                    success=False,
                    message=f"Command validation failed: {error_message}",
                    error=error_message,
                    execution_time=time.time() - start_time
                )

            # Get handler
            handlers = self.get_command_handlers()
            handler = handlers.get(command.intent)

            if not handler:
                return ExecutionResult(
                    success=False,
                    message=f"No handler available for command: {command.intent}",
                    error=f"Unknown command intent: {command.intent}",
                    execution_time=time.time() - start_time
                )

            # Check for confirmation requirement
            if command.requires_confirmation:
                return ExecutionResult(
                    success=False,
                    message=f"Command '{command.intent}' requires confirmation. Please confirm to proceed.",
                    error="Confirmation required",
                    execution_time=time.time() - start_time,
                    data={"requires_confirmation": True}
                )

            # Execute command with timeout
            result = self._execute_with_timeout(handler, command, self.default_timeout)

            # Record command in history
            self._record_command(command, result)

            # Update statistics
            self.commands_executed += 1
            self.last_command_time = datetime.now()

            return result

        except Exception as e:
            self.logger.error(f"Error dispatching command: {e}")
            self.commands_failed += 1

            return ExecutionResult(
                success=False,
                message=f"Error executing command: {str(e)}",
                error=str(e),
                execution_time=time.time() - start_time
            )

    def _execute_with_timeout(self, handler: Callable, command: CommandResult, timeout: int) -> ExecutionResult:
        """Execute a handler function with timeout."""
        import concurrent.futures

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(handler, command)
                
                try:
                    # Wait for completion with timeout
                    result = future.result(timeout=timeout)
                    return result if isinstance(result, ExecutionResult) else ExecutionResult(
                        success=True,
                        message=str(result),
                        data={"result": result} if result else None
                    )
                except concurrent.futures.TimeoutError:
                    future.cancel()
                    return ExecutionResult(
                        success=False,
                        message=f"Command execution timed out after {timeout} seconds",
                        error="Command timeout"
                    )

        except Exception as e:
            return ExecutionResult(
                success=False,
                message=f"Handler execution error: {str(e)}",
                error=str(e)
            )

    def _record_command(self, command: CommandResult, result: ExecutionResult):
        """Record command in history."""
        with self.history_lock:
            history_entry = CommandHistory(command=command, result=result)
            self.command_history.append(history_entry)

            # Limit history size
            if len(self.command_history) > self.max_history_size:
                self.command_history = self.command_history[-self.max_history_size:]

    def get_command_history(self, limit: int = 10) -> List[CommandHistory]:
        """Get recent command history."""
        with self.history_lock:
            return self.command_history[-limit:] if limit else self.command_history.copy()

    def undo_last_command(self) -> ExecutionResult:
        """Undo the last successful command if possible."""
        with self.history_lock:
            if not self.command_history:
                return ExecutionResult(
                    success=False,
                    message="No commands to undo"
                )

            # Find last successful command
            for entry in reversed(self.command_history):
                if entry.result.success:
                    # Check if command is undoable
                    if entry.command.intent in ["open_app", "close_app", "play_music"]:
                        # Undo by reversing the action
                        undo_command = self._create_undo_command(entry.command)
                        if undo_command:
                            return self.dispatch_command(undo_command)

                    return ExecutionResult(
                        success=False,
                        message=f"Cannot undo command: {entry.command.intent}"
                    )

            return ExecutionResult(
                success=False,
                message="No successful commands to undo"
            )

    def _create_undo_command(self, original_command: CommandResult) -> Optional[CommandResult]:
        """Create an undo command for the given command."""
        if original_command.intent == "open_app":
            # Undo by closing the app
            return CommandResult(
                intent="close_app",
                entities=original_command.entities,
                confidence=original_command.confidence,
                requires_confirmation=False,
                raw_text=f"Close {original_command.entities.get('app_name', '')}",
                processing_method=original_command.processing_method,
                timestamp=datetime.now()
            )
        elif original_command.intent == "close_app":
            # Undo by opening the app
            return CommandResult(
                intent="open_app",
                entities=original_command.entities,
                confidence=original_command.confidence,
                requires_confirmation=False,
                raw_text=f"Open {original_command.entities.get('app_name', '')}",
                processing_method=original_command.processing_method,
                timestamp=datetime.now()
            )
        elif original_command.intent == "play_music":
            # Undo by pausing music
            return CommandResult(
                intent="pause_resume_music",
                entities={},
                confidence=original_command.confidence,
                requires_confirmation=False,
                raw_text="Pause music",
                processing_method=original_command.processing_method,
                timestamp=datetime.now()
            )

        return None

    def test_handlers(self) -> bool:
        """Test all command handlers."""
        self.logger.info("Testing command handlers...")

        handlers = [
            (self.system_control, "System Control"),
            (self.web_automation, "Web Automation"),
            (self.information_provider, "Information Provider"),
            (self.communication_handler, "Communication Handler"),
            (self.entertainment_controller, "Entertainment Controller"),
            (self.personal_assistant, "Personal Assistant")
        ]

        for handler, name in handlers:
            if handler and hasattr(handler, 'test'):
                try:
                    if handler.test():
                        self.logger.info(f"✅ {name} test passed")
                    else:
                        self.logger.error(f"❌ {name} test failed")
                        return False
                except Exception as e:
                    self.logger.error(f"❌ {name} test error: {e}")
                    return False
            else:
                self.logger.warning(f"⚠️  {name} has no test method")

        self.logger.info("All handler tests completed")
        return True

    def get_statistics(self) -> Dict[str, Any]:
        """Get dispatcher statistics."""
        with self.history_lock:
            recent_commands = [
                entry for entry in self.command_history
                if datetime.now() - entry.timestamp < timedelta(hours=1)
            ]

        return {
            "total_commands": self.commands_executed,
            "failed_commands": self.commands_failed,
            "success_rate": self.commands_executed / max(1, self.commands_executed + self.commands_failed),
            "commands_last_hour": len(recent_commands),
            "history_size": len(self.command_history),
            "last_command_time": self.last_command_time.isoformat() if self.last_command_time else None
        }

    def clear_history(self):
        """Clear command history."""
        with self.history_lock:
            self.command_history.clear()
        self.logger.info("Command history cleared")

    def shutdown(self):
        """Shutdown command dispatcher and all handlers."""
        self.logger.info("Shutting down command dispatcher...")

        # Shutdown all handlers
        handlers = [
            self.system_control,
            self.web_automation,
            self.information_provider,
            self.communication_handler,
            self.entertainment_controller,
            self.personal_assistant
        ]

        for handler in handlers:
            if handler and hasattr(handler, 'shutdown'):
                try:
                    handler.shutdown()
                except Exception as e:
                    self.logger.error(f"Error shutting down {handler.__class__.__name__}: {e}")

        # Clear history
        self.clear_history()

        self.logger.info("Command dispatcher shutdown complete")
