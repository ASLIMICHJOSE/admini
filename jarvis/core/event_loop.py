#!/usr/bin/env python3
"""
JARVIS Event Loop

Main application event loop that coordinates wake word detection,
hotkey listening, and command processing.
"""

import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Callable
import queue

try:
    import keyboard
except ImportError:
    keyboard = None

try:
    import pynput
    from pynput import keyboard as pynput_keyboard
except ImportError:
    pynput = None

from config import Config
from jarvis.core.speech_engine import SpeechEngine
from jarvis.core.nlp_processor import NLPProcessor, CommandResult
from jarvis.core.command_dispatcher import CommandDispatcher, ExecutionResult


@dataclass
class CommandQueue:
    """Thread-safe command queue."""
    queue: queue.Queue
    timestamp: datetime
    source: str  # "wake_word" or "hotkey"


class EventLoop:
    """Main JARVIS application event loop."""

    def __init__(
        self,
        config: Config,
        logger: logging.Logger,
        speech_engine: SpeechEngine,
        nlp_processor: NLPProcessor,
        command_dispatcher: CommandDispatcher
    ):
        self.config = config
        self.logger = logger
        self.speech_engine = speech_engine
        self.nlp_processor = nlp_processor
        self.command_dispatcher = command_dispatcher

        # Threading and state
        self.running = False
        self.stop_event = threading.Event()

        # Command queue and processing
        self.command_queue = queue.Queue(maxsize=100)
        self.processing_lock = threading.Lock()

        # Wake word detection
        self.wake_word_thread: Optional[threading.Thread] = None

        # Hotkey listener
        self.hotkey_thread: Optional[threading.Thread] = None
        self.hotkey_active = False

        # Statistics
        self.commands_processed = 0
        self.commands_failed = 0
        self.session_start = datetime.now()

        # Audio state
        self.listening_for_wake_word = False
        self.processing_command = False

    def initialize(self) -> bool:
        """Initialize the event loop."""
        try:
            self.logger.info("Initializing event loop...")

            # Check dependencies
            if self.config.audio.wake_word_enabled:
                if not self._check_wake_word_dependencies():
                    self.logger.warning("Wake word dependencies not available, disabling wake word")
                    self.config.audio.wake_word_enabled = False
                else:
                    self.logger.info("Wake word detection enabled")

            if not self._check_hotkey_dependencies():
                self.logger.warning("Hotkey dependencies not available")
                return False
            else:
                self.logger.info("Hotkey activation enabled")

            self.logger.info("Event loop initialized successfully")
            return True

        except Exception as e:
            self.logger.error(f"Failed to initialize event loop: {e}")
            return False

    def _check_wake_word_dependencies(self) -> bool:
        """Check if wake word dependencies are available."""
        if not self.speech_engine:
            return False

        return True

    def _check_hotkey_dependencies(self) -> bool:
        """Check if hotkey dependencies are available."""
        return keyboard is not None or pynput is not None

    def run(self) -> int:
        """Run the event loop in interactive mode."""
        try:
            self.logger.info("Starting JARVIS event loop...")
            
            self.running = True
            
            # Start background threads
            self._start_background_threads()

            # Main processing loop
            return self._main_processing_loop()

        except KeyboardInterrupt:
            self.logger.info("Event loop interrupted by user")
            return 0
        except Exception as e:
            self.logger.error(f"Error in event loop: {e}")
            return 1
        finally:
            self.shutdown()

    def run_daemon(self) -> int:
        """Run the event loop in daemon mode."""
        try:
            self.logger.info("Starting JARVIS in daemon mode...")
            
            self.running = True
            
            # Start background threads
            self._start_background_threads()

            # Daemon mode - just process commands as they come
            return self._daemon_processing_loop()

        except Exception as e:
            self.logger.error(f"Error in daemon mode: {e}")
            return 1
        finally:
            self.shutdown()

    def _start_background_threads(self):
        """Start wake word and hotkey detection threads."""
        # Start wake word detection if enabled
        if self.config.audio.wake_word_enabled:
            self.listening_for_wake_word = True
            self.wake_word_thread = threading.Thread(
                target=self._wake_word_detection_loop,
                name="WakeWordDetector",
                daemon=True
            )
            self.wake_word_thread.start()
            self.logger.info("Wake word detection started")

        # Start hotkey listener
        self.hotkey_thread = threading.Thread(
            target=self._hotkey_listener_loop,
            name="HotkeyListener",
            daemon=True
        )
        self.hotkey_thread.start()
        self.logger.info("Hotkey listener started")

    def _main_processing_loop(self) -> int:
        """Main event processing loop for interactive mode."""
        self.logger.info("Starting main processing loop...")

        while self.running and not self.stop_event.is_set():
            try:
                # Process commands from queue
                try:
                    command_queue = self.command_queue.get(timeout=1.0)
                    
                    # Process the command
                    result = self._process_command(command_queue)
                    
                    # Provide feedback
                    self._provide_command_feedback(result)
                    
                    self.command_queue.task_done()

                except queue.Empty:
                    # No commands to process, continue
                    continue

            except Exception as e:
                self.logger.error(f"Error in main processing loop: {e}")

        return 0

    def _daemon_processing_loop(self) -> int:
        """Daemon mode processing loop."""
        self.logger.info("Starting daemon processing loop...")

        while self.running and not self.stop_event.is_set():
            try:
                # Process commands from queue
                try:
                    command_queue = self.command_queue.get(timeout=1.0)
                    
                    # Process the command
                    result = self._process_command(command_queue)
                    
                    # Log the result
                    self.logger.info(f"Command processed: {result.success} - {result.message}")
                    
                    self.command_queue.task_done()

                except queue.Empty:
                    # No commands to process, continue
                    continue

            except Exception as e:
                self.logger.error(f"Error in daemon processing loop: {e}")

        return 0

    def _wake_word_detection_loop(self):
        """Background thread for wake word detection."""
        self.logger.info("Wake word detection loop started")

        while self.running and not self.stop_event.is_set() and self.listening_for_wake_word:
            try:
                if self.config.audio.wake_word_enabled and not self.processing_command:
                    # Listen for wake word
                    command = self.speech_engine.recognize_speech(timeout=2)
                    
                    if command and self._is_wake_word(command):
                        self.logger.info("Wake word detected")
                        
                        # Give user feedback
                        self.speech_engine.speak("Yes? I'm listening")
                        
                        # Listen for actual command
                        full_command = self.speech_engine.recognize_speech(timeout=10)
                        
                        if full_command:
                            self.logger.info(f"Command received: {full_command}")
                            
                            # Add to command queue
                            command_queue = CommandQueue(
                                queue=queue.Queue(maxsize=1),
                                timestamp=datetime.now(),
                                source="wake_word"
                            )
                            command_queue.queue.put(full_command)
                            
                            try:
                                self.command_queue.put(command_queue, timeout=1)
                            except queue.Full:
                                self.logger.warning("Command queue is full, dropping command")
                                self.speech_engine.speak("I'm busy right now, please try again")

                time.sleep(0.1)  # Small delay to prevent high CPU usage

            except Exception as e:
                self.logger.error(f"Error in wake word detection: {e}")
                time.sleep(1)  # Wait before retrying

        self.logger.info("Wake word detection loop stopped")

    def _hotkey_listener_loop(self):
        """Background thread for hotkey detection."""
        self.logger.info("Hotkey listener loop started")

        try:
            # Setup hotkey based on available library
            if keyboard:
                self._setup_keyboard_hotkey()
            elif pynput:
                self._setup_pynput_hotkey()
            else:
                self.logger.error("No hotkey library available")
                return

            # Keep thread alive
            while self.running and not self.stop_event.is_set():
                time.sleep(0.1)

        except Exception as e:
            self.logger.error(f"Error in hotkey listener: {e}")

        self.logger.info("Hotkey listener loop stopped")

    def _setup_keyboard_hotkey(self):
        """Setup hotkey using keyboard library."""
        def on_hotkey_press():
            if not self.processing_command:
                self._handle_hotkey_activation()

        try:
            # Parse hotkey combination
            hotkey_parts = self.config.audio.hotkey_combination.split('+')
            hotkey_string = '+'.join(part.strip().lower() for part in hotkey_parts)
            
            keyboard.add_hotkey(hotkey_string, on_hotkey_press)
            self.logger.info(f"Hotkey registered: {hotkey_string}")
            
            # Start keyboard listener
            keyboard.wait()  # This blocks until the program exits

        except Exception as e:
            self.logger.error(f"Failed to setup keyboard hotkey: {e}")

    def _setup_pynput_hotkey(self):
        """Setup hotkey using pynput library."""
        def on_press(key):
            try:
                # Check if our hotkey combination is pressed
                # This is simplified - would need proper combination detection
                if hasattr(key, 'char') and key.char == ' ' and keyboard.is_pressed('ctrl'):
                    if not self.processing_command:
                        self._handle_hotkey_activation()
            except AttributeError:
                # Special key
                pass

        try:
            listener = pynput_keyboard.Listener(on_press=on_press)
            listener.start()
            self.logger.info("Pynput hotkey listener started")
            
        except Exception as e:
            self.logger.error(f"Failed to setup pynput hotkey: {e}")

    def _handle_hotkey_activation(self):
        """Handle hotkey activation."""
        self.logger.info("Hotkey activated")
        self.hotkey_active = True

        try:
            # Listen for command
            command = self.speech_engine.recognize_speech(timeout=15)
            
            if command:
                self.logger.info(f"Hotkey command received: {command}")
                
                # Add to command queue
                command_queue = CommandQueue(
                    queue=queue.Queue(maxsize=1),
                    timestamp=datetime.now(),
                    source="hotkey"
                )
                command_queue.queue.put(command)
                
                try:
                    self.command_queue.put(command_queue, timeout=1)
                except queue.Full:
                    self.logger.warning("Command queue is full, dropping command")
                    self.speech_engine.speak("I'm busy right now, please try again")

        except Exception as e:
            self.logger.error(f"Error handling hotkey activation: {e}")
        finally:
            self.hotkey_active = False

    def _is_wake_word(self, text: str) -> bool:
        """Check if text contains wake word."""
        if not text:
            return False

        # Simple wake word detection
        text_lower = text.lower().strip()
        wake_word_lower = self.config.audio.wake_word.lower()
        
        return wake_word_lower in text_lower or text_lower in wake_word_lower

    def _process_command(self, command_queue: CommandQueue) -> ExecutionResult:
        """Process a command from the queue."""
        try:
            # Get command text from queue
            command_text = command_queue.queue.get(timeout=1)
            
            self.processing_command = True
            
            self.logger.info(f"Processing command from {command_queue.source}: {command_text}")
            
            # Process command with NLP
            command_result = self.nlp_processor.process_command(command_text)
            
            if not command_result:
                return ExecutionResult(
                    success=False,
                    message="Could not understand command",
                    error="NLP processing failed"
                )
            
            # Check if sensitive command and source is wake word
            if command_result.requires_confirmation and command_queue.source == "wake_word":
                if self.config.privacy.sensitive_commands_hotkey_only:
                    return ExecutionResult(
                        success=False,
                        message="This command requires hotkey activation (Ctrl+Space)",
                        error="Sensitive command from wake word"
                    )
            
            # Dispatch command
            result = self.command_dispatcher.dispatch_command(command_result)
            
            # Update statistics
            self.commands_processed += 1
            if not result.success:
                self.commands_failed += 1
            
            return result

        except Exception as e:
            self.logger.error(f"Error processing command: {e}")
            self.commands_failed += 1
            return ExecutionResult(
                success=False,
                message=f"Error processing command: {str(e)}",
                error=str(e)
            )
        finally:
            self.processing_command = False

    def _provide_command_feedback(self, result: ExecutionResult):
        """Provide feedback to user based on command result."""
        if result.success:
            self.speech_engine.speak(result.message)
        else:
            if "requires confirmation" in result.error.lower():
                # Special handling for confirmation required
                self.speech_engine.speak("Please confirm by pressing Ctrl+Space and saying 'confirm'")
            else:
                # Error feedback
                error_message = "I'm sorry, " + result.message.lower()
                self.speech_engine.speak(error_message)

    def stop_processing(self):
        """Stop all processing threads."""
        self.logger.info("Stopping event loop processing...")
        
        self.running = False
        self.stop_event.set()
        self.listening_for_wake_word = False

        # Wait for threads to stop
        if self.wake_word_thread and self.wake_word_thread.is_alive():
            self.wake_word_thread.join(timeout=2)
            
        if self.hotkey_thread and self.hotkey_thread.is_alive():
            self.hotkey_thread.join(timeout=2)

        # Stop speech engine
        if self.speech_engine:
            self.speech_engine.stop_listening()

    def get_statistics(self) -> dict:
        """Get event loop statistics."""
        session_duration = datetime.now() - self.session_start
        success_rate = self.commands_processed / max(1, self.commands_processed + self.commands_failed)
        
        return {
            "session_duration_minutes": session_duration.total_seconds() / 60,
            "commands_processed": self.commands_processed,
            "commands_failed": self.commands_failed,
            "success_rate": success_rate,
            "wake_word_enabled": self.config.audio.wake_word_enabled,
            "hotkey_active": self.hotkey_active,
            "processing_command": self.processing_command,
            "queue_size": self.command_queue.qsize()
        }

    def shutdown(self):
        """Shutdown the event loop."""
        self.logger.info("Shutting down event loop...")
        
        self.stop_processing()
        
        # Clear command queue
        while not self.command_queue.empty():
            try:
                self.command_queue.get_nowait()
            except queue.Empty:
                break
        
        self.logger.info("Event loop shutdown complete")
