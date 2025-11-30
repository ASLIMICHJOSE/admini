#!/usr/bin/env python3
"""
JARVIS Command Patterns

Command pattern definitions and response templates.
"""

# Command intent mappings
INTENT_MAPPINGS = {
    "open": "open_app",
    "launch": "open_app",
    "start": "open_app",
    "close": "close_app",
    "quit": "close_app",
    "exit": "close_app",
    "shutdown": "shutdown_system",
    "restart": "restart_system",
    "play": "play_music",
    "music": "play_music",
    "pause": "pause_resume_music",
    "resume": "pause_resume_music",
    "stop": "pause_resume_music",
    "search": "search_web",
    "find": "search_web",
    "google": "search_web",
    "youtube": "search_youtube",
    "wiki": "search_wikipedia",
    "wikipedia": "search_wikipedia",
    "time": "get_time",
    "date": "get_date",
    "weather": "get_weather",
    "news": "get_news",
    "email": "send_email",
    "mail": "send_email",
    "reminder": "set_reminder",
    "timer": "set_timer",
    "alarm": "set_reminder",
    "volume": "set_volume",
    "louder": "set_volume",
    "quieter": "set_volume",
}

# Application mappings
APP_MAPPINGS = {
    "chrome": "Chrome",
    "browser": "Chrome",
    "firefox": "Firefox",
    "safari": "Safari",
    "edge": "Microsoft Edge",
    "vs code": "Visual Studio Code",
    "code": "Visual Studio Code",
    "notepad": "Notepad",
    "spotify": "Spotify",
    "music": "Spotify",
    "discord": "Discord",
    "slack": "Slack",
}

# Response templates
RESPONSE_TEMPLATES = {
    "command_received": "Yes? I'm listening.",
    "processing": "Processing your request.",
    "complete": "Done.",
    "error": "Sorry, I encountered an error.",
    "not_understood": "I didn't understand that. Could you rephrase?",
    "confirmation_required": "This requires confirmation. Please confirm.",
}
