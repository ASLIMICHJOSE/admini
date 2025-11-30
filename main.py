#!/usr/bin/env python3
"""
JARVIS Voice Assistant - Main Entry Point

A fully functional AI-based voice assistant designed to automate daily computer tasks
and provide intelligent responses through speech.

Author: JARVIS Team
License: MIT
"""

import argparse
import asyncio
import logging
import os
import signal
import sys
import threading
from pathlib import Path
from typing import Optional

from config import Config, setup_logging
from jarvis.core.speech_engine import SpeechEngine
from jarvis.core.nlp_processor import NLPProcessor
from jarvis.core.command_dispatcher import CommandDispatcher
from jarvis.core.event_loop import EventLoop
from jarvis.utils.error_handler import ErrorHandler


class JARVIS:
    """Main JARVIS application orchestrator."""

    def __init__(self, config_path: Optional[str] = None):
        """Initialize JARVIS with configuration."""
        self.config = Config.load_from_file(config_path) if config_path else Config()
        self.logger = setup_logging(self.config)
        self.error_handler = ErrorHandler(self.logger)

        # Core components (initialized later)
        self.speech_engine: Optional[SpeechEngine] = None
        self.nlp_processor: Optional[NLPProcessor] = None
        self.command_dispatcher: Optional[CommandDispatcher] = None
        self.event_loop: Optional[EventLoop] = None

        # Application state
        self.running = False
        self.shutdown_event = threading.Event()

        # Setup signal handlers
        self._setup_signal_handlers()

    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            self.logger.info(f"Received signal {signum}. Initiating graceful shutdown...")
            self.shutdown_gracefully()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def check_dependencies(self) -> bool:
        """Verify required dependencies and APIs are available."""
        self.logger.info("Checking dependencies...")

        try:
            # Check core dependencies
            import speech_recognition
            import pyttsx3
            import openai
            self.logger.debug("Core dependencies: OK")
        except ImportError as e:
            self.logger.error(f"Missing core dependency: {e}")
            return False

        # Check microphone access
        try:
            sr = speech_recognition.Recognizer()
            with speech_recognition.Microphone() as source:
                self.logger.debug("Microphone access: OK")
        except Exception as e:
            self.logger.error(f"Microphone access failed: {e}")
            return False

        # Check OpenAI API key if enabled
        if self.config.ai.use_openai and not self.config.api_keys.openai_api_key:
            self.logger.error("OpenAI API key required when USE_OPENAI=True")
            return False

        self.logger.info("All dependencies verified successfully")
        return True

    def initialize_services(self) -> bool:
        """Initialize all core services in the correct order."""
        try:
            self.logger.info("Initializing JARVIS services...")

            # Initialize speech engine (core audio functionality)
            self.speech_engine = SpeechEngine(self.config, self.logger)
            if not self.speech_engine.initialize():
                return False

            # Initialize NLP processor (command understanding)
            self.nlp_processor = NLPProcessor(self.config, self.logger)
            if not self.nlp_processor.initialize():
                return False

            # Initialize command dispatcher (routes commands to handlers)
            self.command_dispatcher = CommandDispatcher(self.config, self.logger)
            if not self.command_dispatcher.initialize():
                return False

            # Initialize event loop (main application loop)
            self.event_loop = EventLoop(
                self.config,
                self.logger,
                self.speech_engine,
                self.nlp_processor,
                self.command_dispatcher
            )
            if not self.event_loop.initialize():
                return False

            self.logger.info("All services initialized successfully")
            return True

        except Exception as e:
            self.logger.error(f"Failed to initialize services: {e}")
            return False

    def run(self, daemon_mode: bool = False) -> int:
        """Run the JARVIS application."""
        self.logger.info("Starting JARVIS Voice Assistant...")

        if not self.check_dependencies():
            self.logger.error("Dependency check failed. Exiting.")
            return 1

        if not self.initialize_services():
            self.logger.error("Service initialization failed. Exiting.")
            return 1

        self.running = True

        try:
            # Startup message
            if self.config.audio.wake_word_enabled:
                self.speech_engine.speak("JARVIS online and listening for commands")
            else:
                self.speech_engine.speak("JARVIS online. Press Ctrl+Space to activate")

            # Run the main event loop
            if daemon_mode:
                self.logger.info("Running in daemon mode")
                return self.event_loop.run_daemon()
            else:
                self.logger.info("Running in interactive mode")
                return self.event_loop.run()

        except KeyboardInterrupt:
            self.logger.info("Keyboard interrupt received")
        except Exception as e:
            self.logger.error(f"Unexpected error in main loop: {e}")
            return 1
        finally:
            self.shutdown_gracefully()

        return 0

    def shutdown_gracefully(self):
        """Perform graceful shutdown of all services."""
        if not self.running:
            return

        self.logger.info("Shutting down JARVIS gracefully...")
        self.running = False

        # Signal all threads to stop
        self.shutdown_event.set()

        try:
            # Shutdown services in reverse order
            if self.event_loop:
                self.event_loop.shutdown()

            if self.command_dispatcher:
                self.command_dispatcher.shutdown()

            if self.nlp_processor:
                self.nlp_processor.shutdown()

            if self.speech_engine:
                self.speech_engine.shutdown()

            self.logger.info("JARVIS shutdown complete")

        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")

    def test_configuration(self) -> bool:
        """Test the current configuration and hardware."""
        self.logger.info("Running configuration test...")

        try:
            # Test audio devices
            if not self.speech_engine or not self.speech_engine.test_microphone():
                print("❌ Microphone test failed")
                return False
            print("✅ Microphone test passed")

            # Test text-to-speech
            if not self.speech_engine or not self.speech_engine.test_speakers():
                print("❌ Speaker test failed")
                return False
            print("✅ Speaker test passed")

            # Test OpenAI connection
            if self.config.ai.use_openai:
                if not self.nlp_processor or not self.nlp_processor.test_openai_connection():
                    print("❌ OpenAI connection test failed")
                    return False
                print("✅ OpenAI connection test passed")

            # Test command dispatcher
            if not self.command_dispatcher or not self.command_dispatcher.test_handlers():
                print("❌ Command handlers test failed")
                return False
            print("✅ Command handlers test passed")

            print("🎉 All configuration tests passed!")
            return True

        except Exception as e:
            print(f"❌ Configuration test failed: {e}")
            return False


def create_argument_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser."""
    parser = argparse.ArgumentParser(
        description="JARVIS Voice Assistant - Your AI Personal Assistant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                    # Start JARVIS in interactive mode
  python main.py --daemon          # Start JARVIS in daemon mode
  python main.py --config custom.yaml  # Use custom configuration
  python main.py --test            # Test configuration and exit
        """
    )

    parser.add_argument(
        "--config", "-c",
        type=str,
        help="Path to configuration file (YAML)"
    )

    parser.add_argument(
        "--daemon", "-d",
        action="store_true",
        help="Run JARVIS in daemon mode (background)"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging (DEBUG level)"
    )

    parser.add_argument(
        "--test", "-t",
        action="store_true",
        help="Test configuration and hardware, then exit"
    )

    parser.add_argument(
        "--version",
        action="version",
        version="JARVIS Voice Assistant 1.0.0"
    )

    return parser


def main() -> int:
    """Main entry point for the JARVIS application."""
    parser = create_argument_parser()
    args = parser.parse_args()

    try:
        # Initialize JARVIS
        jarvis = JARVIS(config_path=args.config)

        # Override log level if verbose flag is set
        if args.verbose:
            jarvis.logger.setLevel(logging.DEBUG)
            logging.getLogger().setLevel(logging.DEBUG)

        # Run configuration test if requested
        if args.test:
            success = jarvis.test_configuration()
            return 0 if success else 1

        # Run the main application
        return jarvis.run(daemon_mode=args.daemon)

    except KeyboardInterrupt:
        print("\nJARVIS stopped by user")
        return 0
    except Exception as e:
        print(f"Fatal error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
