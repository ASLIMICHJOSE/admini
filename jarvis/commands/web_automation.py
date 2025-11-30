#!/usr/bin/env python3
"""
JARVIS Web Automation

Handles web browsing, search engine integration, and browser automation.
Supports multiple browsers and provides secure web access.
"""

import logging
import os
import platform
import subprocess
import time
import urllib.parse
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

try:
    import webbrowser
except ImportError:
    webbrowser = None

try:
    import selenium
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from selenium.webdriver.firefox.service import Service as FirefoxService
    from selenium.webdriver.firefox.options import Options as FirefoxOptions
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import WebDriverException, TimeoutException
except ImportError:
    selenium = None

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    requests = None
    BeautifulSoup = None

from config import WebConfig


@dataclass
class SearchResult:
    """Represents a search result."""
    title: str
    url: str
    description: str
    source: str
    timestamp: datetime


@dataclass
class BrowserTab:
    """Information about a browser tab."""
    title: str
    url: str
    handle: Any


class WebAutomation:
    """Handles web browsing and automation."""

    def __init__(self, config, logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.system = platform.system().lower()

        # Browser instances
        self.driver: Optional[webdriver.Remote] = None
        self.active_tabs: List[BrowserTab] = []

        # Browser preferences
        self.default_browser = getattr(config.web, 'default_browser', 'chrome').lower()
        self.headless_mode = getattr(config.web, 'headless_mode', False)
        self.search_results_count = getattr(config.web, 'search_results_count', 10)

        # Search engines
        self.search_engines = {
            "google": {
                "url": "https://www.google.com/search",
                "query_param": "q",
                "results_selector": "div.g"
            },
            "bing": {
                "url": "https://www.bing.com/search",
                "query_param": "q",
                "results_selector": "li.b_algo"
            },
            "duckduckgo": {
                "url": "https://duckduckgo.com/html/",
                "query_param": "q",
                "results_selector": ".result"
            }
        }

    def initialize(self) -> bool:
        """Initialize web automation."""
        try:
            self.logger.info("Initializing web automation...")

            # Check dependencies
            if webbrowser is None:
                self.logger.error("webbrowser library not available")
                return False

            if selenium is None:
                self.logger.warning("selenium not available, limited functionality")
                self.driver = None
            else:
                self.logger.info("selenium available for browser automation")

            if requests is None:
                self.logger.warning("requests library not available")
            if BeautifulSoup is None:
                self.logger.warning("BeautifulSoup not available")

            # Setup browser based on platform
            self._setup_browser()

            self.logger.info("Web automation initialized successfully")
            return True

        except Exception as e:
            self.logger.error(f"Failed to initialize web automation: {e}")
            return False

    def _setup_browser(self):
        """Setup browser for current platform."""
        try:
            if webbrowser:
                # Try to register browsers
                webbrowser.register(
                    'chrome',
                    None,
                    webbrowser.BackgroundBrowser(
                        self._get_chrome_path()
                    )
                )
                webbrowser.register(
                    'firefox',
                    None,
                    webbrowser.BackgroundBrowser(
                        self._get_firefox_path()
                    )
                )
                webbrowser.register(
                    'safari',
                    None,
                    webbrowser.BackgroundBrowser(
                        self._get_safari_path()
                    )
                )

            # Setup selenium driver if available
            if selenium and not self.headless_mode:
                self._setup_selenium_driver()

        except Exception as e:
            self.logger.warning(f"Browser setup issue: {e}")

    def _get_chrome_path(self) -> str:
        """Get Chrome executable path."""
        if self.system == "windows":
            paths = [
                "C:/Program Files/Google/Chrome/Application/chrome.exe",
                "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
                "chrome.exe"
            ]
        elif self.system == "darwin":
            paths = [
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                "/usr/bin/google-chrome"
            ]
        else:  # Linux
            paths = [
                "/usr/bin/google-chrome",
                "/usr/bin/chromium-browser",
                "/usr/bin/chromium",
                "google-chrome"
            ]

        for path in paths:
            if os.path.exists(path) or path == "google-chrome":
                return path

        return "chrome"  # Fallback to system PATH

    def _get_firefox_path(self) -> str:
        """Get Firefox executable path."""
        if self.system == "windows":
            paths = [
                "C:/Program Files/Mozilla Firefox/firefox.exe",
                "C:/Program Files (x86)/Mozilla Firefox/firefox.exe",
                "firefox.exe"
            ]
        elif self.system == "darwin":
            paths = [
                "/Applications/Firefox.app/Contents/MacOS/firefox",
                "/usr/bin/firefox"
            ]
        else:  # Linux
            paths = [
                "/usr/bin/firefox",
                "/usr/bin/firefox-esr",
                "firefox"
            ]

        for path in paths:
            if os.path.exists(path) or path == "firefox":
                return path

        return "firefox"  # Fallback to system PATH

    def _get_safari_path(self) -> str:
        """Get Safari executable path (macOS only)."""
        if self.system == "darwin":
            return "/Applications/Safari.app/Contents/MacOS/Safari"
        return "safari"

    def _setup_selenium_driver(self):
        """Setup Selenium WebDriver."""
        try:
            if self.default_browser == "chrome":
                chrome_options = ChromeOptions()
                
                if self.headless_mode:
                    chrome_options.add_argument("--headless")
                    chrome_options.add_argument("--disable-gpu")
                
                chrome_options.add_argument("--no-sandbox")
                chrome_options.add_argument("--disable-dev-shm-usage")
                chrome_options.add_argument("--disable-extensions")
                
                try:
                    service = ChromeService()
                    self.driver = webdriver.Chrome(service=service, options=chrome_options)
                    self.logger.info("Chrome WebDriver initialized")
                except WebDriverException as e:
                    self.logger.warning(f"Chrome WebDriver setup failed: {e}")
                    self.driver = None

            elif self.default_browser == "firefox":
                firefox_options = FirefoxOptions()
                
                if self.headless_mode:
                    firefox_options.add_argument("--headless")
                
                try:
                    service = FirefoxService()
                    self.driver = webdriver.Firefox(service=service, options=firefox_options)
                    self.logger.info("Firefox WebDriver initialized")
                except WebDriverException as e:
                    self.logger.warning(f"Firefox WebDriver setup failed: {e}")
                    self.driver = None

        except Exception as e:
            self.logger.error(f"Selenium setup failed: {e}")
            self.driver = None

    def search_google(self, command) -> Any:
        """Search Google for a query."""
        from jarvis.core.command_dispatcher import ExecutionResult
        
        query = command.entities.get("query", "").strip()
        
        if not query:
            return ExecutionResult(
                success=False,
                message="Search query is required",
                error="Missing search query parameter"
            )

        try:
            self.logger.info(f"Searching Google for: {query}")
            
            # Perform search
            search_results = self._perform_search("google", query)
            
            if search_results:
                # Open top result in browser
                top_result = search_results[0]
                self.open_website({"url": top_result.url})
                
                return ExecutionResult(
                    success=True,
                    message=f"Found {len(search_results)} results for '{query}'. Opening top result.",
                    data={
                        "query": query,
                        "results_count": len(search_results),
                        "top_result": top_result.url
                    }
                )
            else:
                return ExecutionResult(
                    success=False,
                    message=f"No search results found for: {query}",
                    error="No results returned"
                )

        except Exception as e:
            return ExecutionResult(
                success=False,
                message=f"Error searching Google: {str(e)}",
                error=str(e)
            )

    def search_youtube(self, command) -> Any:
        """Search YouTube for videos."""
        from jarvis.core.command_dispatcher import ExecutionResult
        
        query = command.entities.get("query", "").strip()
        
        if not query:
            return ExecutionResult(
                success=False,
                message="YouTube search query is required",
                error="Missing search query parameter"
            )

        try:
            self.logger.info(f"Searching YouTube for: {query}")
            
            # Construct YouTube search URL
            youtube_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"
            
            # Open YouTube search results
            if self.open_website({"url": youtube_url}):
                return ExecutionResult(
                    success=True,
                    message=f"Opening YouTube search results for: {query}",
                    data={
                        "query": query,
                        "url": youtube_url
                    }
                )
            else:
                return ExecutionResult(
                    success=False,
                    message="Failed to open YouTube",
                    error="Browser launch failed"
                )

        except Exception as e:
            return ExecutionResult(
                success=False,
                message=f"Error searching YouTube: {str(e)}",
                error=str(e)
            )

    def open_website(self, command) -> Any:
        """Open a specific website."""
        from jarvis.core.command_dispatcher import ExecutionResult
        
        url = command.entities.get("url", "").strip()
        
        if not url:
            return ExecutionResult(
                success=False,
                message="Website URL is required",
                error="Missing URL parameter"
            )

        try:
            self.logger.info(f"Opening website: {url}")
            
            # Validate and normalize URL
            normalized_url = self._normalize_url(url)
            
            # Open in browser
            if webbrowser:
                try:
                    webbrowser.open(normalized_url, new=2)  # Open in new tab
                    return ExecutionResult(
                        success=True,
                        message=f"Opened website: {normalized_url}",
                        data={"url": normalized_url}
                    )
                except Exception as e:
                    return ExecutionResult(
                        success=False,
                        message=f"Failed to open website: {str(e)}",
                        error=str(e)
                    )
            else:
                return ExecutionResult(
                    success=False,
                    message="Web browser functionality not available",
                    error="Missing webbrowser library"
                )

        except Exception as e:
            return ExecutionResult(
                success=False,
                message=f"Error opening website: {str(e)}",
                error=str(e)
            )

    def _normalize_url(self, url: str) -> str:
        """Normalize and validate URL."""
        if not url:
            return ""
        
        # Add protocol if missing
        if not url.startswith(('http://', 'https://')):
            if '://' in url:
                protocol, rest = url.split('://', 1)
                return f"http://{rest}"
            else:
                return f"http://{url}"
        
        return url

    def _perform_search(self, engine: str, query: str) -> List[SearchResult]:
        """Perform search using specified engine."""
        try:
            if selenium and self.driver:
                # Use Selenium for detailed search results
                return self._selenium_search(engine, query)
            elif requests and BeautifulSoup:
                # Use requests + BeautifulSoup for basic search
                return self._requests_search(engine, query)
            else:
                # Fallback to basic web browser search
                return self._browser_search(engine, query)

        except Exception as e:
            self.logger.error(f"Search error: {e}")
            return []

    def _selenium_search(self, engine: str, query: str) -> List[SearchResult]:
        """Perform search using Selenium."""
        try:
            engine_config = self.search_engines.get(engine)
            if not engine_config:
                engine_config = self.search_engines["google"]  # Fallback to Google

            search_url = f"{engine_config['url']}?{engine_config['query_param']}={urllib.parse.quote(query)}"
            
            self.driver.get(search_url)
            time.sleep(2)  # Wait for results to load

            results = []
            result_elements = self.driver.find_elements(By.CSS_SELECTOR, engine_config["results_selector"])
            
            for element in result_elements[:self.search_results_count]:
                try:
                    title_element = element.find_element(By.TAG_NAME, "h3") or element.find_element(By.CSS_SELECTOR, "h3")
                    link_element = element.find_element(By.TAG_NAME, "a")
                    
                    title = title_element.text.strip()
                    url = link_element.get_attribute("href")
                    
                    if title and url:
                        results.append(SearchResult(
                            title=title,
                            url=url,
                            description="",
                            source=engine,
                            timestamp=datetime.now()
                        ))
                except Exception:
                    continue

            return results

        except Exception as e:
            self.logger.error(f"Selenium search failed: {e}")
            return []

    def _requests_search(self, engine: str, query: str) -> List[SearchResult]:
        """Perform search using requests library."""
        try:
            engine_config = self.search_engines.get(engine)
            if not engine_config:
                return []

            search_url = f"{engine_config['url']}?{engine_config['query_param']}={urllib.parse.quote(query)}"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(search_url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            results = []
            
            # This is simplified - real implementation would need engine-specific parsing
            for link in soup.find_all('a', href=True)[:self.search_results_count]:
                href = link.get('href')
                text = link.get_text().strip()
                
                if href and text and href.startswith('http'):
                    results.append(SearchResult(
                        title=text,
                        url=href,
                        description="",
                        source=engine,
                        timestamp=datetime.now()
                    ))

            return results

        except Exception as e:
            self.logger.error(f"Requests search failed: {e}")
            return []

    def _browser_search(self, engine: str, query: str) -> List[SearchResult]:
        """Perform search by opening in browser."""
        try:
            engine_config = self.search_engines.get(engine)
            if not engine_config:
                return []

            search_url = f"{engine_config['url']}?{engine_config['query_param']}={urllib.parse.quote(query)}"
            
            # Open search results in browser
            if webbrowser.open(search_url, new=2):
                return [SearchResult(
                    title=f"Search {query} on {engine}",
                    url=search_url,
                    description=f"Browser opened with search results",
                    source=engine,
                    timestamp=datetime.now()
                )]
            else:
                return []

        except Exception as e:
            self.logger.error(f"Browser search failed: {e}")
            return []

    def scrape_webpage(self, url: str, selector: Optional[str] = None) -> Optional[str]:
        """Scrape content from a webpage."""
        try:
            self.logger.info(f"Scraping webpage: {url}")
            
            if selenium and self.driver:
                return self._selenium_scrape(url, selector)
            elif requests and BeautifulSoup:
                return self._requests_scrape(url, selector)
            else:
                self.logger.warning("Web scraping not available - missing dependencies")
                return None

        except Exception as e:
            self.logger.error(f"Web scraping error: {e}")
            return None

    def _selenium_scrape(self, url: str, selector: Optional[str]) -> Optional[str]:
        """Scrape using Selenium."""
        try:
            self.driver.get(url)
            time.sleep(2)  # Wait for page to load

            if selector:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    return elements[0].text
            else:
                # Get page text
                return self.driver.find_element(By.TAG_NAME, "body").text

        except Exception as e:
            self.logger.error(f"Selenium scraping failed: {e}")
            return None

    def _requests_scrape(self, url: str, selector: Optional[str]) -> Optional[str]:
        """Scrape using requests and BeautifulSoup."""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            if selector:
                elements = soup.select(selector)
                if elements:
                    return elements[0].get_text().strip()
            else:
                return soup.get_text()

        except Exception as e:
            self.logger.error(f"Requests scraping failed: {e}")
            return None

    def test(self) -> bool:
        """Test web automation functionality."""
        try:
            self.logger.info("Testing web automation...")
            
            # Test webbrowser
            if webbrowser:
                self.logger.info("✅ Web browser module - AVAILABLE")
            else:
                self.logger.error("❌ Web browser module - NOT AVAILABLE")
                return False

            # Test selenium
            if selenium:
                self.logger.info("✅ Selenium - AVAILABLE")
                if self.driver:
                    self.logger.info("✅ Selenium WebDriver - INITIALIZED")
                else:
                    self.logger.warning("⚠️  Selenium WebDriver - NOT INITIALIZED")
            else:
                self.logger.warning("⚠️  Selenium - NOT AVAILABLE")

            # Test requests and BeautifulSoup
            if requests:
                self.logger.info("✅ Requests - AVAILABLE")
            else:
                self.logger.warning("⚠️  Requests - NOT AVAILABLE")

            if BeautifulSoup:
                self.logger.info("✅ BeautifulSoup - AVAILABLE")
            else:
                self.logger.warning("⚠️  BeautifulSoup - NOT AVAILABLE")

            # Test simple search
            test_results = self._perform_search("google", "test")
            if test_results:
                self.logger.info("✅ Web search - WORKING")
            else:
                self.logger.warning("⚠️  Web search - LIMITED")

            self.logger.info("Web automation tests completed")
            return True

        except Exception as e:
            self.logger.error(f"Web automation test failed: {e}")
            return False

    def shutdown(self):
        """Shutdown web automation resources."""
        self.logger.info("Shutting down web automation...")

        # Close Selenium driver
        if self.driver:
            try:
                self.driver.quit()
                self.driver = None
                self.logger.info("Selenium WebDriver closed")
            except Exception as e:
                self.logger.error(f"Error closing WebDriver: {e}")

        self.logger.info("Web automation shutdown complete")
