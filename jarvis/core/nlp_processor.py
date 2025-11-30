#!/usr/bin/env python3
"""
JARVIS NLP Processor

Handles natural language processing using OpenAI API for intelligent command understanding.
Includes fallback to rule-based processing for offline functionality.
"""

import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

try:
    import openai
except ImportError:
    openai = None

try:
    import tiktoken
except ImportError:
    tiktoken = None

from config import AIConfig, APIKeys


@dataclass
class CommandResult:
    """Result of NLP command processing."""
    intent: str
    entities: Dict[str, Any]
    confidence: float
    requires_confirmation: bool
    raw_text: str
    processing_method: str  # "openai" or "fallback"
    timestamp: datetime


@dataclass
class CachedResponse:
    """Cached API response."""
    key: str
    response: CommandResult
    created_at: datetime
    ttl_hours: int


class FallbackProcessor:
    """Fallback rule-based command processor for offline functionality."""

    def __init__(self):
        self.intent_patterns = {
            "open_app": [
                r"(?:open|launch|start|run)\s+(.+?)(?:\s+(?:app|application|program))?$",
                r"(?:start|run)\s+(.+?)$",
                r"open\s+(.+?)\s+app$"
            ],
            "close_app": [
                r"(?:close|quit|exit|stop)\s+(.+?)(?:\s+(?:app|application|program))?$",
                r"(?:close|quit)\s+(.+?)$",
                r"shutdown\s+(.+?)\s+app$"
            ],
            "get_weather": [
                r"(?:what'?s?|tell me|show me)\s+(?:the\s+)?weather(?:\s+(?:in|for|at)\s+(.+))?$",
                r"weather(?:\s+(?:in|for|at)\s+(.+))?$",
                r"(?:how'?s?|what'?s? the) weather(?:\s+(?:in|for|at)\s+(.+))?$"
            ],
            "search_web": [
                r"(?:search|google|look up)\s+(.+?)\s*(?:on\s+google)?$",
                r"(?:find|find out|tell me about)\s+(.+?)$",
                r"(?:what\s+is|who\s+is|where\s+is)\s+(.+?)$"
            ],
            "search_youtube": [
                r"(?:search|play|find)\s+(.+?)\s+on\s+youtube$",
                r"youtube\s+(.+?)$",
                r"(?:play|watch)\s+(.+?)\s+on\s+youtube$"
            ],
            "search_wikipedia": [
                r"(?:search|look up)\s+(.+?)\s+on\s+wikipedia$",
                r"wikipedia\s+(.+?)$",
                r"tell me about\s+(.+?)$"
            ],
            "set_reminder": [
                r"(?:remind|reminder)\s+(?:me\s+)?(?:to\s+)?(.+?)(?:\s+in\s+(\d+)\s+(minute|minutes|hour|hours))?$",
                r"(?:set\s+)?reminder\s+(?:to\s+)?(.+?)$",
                r"remind\s+me\s+(.+?)$"
            ],
            "set_timer": [
                r"(?:set\s+)?(?:a\s+)?timer\s+for\s+(\d+)\s+(minute|minutes|hour|hours)$",
                r"timer\s+(\d+)\s+(minute|minutes|hour|hours)$",
                r"(?:count|countdown)\s+(.+?)$"
            ],
            "play_music": [
                r"(?:play|start)\s+(.+?)(?:\s+(?:music|song|track))?$",
                r"(?:listen to|hear)\s+(.+?)$",
                r"music\s+(.+?)$"
            ],
            "send_email": [
                r"(?:send|write)\s+(?:an\s+)?email\s+(?:to\s+)?(.+?)(?:\s+saying\s+(.+?))?$",
                r"email\s+(.+?)(?:\s+saying\s+(.+?))?$",
                r"(?:message|contact)\s+(.+?)$"
            ],
            "get_time": [
                r"(?:what\s+)?time\s+is\s+it$",
                r"(?:current\s+)?time$",
                r"(?:tell me the time|what time)$"
            ],
            "get_date": [
                r"(?:what\s+)?(?:day|date)\s+is\s+it$",
                r"(?:current\s+)?(?:day|date)$",
                r"(?:tell me the date|what date)$"
            ],
            "shutdown_system": [
                r"(?:shutdown|turn off|power off)\s+(?:the\s+)?(?:computer|pc|system)$",
                r"(?:shut\s+down|power\s+down)$"
            ],
            "restart_system": [
                r"(?:restart|reboot|reboot)\s+(?:the\s+)?(?:computer|pc|system)$",
                r"(?:restart\s+computer|reboot\s+system)$"
            ],
            "get_news": [
                r"(?:what'?s?\s+(?:the\s+)?latest\s+)?news(?:\s+(?:about|on)\s+(.+?))?$",
                r"(?:tell|show)\s+(?:me\s+)?(?:the\s+)?news(?:\s+(?:about|on)\s+(.+?))?$",
                r"(?:news|headlines)(?:\s+(?:about|on)\s+(.+?))?$"
            ]
        }

        self.sensitive_patterns = [
            r"\b(password|secret|token|key|credential)\b",
            r"\b(delete|remove|uninstall)\s+.+\b",
            r"\b(format|erase|wipe)\s+.+\b",
            r"\b(administrator|root|sudo)\b"
        ]

    def process_command(self, text: str) -> Optional[CommandResult]:
        """Process command using rule-based patterns."""
        text = text.strip().lower()

        # Check for sensitive commands
        is_sensitive = any(re.search(pattern, text) for pattern in self.sensitive_patterns)

        # Try to match intent patterns
        for intent, patterns in self.intent_patterns.items():
            for pattern in patterns:
                match = re.match(pattern, text, re.IGNORECASE)
                if match:
                    entities = {}
                    if match.groups():
                        groups = match.groups()
                        if intent == "open_app":
                            entities["app_name"] = groups[0].strip()
                        elif intent == "close_app":
                            entities["app_name"] = groups[0].strip()
                        elif intent in ["get_weather", "search_web", "search_youtube", "search_wikipedia"]:
                            entities["query"] = groups[0].strip() if groups[0] else None
                        elif intent == "set_reminder":
                            entities["message"] = groups[0].strip()
                            if len(groups) > 2 and groups[1]:
                                entities["time_value"] = int(groups[1])
                                entities["time_unit"] = groups[2]
                        elif intent == "set_timer":
                            entities["time_value"] = int(groups[0])
                            entities["time_unit"] = groups[1]
                        elif intent == "play_music":
                            entities["song_or_playlist"] = groups[0].strip()
                        elif intent == "send_email":
                            entities["recipient"] = groups[0].strip()
                            if len(groups) > 1 and groups[1]:
                                entities["message"] = groups[1].strip()

                    return CommandResult(
                        intent=intent,
                        entities=entities,
                        confidence=0.7,  # Medium confidence for fallback
                        requires_confirmation=is_sensitive or intent in ["shutdown_system", "restart_system", "send_email"],
                        raw_text=text,
                        processing_method="fallback",
                        timestamp=datetime.now()
                    )

        # If no pattern matched, return general query
        return CommandResult(
            intent="general_query",
            entities={"query": text},
            confidence=0.3,
            requires_confirmation=False,
            raw_text=text,
            processing_method="fallback",
            timestamp=datetime.now()
        )


class NLPProcessor:
    """Main NLP processor with OpenAI integration and fallback."""

    def __init__(self, config: AIConfig, logger: logging.Logger):
        self.config = config
        self.logger = logger

        # OpenAI client
        self.openai_client = None
        self.encoding = None

        # Fallback processor
        self.fallback_processor = FallbackProcessor()

        # Response cache
        self.cache: Dict[str, CachedResponse] = {}
        self.cache_dir = Path("cache")
        self.cache_file = self.cache_dir / "nlp_cache.json"

        # Statistics
        self.requests_made = 0
        self.cache_hits = 0

        # System prompts
        self.system_prompt = """
You are JARVIS, a voice assistant that helps users with daily computer tasks. Parse user commands into structured JSON format.

Common intents:
- open_app: Launch an application
- close_app: Close a running application  
- get_weather: Get weather information
- search_web: Search the internet
- search_youtube: Search YouTube videos
- search_wikipedia: Search Wikipedia articles
- set_reminder: Set a reminder
- set_timer: Set a timer
- play_music: Play music
- send_email: Send an email
- get_time: Get current time
- get_date: Get current date
- shutdown_system: Shutdown the computer
- restart_system: Restart the computer
- get_news: Get news headlines

Response format (JSON only):
{
    "intent": "command_intent",
    "entities": {
        "key": "value"
    },
    "confidence": 0.95,
    "requires_confirmation": false
}

Only respond with valid JSON. No additional text.
        """

    def initialize(self) -> bool:
        """Initialize the NLP processor."""
        try:
            self.logger.info("Initializing NLP processor...")

            # Initialize cache directory
            self.cache_dir.mkdir(exist_ok=True)

            # Initialize OpenAI if enabled
            if self.config.use_openai:
                if openai is None:
                    self.logger.error("OpenAI library not installed")
                    return False

                if not hasattr(self.config, 'api_keys') or not self.config.api_keys.openai_api_key:
                    self.logger.error("OpenAI API key not configured")
                    return False

                self.openai_client = openai.OpenAI(api_key=self.config.api_keys.openai_api_key)

                # Initialize tokenizer for caching
                if tiktoken:
                    self.encoding = tiktoken.encoding_for_model(self.config.openai_model)

                self.logger.info("OpenAI client initialized")
            else:
                self.logger.info("OpenAI disabled, using fallback only")

            # Load existing cache
            self._load_cache()

            self.logger.info("NLP processor initialized successfully")
            return True

        except Exception as e:
            self.logger.error(f"Failed to initialize NLP processor: {e}")
            return False

    def process_command(self, text: str) -> CommandResult:
        """Process a command using OpenAI or fallback."""
        if not text or not text.strip():
            return CommandResult(
                intent="error",
                entities={"error": "Empty command"},
                confidence=0.0,
                requires_confirmation=False,
                raw_text=text,
                processing_method="error",
                timestamp=datetime.now()
            )

        text = text.strip()

        # Try OpenAI if enabled
        if self.config.use_openai and self.openai_client:
            try:
                result = self._process_with_openai(text)
                if result:
                    self.requests_made += 1
                    return result
            except Exception as e:
                self.logger.error(f"OpenAI processing failed: {e}")

        # Fallback to rule-based processing
        self.logger.debug("Using fallback processing")
        return self.fallback_processor.process_command(text)

    def _process_with_openai(self, text: str) -> Optional[CommandResult]:
        """Process command using OpenAI API."""
        # Check cache first
        if self.config.cache_responses:
            cached_result = self._get_cached_response(text)
            if cached_result:
                self.cache_hits += 1
                return cached_result

        try:
            response = self.openai_client.chat.completions.create(
                model=self.config.openai_model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": text}
                ],
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature
            )

            content = response.choices[0].message.content.strip()

            # Parse JSON response
            try:
                parsed = json.loads(content)
            except json.JSONDecodeError:
                # Try to extract JSON from content
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    parsed = json.loads(json_match.group())
                else:
                    raise ValueError("Could not parse OpenAI response as JSON")

            # Create CommandResult
            result = CommandResult(
                intent=parsed.get("intent", "unknown"),
                entities=parsed.get("entities", {}),
                confidence=float(parsed.get("confidence", 0.5)),
                requires_confirmation=bool(parsed.get("requires_confirmation", False)),
                raw_text=text,
                processing_method="openai",
                timestamp=datetime.now()
            )

            # Cache the response
            if self.config.cache_responses:
                self._cache_response(text, result)

            return result

        except Exception as e:
            self.logger.error(f"OpenAI API error: {e}")
            return None

    def _get_cache_key(self, text: str) -> str:
        """Generate cache key for text."""
        # Create a consistent hash for caching
        return hashlib.md5(text.lower().encode()).hexdigest()

    def _get_cached_response(self, text: str) -> Optional[CommandResult]:
        """Get cached response if valid."""
        if not self.config.cache_responses:
            return None

        cache_key = self._get_cache_key(text)

        if cache_key in self.cache:
            cached = self.cache[cache_key]
            age = datetime.now() - cached.created_at
            
            if age < timedelta(hours=cached.ttl_hours):
                return cached.response
            else:
                # Remove expired cache
                del self.cache[cache_key]

        return None

    def _cache_response(self, text: str, response: CommandResult):
        """Cache a response."""
        if not self.config.cache_responses:
            return

        cache_key = self._get_cache_key(text)
        self.cache[cache_key] = CachedResponse(
            key=cache_key,
            response=response,
            created_at=datetime.now(),
            ttl_hours=self.config.cache_ttl_hours
        )

    def _load_cache(self):
        """Load cache from file."""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, 'r') as f:
                    data = json.load(f)

                for key, item in data.items():
                    created_at = datetime.fromisoformat(item["created_at"])
                    age = datetime.now() - created_at

                    if age < timedelta(hours=item["ttl_hours"]):
                        # Reconstruct CommandResult
                        response_data = item["response"]
                        response = CommandResult(
                            intent=response_data["intent"],
                            entities=response_data["entities"],
                            confidence=response_data["confidence"],
                            requires_confirmation=response_data["requires_confirmation"],
                            raw_text=response_data["raw_text"],
                            processing_method=response_data["processing_method"],
                            timestamp=datetime.fromisoformat(response_data["timestamp"])
                        )

                        self.cache[key] = CachedResponse(
                            key=key,
                            response=response,
                            created_at=created_at,
                            ttl_hours=item["ttl_hours"]
                        )

                self.logger.info(f"Loaded {len(self.cache)} cached responses")

        except Exception as e:
            self.logger.error(f"Failed to load cache: {e}")

    def _save_cache(self):
        """Save cache to file."""
        try:
            # Convert cache to JSON-serializable format
            serializable_cache = {}
            for key, cached in self.cache.items():
                serializable_cache[key] = {
                    "response": {
                        "intent": cached.response.intent,
                        "entities": cached.response.entities,
                        "confidence": cached.response.confidence,
                        "requires_confirmation": cached.response.requires_confirmation,
                        "raw_text": cached.response.raw_text,
                        "processing_method": cached.response.processing_method,
                        "timestamp": cached.response.timestamp.isoformat()
                    },
                    "created_at": cached.created_at.isoformat(),
                    "ttl_hours": cached.ttl_hours
                }

            with open(self.cache_file, 'w') as f:
                json.dump(serializable_cache, f, indent=2)

        except Exception as e:
            self.logger.error(f"Failed to save cache: {e}")

    def check_sensitive_command(self, text: str) -> bool:
        """Check if command contains sensitive content."""
        sensitive_patterns = [
            r"\b(password|secret|token|key|credential)\b",
            r"\b(delete|remove|uninstall)\s+.+\b",
            r"\b(format|erase|wipe)\s+.+\b",
            r"\b(administrator|root|sudo)\b"
        ]

        text_lower = text.lower()
        return any(re.search(pattern, text_lower) for pattern in sensitive_patterns)

    def test_openai_connection(self) -> bool:
        """Test OpenAI API connection."""
        if not self.config.use_openai or not self.openai_client:
            return False

        try:
            response = self.openai_client.chat.completions.create(
                model=self.config.openai_model,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=10
            )
            return response.choices[0].message.content is not None
        except Exception as e:
            self.logger.error(f"OpenAI connection test failed: {e}")
            return False

    def get_statistics(self) -> Dict[str, Any]:
        """Get processing statistics."""
        return {
            "requests_made": self.requests_made,
            "cache_hits": self.cache_hits,
            "cache_size": len(self.cache),
            "cache_hit_rate": self.cache_hits / max(1, self.requests_made),
            "processing_method": "openai" if self.config.use_openai else "fallback"
        }

    def clear_cache(self):
        """Clear the response cache."""
        self.cache.clear()
        try:
            if self.cache_file.exists():
                self.cache_file.unlink()
        except Exception as e:
            self.logger.error(f"Failed to clear cache file: {e}")

    def shutdown(self):
        """Cleanup NLP processor resources."""
        self.logger.info("Shutting down NLP processor...")

        # Save cache
        self._save_cache()

        self.logger.info("NLP processor shutdown complete")
