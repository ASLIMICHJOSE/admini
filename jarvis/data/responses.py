#!/usr/bin/env python3
"""
JARVIS Response Templates

Predefined responses for common situations.
"""

# Greetings and acknowledgments
GREETINGS = [
    "I'm here to help.",
    "Yes? I'm listening.",
    "Ready for your command.",
    "How can I assist you?",
]

# Error responses
ERROR_RESPONSES = {
    "audio_error": "I'm having trouble with the audio. Please check your microphone.",
    "network_error": "I can't connect to the internet right now.",
    "api_error": "One of my services is temporarily unavailable.",
    "permission_error": "I don't have the necessary permissions for that.",
    "not_understood": "I didn't understand that command.",
}

# Success responses
SUCCESS_RESPONSES = {
    "app_opened": "Opened successfully.",
    "app_closed": "Closed successfully.",
    "email_sent": "Email sent successfully.",
    "timer_set": "Timer set successfully.",
    "reminder_set": "Reminder set successfully.",
    "volume_changed": "Volume adjusted successfully.",
}

# Confirmation requests
CONFIRMATION_REQUESTS = [
    "Are you sure you want me to do that?",
    "This is a system command. Confirm if you want to proceed.",
    "This requires confirmation. Shall I continue?",
]

# Status updates
STATUS_UPDATES = {
    "thinking": "Let me check on that for you.",
    "working": "I'm working on that now.",
    "searching": "Searching for information...",
    "loading": "Please wait while I process that.",
}
