#!/usr/bin/env python3
"""
JARVIS Speech Engine

Handles speech recognition, text-to-speech, and audio device management.
Supports wake word detection, push-to-talk activation, and error handling.
"""

import logging
import os
import queue
import threading
import time
from typing import Optional, Callable, Any
from dataclasses import dataclass

try:
    import speech_recognition as sr
except ImportError:
    sr = None

try:
    import pyttsx3
except ImportError:
    pyttsx3 = None

try:
    import pyaudio
except ImportError:
    pyaudio = None

try:
    import sounddevice as sd
    import numpy as np
except ImportError:
    sd = None
    np = None

from config import AudioConfig


@dataclass
class AudioDevice:
    """Audio device information."""
    id: int
    name: str
    channels: int
    sample_rate: int
    is_input: bool
    is_output: bool


class WakeWordDetector:
    """Simple wake word detection using energy threshold."""

    def __init__(self, wake_word: str = "Hey JARVIS", sensitivity: float = 0.5):
        self.wake_word = wake_word.lower()
        self.sensitivity = sensitivity
        self.energy_threshold = 300
        self.dynamic_energy_threshold = True
        self.pause_threshold = 0.8

    def detect_wake_word(self, audio_data) -> bool:
        """Simple wake word detection based on audio energy."""
        if not hasattr(audio_data, 'get_energy'):
            return False

        # Adjust energy threshold if dynamic
        if self.dynamic_energy_threshold:
            self.energy_threshold = max(self.energy_threshold * 0.95, audio_data.get_energy() * 0.15)

        return audio_data.get_energy() > self.energy_threshold * (1 + self.sensitivity)


class SpeechEngine:
    """Main speech recognition and TTS engine."""

    def __init__(self, config: AudioConfig, logger: logging.Logger):
        self.config = config
        self.logger = logger

        # Audio components
        self.recognizer = None
        self.microphone = None
        self.tts_engine = None

        # Wake word detection
        self.wake_detector = None
        self.wake_word_active = False

        # Audio threading
        self.audio_queue = queue.Queue()
        self.audio_thread = None
        self.stop_audio = threading.Event()

        # Callback for speech detection
        self.on_speech_detected: Optional[Callable[[str], None]] = None

    def initialize(self) -> bool:
        """Initialize speech recognition and TTS components."""
        try:
            self.logger.info("Initializing speech engine...")

            # Check dependencies
            if sr is None:
                self.logger.error("speech_recognition library not installed")
                return False

            if pyttsx3 is None:
                self.logger.error("pyttsx3 library not installed")
                return False

            if pyaudio is None:
                self.logger.error("pyaudio library not installed")
                return False

            # Initialize recognizer
            self.recognizer = sr.Recognizer()
            self.recognizer.energy_threshold = 300
            self.recognizer.dynamic_energy_threshold = True
            self.recognizer.pause_threshold = 0.8

            # Initialize microphone
            try:
                self.microphone = sr.Microphone()
                with self.microphone as source:
                    self.recognizer.adjust_for_ambient_noise(source, duration=1)
                self.logger.debug("Microphone initialized successfully")
            except Exception as e:
                self.logger.error(f"Failed to initialize microphone: {e}")
                return False

            # Initialize TTS engine
            try:
                self.tts_engine = pyttsx3.init()
                self._configure_tts()
                self.logger.debug("TTS engine initialized successfully")
            except Exception as e:
                self.logger.error(f"Failed to initialize TTS engine: {e}")
                return False

            # Initialize wake word detector
            if self.config.wake_word_enabled:
                self.wake_detector = WakeWordDetector(
                    self.config.wake_word, 
                    self.config.sensitivity
                )

            self.logger.info("Speech engine initialized successfully")
            return True

        except Exception as e:
            self.logger.error(f"Failed to initialize speech engine: {e}")
            return False

    def _configure_tts(self):
        """Configure text-to-speech engine."""
        if not self.tts_engine:
            return

        # Configure voice
        voices = self.tts_engine.getProperty('voices')
        if voices:
            # Try to find a good voice (preferably English)
            for voice in voices:
                if 'english' in voice.name.lower() or 'en_' in voice.id:
                    self.tts_engine.setProperty('voice', voice.id)
                    break

        # Configure rate and volume
        self.tts_engine.setProperty('rate', 200)  # Words per minute
        self.tts_engine.setProperty('volume', 0.9)

    def recognize_speech(self, timeout: Optional[int] = None) -> Optional[str]:
        """Recognize speech from microphone."""
        if not self.recognizer or not self.microphone:
            self.logger.error("Speech engine not initialized")
            return None

        timeout = timeout or self.config.timeout_seconds

        try:
            self.logger.debug("Listening for speech...")
            with self.microphone as source:
                audio = self.recognizer.listen(source, timeout=timeout)

            self.logger.debug("Processing speech recognition...")

            # Try Google Speech API first (default)
            try:
                text = self.recognizer.recognize_google(audio)
                self.logger.debug(f"Recognized: {text}")
                return text
            except sr.RequestError:
                self.logger.warning("Google Speech API unavailable")
                # Fallback to offline recognition (limited)
                try:
                    text = self.recognizer.recognize_sphinx(audio)
                    self.logger.debug(f"Recognized (offline): {text}")
                    return text
                except sr.RequestError:
                    self.logger.error("Both online and offline recognition failed")
                    return None

        except sr.WaitTimeoutError:
            self.logger.debug("Speech recognition timeout")
            return None
        except sr.UnknownValueError:
            self.logger.debug("Could not understand audio")
            return None
        except Exception as e:
            self.logger.error(f"Speech recognition error: {e}")
            return None

    def speak_response(self, text: str, wait: bool = True) -> bool:
        """Convert text to speech."""
        if not self.tts_engine:
            self.logger.error("TTS engine not initialized")
            return False

        try:
            self.logger.debug(f"Speaking: {text}")
            
            if wait:
                self.tts_engine.say(text)
                self.tts_engine.runAndWait()
            else:
                # Run TTS in separate thread
                threading.Thread(
                    target=lambda: self.tts_engine.say(text) or self.tts_engine.runAndWait(),
                    daemon=True
                ).start()

            return True

        except Exception as e:
            self.logger.error(f"TTS error: {e}")
            return False

    def listen_for_wake_word(self, callback: Callable[[str], None]):
        """Start listening for wake word in background thread."""
        if not self.config.wake_word_enabled or not self.wake_detector:
            self.logger.warning("Wake word detection is disabled")
            return

        self.on_speech_detected = callback
        self.stop_audio.clear()

        def wake_word_loop():
            """Background thread for wake word detection."""
            self.logger.info(f"Listening for wake word: '{self.config.wake_word}'")

            while not self.stop_audio.is_set():
                try:
                    with self.microphone as source:
                        audio = self.recognizer.listen(source, timeout=1, phrase_time_limit=3)

                    # Check if this might be wake word
                    if self.wake_detector.detect_wake_word(audio):
                        self.logger.debug("Wake word detected, recognizing command...")
                        
                        # Recognize the actual command
                        command = self.recognize_speech(timeout=5)
                        if command:
                            self.wake_word_active = True
                            callback(command)
                            self.wake_word_active = False

                except sr.WaitTimeoutError:
                    continue
                except Exception as e:
                    self.logger.error(f"Wake word detection error: {e}")
                    time.sleep(1)

        self.audio_thread = threading.Thread(target=wake_word_loop, daemon=True)
        self.audio_thread.start()

    def listen_hotkey(self, callback: Callable[[str], None]):
        """Listen for speech when hotkey is pressed."""
        self.on_speech_detected = callback

        if self.config.wake_word_enabled:
            # Start wake word detection in background
            self.listen_for_wake_word(callback)

        self.logger.info("Hotkey mode activated. Press Ctrl+Space to speak.")

    def get_audio_devices(self) -> dict:
        """Get list of available audio devices."""
        devices = {
            "input": [],
            "output": []
        }

        try:
            if pyaudio:
                p = pyaudio.PyAudio()
                for i in range(p.get_device_count()):
                    info = p.get_device_info_by_index(i)
                    device = AudioDevice(
                        id=i,
                        name=info["name"],
                        channels=info["maxInputChannels"] if info["maxInputChannels"] > 0 else info["maxOutputChannels"],
                        sample_rate=int(info["defaultSampleRate"]),
                        is_input=info["maxInputChannels"] > 0,
                        is_output=info["maxOutputChannels"] > 0
                    )

                    if device.is_input:
                        devices["input"].append(device)
                    if device.is_output:
                        devices["output"].append(device)
                p.terminate()

        except Exception as e:
            self.logger.error(f"Failed to enumerate audio devices: {e}")

        return devices

    def test_microphone(self) -> bool:
        """Test microphone functionality."""
        if not self.recognizer or not self.microphone:
            self.logger.error("Speech engine not initialized")
            return False

        try:
            self.logger.info("Testing microphone...")
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
                audio = self.recognizer.listen(source, timeout=3)

            # Try to recognize something
            text = self.recognize_speech(timeout=5)
            self.logger.info("Microphone test successful")
            return True

        except Exception as e:
            self.logger.error(f"Microphone test failed: {e}")
            return False

    def test_speakers(self) -> bool:
        """Test speaker functionality."""
        if not self.tts_engine:
            self.logger.error("TTS engine not initialized")
            return False

        try:
            self.logger.info("Testing speakers...")
            self.speak_response("Testing JARVIS audio system", wait=True)
            self.logger.info("Speaker test successful")
            return True

        except Exception as e:
            self.logger.error(f"Speaker test failed: {e}")
            return False

    def set_volume(self, volume: float):
        """Set TTS volume (0.0 to 1.0)."""
        if self.tts_engine:
            self.tts_engine.setProperty('volume', max(0.0, min(1.0, volume)))

    def set_speech_rate(self, rate: int):
        """Set speech rate in words per minute."""
        if self.tts_engine:
            self.tts_engine.setProperty('rate', max(50, min(400, rate)))

    def stop_listening(self):
        """Stop audio listening threads."""
        self.stop_audio.set()
        if self.audio_thread and self.audio_thread.is_alive():
            self.audio_thread.join(timeout=2)
        self.logger.info("Stopped audio listening")

    def shutdown(self):
        """Cleanup speech engine resources."""
        self.logger.info("Shutting down speech engine...")
        
        self.stop_listening()

        if self.tts_engine:
            try:
                self.tts_engine.stop()
            except Exception as e:
                self.logger.error(f"Error stopping TTS engine: {e}")

        self.logger.info("Speech engine shutdown complete")
