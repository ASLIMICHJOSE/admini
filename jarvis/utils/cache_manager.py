#!/usr/bin/env python3
"""
JARVIS Cache Manager

Efficient caching system with TTL and cleanup.
"""

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional


class CacheManager:
    """Manages cached data with TTL."""

    def __init__(self, cache_file: str = "jarvis_cache.json"):
        self.cache_file = Path(cache_file)
        self.cache: Dict[str, Dict] = {}
        self.default_ttl = 3600  # 1 hour
        self.max_entries = 1000

    def load_cache(self):
        """Load cache from file."""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, 'r') as f:
                    self.cache = json.load(f)
        except Exception as e:
            logging.error(f"Failed to load cache: {e}")

    def save_cache(self):
        """Save cache to file."""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.cache, f, indent=2)
        except Exception as e:
            logging.error(f"Failed to save cache: {e}")

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if key in self.cache:
            entry = self.cache[key]
            if time.time() < entry.get('expires', 0):
                return entry.get('value')
            else:
                del self.cache[key]
        return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """Set value in cache with TTL."""
        ttl = ttl or self.default_ttl
        self.cache[key] = {
            'value': value,
            'expires': time.time() + ttl,
            'created': time.time()
        }
        
        # Cleanup old entries
        self._cleanup()
    
    def _cleanup(self):
        """Remove expired entries."""
        current_time = time.time()
        expired_keys = [
            key for key, entry in self.cache.items()
            if current_time > entry.get('expires', 0)
        ]
        
        for key in expired_keys:
            del self.cache[key]
        
        # Limit cache size
        if len(self.cache) > self.max_entries:
            # Keep most recent entries
            sorted_items = sorted(
                self.cache.items(),
                key=lambda x: x[1].get('created', 0),
                reverse=True
            )
            self.cache = dict(sorted_items[:self.max_entries])
    
    def clear(self):
        """Clear all cache entries."""
        self.cache.clear()
        
    def get_stats(self) -> Dict:
        """Get cache statistics."""
        return {
            'entries': len(self.cache),
            'max_entries': self.max_entries,
            'ttl': self.default_ttl
        }
