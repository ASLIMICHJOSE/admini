#!/usr/bin/env python3
"""
JARVIS Audio Utilities

Audio processing utilities and helper functions.
"""

import logging
from typing import Optional


def detect_microphone() -> bool:
    """Detect if microphone is available."""
    try:
        import speech_recognition as sr
        mic = sr.Microphone()
        return True
    except Exception:
        return False


def detect_speakers() -> bool:
    """Detect if speakers are available."""
    try:
        import pyttsx3
        engine = pyttsx3.init()
        return True
    except Exception:
        return False


def get_audio_devices() -> dict:
    """Get available audio devices."""
    return {
        "microphone": detect_microphone(),
        "speakers": detect_speakers()
    }
