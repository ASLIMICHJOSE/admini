#!/usr/bin/env python3
"""
JARVIS Information Provider

Handles information retrieval from various sources including weather,
news, Wikipedia, and general knowledge queries.
"""

import json
import logging
import requests
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from urllib.parse import urlencode, quote

from config import AIConfig, APIKeys


class InformationProvider:
    """Provides information from various external sources."""

    def __init__(self, config, logger: logging.Logger):
        self.config = config
        self.logger = logger

        # API clients
        self.weather_api_key = None
        self.news_api_key = None
        self.openai_client = None

        # Response cache
        self.cache: Dict[str, Dict] = {}
        self.cache_ttl = {
            "weather": 600,  # 10 minutes
            "news": 1800,   # 30 minutes
            "wikipedia": 86400  # 24 hours
        }

    def initialize(self) -> bool:
        """Initialize information provider."""
        try:
            self.logger.info("Initializing information provider...")

            # Setup API keys
            if hasattr(self.config, 'api_keys'):
                self.weather_api_key = getattr(self.config.api_keys, 'weather_api_key', None)
                self.news_api_key = getattr(self.config.api_keys, 'news_api_key', None)

            # Setup OpenAI client if enabled
            if self.config.use_openai and hasattr(self.config, 'api_keys'):
                try:
                    import openai
                    api_key = getattr(self.config.api_keys, 'openai_api_key', None)
                    if api_key:
                        self.openai_client = openai.OpenAI(api_key=api_key)
                        self.logger.info("OpenAI client initialized for general queries")
                except ImportError:
                    self.logger.warning("OpenAI library not available")
                except Exception as e:
                    self.logger.warning(f"Failed to initialize OpenAI: {e}")

            # Test API connections
            if self.weather_api_key:
                if not self._test_weather_api():
                    self.logger.warning("Weather API test failed")
                    self.weather_api_key = None
                else:
                    self.logger.info("Weather API initialized")
            
            if self.news_api_key:
                if not self._test_news_api():
                    self.logger.warning("News API test failed")
                    self.news_api_key = None
                else:
                    self.logger.info("News API initialized")

            self.logger.info("Information provider initialized successfully")
            return True

        except Exception as e:
            self.logger.error(f"Failed to initialize information provider: {e}")
            return False

    def get_weather(self, command) -> Any:
        """Get weather information for a location."""
        from jarvis.core.command_dispatcher import ExecutionResult
        
        location = command.entities.get("location", "current location")
        
        try:
            self.logger.info(f"Getting weather for: {location}")
            
            # Check cache
            cache_key = f"weather_{location.lower()}"
            if self._is_cached(cache_key, "weather"):
                cached_data = self.cache[cache_key]["data"]
                return ExecutionResult(
                    success=True,
                    message=f"Weather information for {location} (from cache)",
                    data=cached_data
                )

            if not self.weather_api_key:
                return ExecutionResult(
                    success=False,
                    message="Weather API key not configured",
                    error="Missing weather API key"
                )

            # Get weather from OpenWeatherMap
            weather_data = self._fetch_weather_data(location)
            
            if weather_data:
                # Cache the result
                self._cache_result(cache_key, "weather", weather_data)
                
                return ExecutionResult(
                    success=True,
                    message=f"Successfully retrieved weather for {location}",
                    data=weather_data
                )
            else:
                return ExecutionResult(
                    success=False,
                    message=f"Could not retrieve weather for {location}",
                    error="Weather API request failed"
                )

        except Exception as e:
            return ExecutionResult(
                success=False,
                message=f"Error getting weather: {str(e)}",
                error=str(e)
            )

    def _fetch_weather_data(self, location: str) -> Optional[Dict]:
        """Fetch weather data from OpenWeatherMap API."""
        try:
            # Prepare API request
            base_url = "https://api.openweathermap.org/data/2.5/weather"
            
            # Handle special case for current location
            if location.lower() in ["current location", "here", "my location"]:
                # Use a default location or geolocation (simplified)
                location = "New York, US"  # Default fallback
            
            params = {
                "q": location,
                "appid": self.weather_api_key,
                "units": "metric"  # Celsius
            }

            response = requests.get(base_url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()
            
            # Parse weather data
            weather = {
                "location": data["name"],
                "country": data["sys"]["country"],
                "temperature": round(data["main"]["temp"], 1),
                "feels_like": round(data["main"]["feels_like"], 1),
                "humidity": data["main"]["humidity"],
                "pressure": data["main"]["pressure"],
                "description": data["weather"][0]["description"].title(),
                "wind_speed": data.get("wind", {}).get("speed", 0),
                "wind_direction": data.get("wind", {}).get("deg", 0),
                "visibility": data.get("visibility", 0) / 1000,  # Convert to km
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

            return weather

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Weather API request error: {e}")
            return None
        except KeyError as e:
            self.logger.error(f"Weather data parsing error: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Weather fetch error: {e}")
            return None

    def get_news(self, command) -> Any:
        """Get news headlines."""
        from jarvis.core.command_dispatcher import ExecutionResult
        
        category = command.entities.get("category", "general")
        count = 10  # Default number of headlines
        
        try:
            self.logger.info(f"Getting news for category: {category}")
            
            # Check cache
            cache_key = f"news_{category}"
            if self._is_cached(cache_key, "news"):
                cached_data = self.cache[cache_key]["data"]
                return ExecutionResult(
                    success=True,
                    message=f"News headlines for {category} (from cache)",
                    data=cached_data
                )

            if not self.news_api_key:
                return ExecutionResult(
                    success=False,
                    message="News API key not configured",
                    error="Missing news API key"
                )

            # Get news from NewsAPI
            news_data = self._fetch_news_data(category, count)
            
            if news_data:
                # Cache the result
                self._cache_result(cache_key, "news", news_data)
                
                return ExecutionResult(
                    success=True,
                    message=f"Successfully retrieved {len(news_data['articles'])} news articles",
                    data=news_data
                )
            else:
                return ExecutionResult(
                    success=False,
                    message=f"Could not retrieve news for category: {category}",
                    error="News API request failed"
                )

        except Exception as e:
            return ExecutionResult(
                success=False,
                message=f"Error getting news: {str(e)}",
                error=str(e)
            )

    def _fetch_news_data(self, category: str, count: int) -> Optional[Dict]:
        """Fetch news data from NewsAPI."""
        try:
            # Prepare API request
            base_url = "https://newsapi.org/v2/top-headlines"
            
            # Map common categories to NewsAPI categories
            category_map = {
                "general": "general",
                "business": "business",
                "technology": "technology",
                "science": "science",
                "health": "health",
                "sports": "sports",
                "entertainment": "entertainment"
            }
            
            api_category = category_map.get(category.lower(), "general")
            
            params = {
                "apiKey": self.news_api_key,
                "category": api_category,
                "country": "us",  # Default to US news
                "pageSize": min(count, 100)  # API limit
            }

            response = requests.get(base_url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()
            
            # Parse news data
            articles = []
            for article in data.get("articles", [])[:count]:
                parsed_article = {
                    "title": article.get("title", ""),
                    "description": article.get("description", ""),
                    "source": article.get("source", {}).get("name", ""),
                    "author": article.get("author", ""),
                    "url": article.get("url", ""),
                    "url_to_image": article.get("urlToImage", ""),
                    "published_at": article.get("publishedAt", ""),
                    "content": article.get("content", "")
                }
                articles.append(parsed_article)

            return {
                "category": category,
                "total_results": len(articles),
                "articles": articles,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

        except requests.exceptions.RequestException as e:
            self.logger.error(f"News API request error: {e}")
            return None
        except KeyError as e:
            self.logger.error(f"News data parsing error: {e}")
            return None
        except Exception as e:
            self.logger.error(f"News fetch error: {e}")
            return None

    def get_wikipedia_summary(self, command) -> Any:
        """Get Wikipedia article summary."""
        from jarvis.core.command_dispatcher import ExecutionResult
        
        topic = command.entities.get("query", "").strip()
        
        if not topic:
            return ExecutionResult(
                success=False,
                message="Search topic is required for Wikipedia",
                error="Missing search query"
            )

        try:
            self.logger.info(f"Getting Wikipedia summary for: {topic}")
            
            # Check cache
            cache_key = f"wikipedia_{topic.lower()}"
            if self._is_cached(cache_key, "wikipedia"):
                cached_data = self.cache[cache_key]["data"]
                return ExecutionResult(
                    success=True,
                    message=f"Wikipedia summary for {topic} (from cache)",
                    data=cached_data
                )

            # Get Wikipedia data
            wiki_data = self._fetch_wikipedia_data(topic)
            
            if wiki_data:
                # Cache the result
                self._cache_result(cache_key, "wikipedia", wiki_data)
                
                return ExecutionResult(
                    success=True,
                    message=f"Successfully retrieved Wikipedia summary for {topic}",
                    data=wiki_data
                )
            else:
                return ExecutionResult(
                    success=False,
                    message=f"Could not find Wikipedia article for: {topic}",
                    error="Wikipedia article not found"
                )

        except Exception as e:
            return ExecutionResult(
                success=False,
                message=f"Error getting Wikipedia summary: {str(e)}",
                error=str(e)
            )

    def _fetch_wikipedia_data(self, topic: str) -> Optional[Dict]:
        """Fetch Wikipedia data using MediaWiki API."""
        try:
            # Wikipedia API endpoint
            base_url = "https://en.wikipedia.org/w/api.php"
            
            # Step 1: Search for the article
            search_params = {
                "action": "query",
                "list": "search",
                "srsearch": topic,
                "format": "json",
                "utf8": 1,
                "srlimit": 1
            }

            response = requests.get(base_url, params=search_params, timeout=10)
            response.raise_for_status()

            search_data = response.json()
            search_results = search_data.get("query", {}).get("search", [])
            
            if not search_results:
                return None

            # Get the page title from search results
            page_title = search_results[0]["title"]
            
            # Step 2: Get article extract
            extract_params = {
                "action": "query",
                "prop": "extracts|info",
                "titles": page_title,
                "exintro": True,
                "explaintext": True,
                "format": "json",
                "utf8": 1
            }

            response = requests.get(base_url, params=extract_params, timeout=10)
            response.raise_for_status()

            article_data = response.json()
            pages = article_data.get("query", {}).get("pages", {})
            
            # Get the page (there should be only one)
            if not pages:
                return None
            
            page_id = next(iter(pages))
            page_info = pages[page_id]
            
            # Parse article data
            return {
                "title": page_info.get("title", ""),
                "extract": page_info.get("extract", ""),
                "description": page_info.get("description", ""),
                "url": f"https://en.wikipedia.org/wiki/{quote(page_title.replace(' ', '_'))}",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Wikipedia API request error: {e}")
            return None
        except KeyError as e:
            self.logger.error(f"Wikipedia data parsing error: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Wikipedia fetch error: {e}")
            return None

    def get_current_time(self, command) -> Any:
        """Get current time, optionally for a specific timezone."""
        from jarvis.core.command_dispatcher import ExecutionResult
        
        timezone_str = command.entities.get("timezone", "local")
        
        try:
            self.logger.info(f"Getting current time for: {timezone_str}")
            
            # Get current time
            if timezone_str.lower() == "local":
                current_time = datetime.now()
                time_str = current_time.strftime("%I:%M %p on %A, %B %d, %Y")
                location = "your local time"
            else:
                # For simplicity, just return UTC time for non-local requests
                current_time = datetime.now(timezone.utc)
                time_str = current_time.strftime("%I:%M %p UTC on %A, %B %d, %Y")
                location = "UTC time"
            
            return ExecutionResult(
                success=True,
                message=f"Current {location}: {time_str}",
                data={
                    "time": time_str,
                    "timezone": timezone_str,
                    "timestamp": current_time.isoformat()
                }
            )

        except Exception as e:
            return ExecutionResult(
                success=False,
                message=f"Error getting time: {str(e)}",
                error=str(e)
            )

    def get_current_date(self, command) -> Any:
        """Get current date."""
        from jarvis.core.command_dispatcher import ExecutionResult
        
        try:
            self.logger.info("Getting current date")
            
            current_date = datetime.now()
            date_str = current_date.strftime("%A, %B %d, %Y")
            
            return ExecutionResult(
                success=True,
                message=f"Today is {date_str}",
                data={
                    "date": date_str,
                    "day_of_week": current_date.strftime("%A"),
                    "month": current_date.strftime("%B"),
                    "day": current_date.day,
                    "year": current_date.year,
                    "timestamp": current_date.isoformat()
                }
            )

        except Exception as e:
            return ExecutionResult(
                success=False,
                message=f"Error getting date: {str(e)}",
                error=str(e)
            )

    def answer_general_question(self, command) -> Any:
        """Answer general knowledge questions using OpenAI."""
        from jarvis.core.command_dispatcher import ExecutionResult
        
        question = command.entities.get("query", "").strip()
        
        if not question:
            return ExecutionResult(
                success=False,
                message="Question is required for general query",
                error="Missing query parameter"
            )

        try:
            self.logger.info(f"Answering general question: {question}")
            
            if not self.openai_client:
                return ExecutionResult(
                    success=False,
                    message="OpenAI not available for general questions",
                    error="OpenAI client not initialized"
                )

            # Check cache
            cache_key = f"question_{hash(question)}"
            if self._is_cached(cache_key, "weather", 3600):  # 1 hour cache for questions
                cached_data = self.cache[cache_key]["data"]
                return ExecutionResult(
                    success=True,
                    message=f"Answer from cache",
                    data=cached_data
                )

            # Use OpenAI to answer the question
            answer = self._ask_openai(question)
            
            if answer:
                result_data = {
                    "question": question,
                    "answer": answer,
                    "source": "OpenAI",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                
                # Cache the result
                self._cache_result(cache_key, "weather", result_data, 3600)  # 1 hour TTL
                
                return ExecutionResult(
                    success=True,
                    message="Question answered successfully",
                    data=result_data
                )
            else:
                return ExecutionResult(
                    success=False,
                    message="Could not get an answer to your question",
                    error="OpenAI request failed"
                )

        except Exception as e:
            return ExecutionResult(
                success=False,
                message=f"Error answering question: {str(e)}",
                error=str(e)
            )

    def _ask_openai(self, question: str) -> Optional[str]:
        """Ask OpenAI a question."""
        try:
            response = self.openai_client.chat.completions.create(
                model=getattr(self.config, 'openai_model', 'gpt-3.5-turbo'),
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant. Provide clear, concise answers to questions."
                    },
                    {
                        "role": "user",
                        "content": question
                    }
                ],
                max_tokens=getattr(self.config, 'max_tokens', 300),
                temperature=getattr(self.config, 'temperature', 0.7)
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            self.logger.error(f"OpenAI request error: {e}")
            return None

    def _test_weather_api(self) -> bool:
        """Test weather API connection."""
        try:
            response = requests.get(
                "https://api.openweathermap.org/data/2.5/weather",
                params={"q": "London", "appid": self.weather_api_key},
                timeout=5
            )
            return response.status_code == 200
        except Exception:
            return False

    def _test_news_api(self) -> bool:
        """Test news API connection."""
        try:
            response = requests.get(
                "https://newsapi.org/v2/top-headlines",
                params={"apiKey": self.news_api_key, "country": "us", "pageSize": 1},
                timeout=5
            )
            return response.status_code == 200
        except Exception:
            return False

    def _is_cached(self, cache_key: str, cache_type: str, custom_ttl: Optional[int] = None) -> bool:
        """Check if data is cached and not expired."""
        if cache_key not in self.cache:
            return False
        
        cache_entry = self.cache[cache_key]
        ttl = custom_ttl or self.cache_ttl.get(cache_type, 600)
        
        # Check if cache is expired
        elapsed = time.time() - cache_entry["timestamp"]
        if elapsed > ttl:
            del self.cache[cache_key]
            return False
        
        return True

    def _cache_result(self, cache_key: str, cache_type: str, data: Any, ttl: Optional[int] = None):
        """Cache result with timestamp."""
        self.cache[cache_key] = {
            "data": data,
            "timestamp": time.time(),
            "type": cache_type,
            "ttl": ttl or self.cache_ttl.get(cache_type, 600)
        }

    def test(self) -> bool:
        """Test information provider functionality."""
        try:
            self.logger.info("Testing information provider...")
            
            # Test basic functionality
            test_commands = [
                ("get_current_time", "Test time retrieval"),
                ("get_current_date", "Test date retrieval")
            ]

            for method_name, description in test_commands:
                try:
                    method = getattr(self, method_name)
                    result = method(None)
                    
                    if result.success:
                        self.logger.info(f"✅ {description} - PASSED")
                    else:
                        self.logger.error(f"❌ {description} - FAILED: {result.error}")
                        return False
                        
                except Exception as e:
                    self.logger.error(f"❌ {description} - ERROR: {e}")
                    return False

            # Test API connections if available
            if self.weather_api_key:
                self.logger.info("✅ Weather API - AVAILABLE")
            else:
                self.logger.warning("⚠️  Weather API - NOT CONFIGURED")

            if self.news_api_key:
                self.logger.info("✅ News API - AVAILABLE")
            else:
                self.logger.warning("⚠️  News API - NOT CONFIGURED")

            if self.openai_client:
                self.logger.info("✅ OpenAI - AVAILABLE")
            else:
                self.logger.warning("⚠️  OpenAI - NOT CONFIGURED")

            self.logger.info("Information provider tests completed successfully")
            return True

        except Exception as e:
            self.logger.error(f"Information provider test failed: {e}")
            return False

    def shutdown(self):
        """Cleanup information provider resources."""
        self.logger.info("Shutting down information provider...")
        
        # Clear cache
        self.cache.clear()
        
        self.logger.info("Information provider shutdown complete")
