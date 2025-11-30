#!/usr/bin/env python3
"""
JARVIS Text Utilities

Text processing and sanitization utilities.
"""

import re
from typing import List, Optional


def clean_text(text: str) -> str:
    """Clean and normalize text."""
    if not text:
        return ""
    
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text.strip())
    
    return text


def extract_email(text: str) -> Optional[str]:
    """Extract email address from text."""
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    match = re.search(email_pattern, text)
    return match.group(0) if match else None


def extract_numbers(text: str) -> List[int]:
    """Extract all numbers from text."""
    numbers = re.findall(r'\d+', text)
    return [int(num) for num in numbers]


def safe_filename(text: str) -> str:
    """Convert text to safe filename."""
    # Remove or replace unsafe characters
    safe = re.sub(r'[<>:"/\\|?*]', '_', text)
    safe = safe.strip()
    
    # Limit length
    return safe[:100]
