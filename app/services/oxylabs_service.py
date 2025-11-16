import logging
import requests
import time
import asyncio
import base64
import platform
import subprocess
import os
import shutil
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Optional, Any
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.os_manager import ChromeType
from urllib.parse import urljoin
from app.core.config import settings

logger = logging.getLogger(__name__)

class OxylabsService:
    def __init__(self):
        self.username = settings.OXYLABS_USERNAME
        self.password = settings.OXYLABS_PASSWORD
        self.proxy_url = "unblock.oxylabs.io:60000"
        self.proxy = f'http://{self.username}:{self.password}@{self.proxy_url}'
        self._executor = ThreadPoolExecutor(max_workers=15)
        self._check_chrome_installation()
    
    def _check_chrome_installation(self):
        """Check if Chrome is installed"""
        self.system = platform.system().lower()
        self.chrome_available = False
        
        if self.system == 'linux':
            try:
                # Check if Chrome is installed
                result = subprocess.run(['which', 'google-chrome'], capture_output=True, text=True)
                
                if result.returncode != 0:
                    logger.warning("Chrome not found on Ubuntu. Selenium scraping will not be available.")
                    logger.info("To install Chrome manually, run: apt-get update && apt-get install -y google-chrome-stable")
                    self.chrome_available = False
                else:
                    logger.info("Google Chrome is already installed")
                    self.chrome_available = True
            except Exception as e:
                logger.error(f"Error checking Chrome installation: {str(e)}")
                self.chrome_available = False
        else:
            # On Mac/Windows, assume Chrome is available
            self.chrome_available = True
    
    def scrape_url(self, url: str, method: str = 'GET', headers: Optional[Dict] = None, 
                        params: Optional[Dict] = None, data: Optional[Dict] = None) -> str:
        """
        Scrape a URL using Oxylabs proxy service - ENHANCED WITH BETTER ERROR HANDLING
        
        Args:
            url: Target URL to scrape
            method: HTTP method (GET, POST, etc.)
            headers: Optional request headers
            params: Optional URL parameters
            data: Optional request body data
            
        Returns:
            str: HTML content of the response
        
        Raises:
            Exception: If the request fails after all retries
        """
        max_retries = 3
        retry_count = 0
        
        # Enhanced headers for better success rate
        enhanced_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0',
        }
        
        # Merge with provided headers
        if headers:
            enhanced_headers.update(headers)
        
        while retry_count < max_retries:
            try:
                logger.info(f"🔍 Oxylabs scraping URL: {url} (attempt {retry_count + 1}/{max_retries})")
                
                response = requests.request(
                    method=method,
                    url=url,
                    headers=enhanced_headers,
                    params=params,
                    data=data,
                    proxies={'http': self.proxy, 'https': self.proxy},
                    verify=False,  # Ignore SSL certificate verification
                    timeout=30
                )
                
                # Check if response is successful
                if response.status_code == 200:
                    logger.info(f"✅ Oxylabs scraping SUCCESS: {len(response.text)} chars for {url}")
                    return response.text
                else:
                    logger.warning(f"⚠️ Oxylabs returned status {response.status_code} for {url}")
                    response.raise_for_status()
                    
            except requests.exceptions.Timeout as e:
                retry_count += 1
                logger.error(f"⏰ Timeout error scraping URL {url} (attempt {retry_count}/{max_retries}): {str(e)}")
                if retry_count >= max_retries:
                    raise Exception(f"Oxylabs timeout after {max_retries} attempts: {str(e)}")
                time.sleep(3)  # Longer wait for timeouts
                
            except requests.exceptions.ConnectionError as e:
                retry_count += 1
                logger.error(f"🔌 Connection error scraping URL {url} (attempt {retry_count}/{max_retries}): {str(e)}")
                if retry_count >= max_retries:
                    raise Exception(f"Oxylabs connection error after {max_retries} attempts: {str(e)}")
                time.sleep(2)
                
            except requests.exceptions.HTTPError as e:
                retry_count += 1
                logger.error(f"🌐 HTTP error scraping URL {url} (attempt {retry_count}/{max_retries}): {str(e)}")
                if retry_count >= max_retries:
                    raise Exception(f"Oxylabs HTTP error after {max_retries} attempts: {str(e)}")
                time.sleep(2)
                
            except Exception as e:
                retry_count += 1
                logger.error(f"❌ Unexpected error scraping URL {url} (attempt {retry_count}/{max_retries}): {str(e)}")
                if retry_count >= max_retries:
                    raise Exception(f"Oxylabs failed after {max_retries} attempts: {str(e)}")
                time.sleep(2)
        
        # This should never be reached, but just in case
        raise Exception(f"Oxylabs scraping failed for {url} after {max_retries} attempts")
    
    def scrape_url_with_selenium(self, url: str, method: str = 'GET', headers: Optional[Dict] = None, 
                        params: Optional[Dict] = None, data: Optional[Dict] = None) -> str:
        """
        Scrape a URL using Selenium with Oxylabs proxy service
        
        Args:
            url: Target URL to scrape
            method: HTTP method (GET, POST, etc.) - Note: Selenium primarily uses GET
            headers: Optional request headers
            params: Optional URL parameters - Will be appended to the URL
            data: Optional request body data - Not used with Selenium GET requests
            
        Returns:
            str: HTML content of the response
        
        Raises:
            Exception: If the scraping fails
        """
        # Check if Chrome is available
        if not self.chrome_available:
            logger.warning("Chrome not available on this system, falling back to regular scraping")
            return self.scrape_url(url, method, headers, params, data)
        
        max_retries = 2  # Reduced from 3 to 2
        retry_count = 0
        driver = None
        
        # If params are provided, append them to the URL
        if params:
            from urllib.parse import urlencode
            param_string = urlencode(params)
            url = f"{url}?{param_string}" if '?' not in url else f"{url}&{param_string}"
        
        while retry_count < max_retries:
            try:
                logger.info(f"Scraping URL with Selenium: {url}")
                
                # Configure Chrome options for maximum performance
                options = Options()
                options.add_argument('--headless')
                options.add_argument('--no-sandbox')
                options.add_argument('--disable-dev-shm-usage')
                options.add_argument('--disable-gpu')
                options.add_argument('--disable-extensions')
                options.add_argument('--disable-infobars')
                options.add_argument('--disable-notifications')
                options.add_argument('--disable-popup-blocking')
                # Add a modern user agent
                options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36')
                # Don't disable images as they might be important for content detection
                # options.add_argument('--blink-settings=imagesEnabled=false')
                # Don't disable JavaScript as it's needed for dynamic content
                # options.add_argument('--disable-javascript')
                options.add_argument('--window-size=1920,1080')  # Full-size window for better rendering
                
                # Set up proxy - Use a simpler approach with direct proxy string
                proxy = {
                    'proxy': {
                        'http': self.proxy,
                        'https': self.proxy,
                        'no_proxy': 'localhost,127.0.0.1'
                    }
                }
                
                # Add custom headers if provided
                if headers:
                    for key, value in headers.items():
                        options.add_argument(f'--header={key}: {value}')
                
                # Initialize the Chrome driver with a cached ChromeDriver
                try:
                    if self.system == 'linux':
                        # On Linux, specify the Chrome binary path
                        chrome_path = subprocess.run(
                            ['which', 'google-chrome'], 
                            capture_output=True, 
                            text=True
                        ).stdout.strip()
                        
                        options.binary_location = chrome_path
                        service = Service(ChromeDriverManager(chrome_type=ChromeType.GOOGLE).install())
                    else:
                        # On Mac/Windows
                        service = Service(ChromeDriverManager().install())
                        
                    driver = webdriver.Chrome(service=service, options=options)
                except Exception as driver_error:
                    logger.error(f"Failed to initialize Chrome driver: {str(driver_error)}")
                    # Fall back to regular scraping
                    return self.scrape_url(url, method, headers, params, data)
                
                # Try a different approach for proxy - use a direct request to configure proxy
                # This is a workaround for Selenium's limitations with authenticated proxies
                try:
                    # First try to access the target URL without the proxy to test if it works directly
                    direct_url = url
                    driver.get(direct_url)
                    
                    # If we're here, direct access worked - no need for proxy
                    logger.info(f"Direct access to {url} successful, not using proxy")
                except Exception as direct_error:
                    logger.warning(f"Direct access failed, falling back to regular scraping: {str(direct_error)}")
                    # Close the driver and fall back to regular scraping
                    driver.quit()
                    return self.scrape_url(url, method, headers, params, data)
                
                # Set shorter page load timeout
                driver.set_page_load_timeout(30)  # Reduced from 60 to 30 seconds
                
                # Navigate to the URL
                driver.get(url)
                
                # Wait for the page to load - with better waiting mechanism
                try:
                    # First wait for document ready state
                    WebDriverWait(driver, 15).until(
                        lambda d: d.execute_script('return document.readyState') == 'complete'
                    )
                    
                    # Then wait for network to be idle (no more than 2 connections for 500ms)
                    time.sleep(3)  # Initial wait for JavaScript to start loading content
                    
                    # Try to detect common loading indicators
                    loading_indicators = ["Loading", "Please wait", "Loading...", "LOADING"]
                    has_loading = any(indicator in driver.page_source for indicator in loading_indicators)
                    
                    if has_loading:
                        logger.info(f"Detected loading indicator, waiting longer for {url}")
                        # Wait longer for content to load
                        time.sleep(7)
                        
                        # Scroll down to trigger lazy loading
                        driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
                        time.sleep(2)
                        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                        time.sleep(2)
                        driver.execute_script("window.scrollTo(0, 0);")
                        time.sleep(1)
                    
                    # Additional check for dynamic content - wait for DOM to stabilize
                    initial_dom_size = len(driver.page_source)
                    time.sleep(2)
                    final_dom_size = len(driver.page_source)
                    
                    # If DOM is still changing, wait a bit more
                    if final_dom_size > initial_dom_size + 500:  # If more than 500 chars added
                        logger.info(f"DOM still changing, waiting more time for {url}")
                        time.sleep(5)
                        
                except Exception as wait_error:
                    # If timeout, just continue with what we have
                    logger.warning(f"Timeout or error waiting for page to load completely: {url} - {str(wait_error)}")
                    pass
                
                # Get the page source after all waiting
                page_source = driver.page_source
                
                # Check if we still have loading indicators
                if "Loading" in page_source and len(page_source) < 5000:
                    logger.warning(f"Page still shows loading indicators, may not be fully loaded: {url}")
                
                # Close the driver
                driver.quit()
                driver = None
                logger.info(f"Successfully scraped URL with Selenium: {url}")
                # Don't log the entire HTML content as it's too large
                # logger.info(page_source)
                return page_source
                
            except Exception as e:
                retry_count += 1
                logger.error(f"Error scraping URL with Selenium {url} (attempt {retry_count}/{max_retries}): {str(e)}")
                
                if driver:
                    try:
                        driver.quit()
                    except:
                        pass
                    driver = None
                
                if retry_count >= max_retries:
                    # If all retries fail, fall back to regular scraping
                    logger.warning(f"Selenium scraping failed, falling back to regular scraping for {url}")
                    try:
                        return self.scrape_url(url, method, headers, params, data)
                    except Exception as fallback_error:
                        logger.error(f"Fallback scraping also failed for {url}: {str(fallback_error)}")
                        raise
                
                time.sleep(1)  # Reduced from 2 to 1 second
    
    async def async_scrape_url_with_selenium(self, url: str, method: str = 'GET', headers: Optional[Dict] = None, 
                        params: Optional[Dict] = None, data: Optional[Dict] = None) -> str:
        """
        Async version of scrape_url_with_selenium
        """
        # If params are provided, append them to the URL
        if params:
            from urllib.parse import urlencode
            param_string = urlencode(params)
            url = f"{url}?{param_string}" if '?' not in url else f"{url}&{param_string}"
        
        # Run the Selenium scraping in a thread pool to avoid blocking
        return await asyncio.get_event_loop().run_in_executor(
            self._executor, 
            self._selenium_scrape_worker,
            url, headers
        )
    
    def _selenium_scrape_worker(self, url: str, headers: Optional[Dict] = None) -> str:
        """
        Worker function that runs in a thread to handle Selenium scraping
        """
        max_retries = 3
        retry_count = 0
        driver = None
        
        while retry_count < max_retries:
            try:
                logger.info(f"Scraping URL with Selenium: {url}")
                
                # Configure Chrome options
                options = Options()
                options.add_argument('--headless')  # Run in headless mode
                options.add_argument('--no-sandbox')
                options.add_argument('--disable-dev-shm-usage')
                options.add_argument('--disable-gpu')
                options.add_argument('--window-size=1920,1080')
                
                # Set up proxy - Use a simpler approach with direct proxy string
                proxy = {
                    'proxy': {
                        'http': self.proxy,
                        'https': self.proxy,
                        'no_proxy': 'localhost,127.0.0.1'
                    }
                }
                
                # Add custom headers if provided
                if headers:
                    for key, value in headers.items():
                        options.add_argument(f'--header={key}: {value}')
                
                # Initialize the Chrome driver
                try:
                    if self.system == 'linux':
                        # On Linux, specify the Chrome binary path
                        chrome_path = subprocess.run(
                            ['which', 'google-chrome'], 
                            capture_output=True, 
                            text=True
                        ).stdout.strip()
                        
                        options.binary_location = chrome_path
                        service = Service(ChromeDriverManager(chrome_type=ChromeType.GOOGLE).install())
                    else:
                        # On Mac/Windows
                        service = Service(ChromeDriverManager().install())
                        
                    driver = webdriver.Chrome(service=service, options=options)
                except Exception as driver_error:
                    logger.error(f"Failed to initialize Chrome driver: {str(driver_error)}")
                    # Fall back to regular scraping
                    return self.scrape_url(url, method, headers, params, data)
                
                # Try a different approach for proxy - use a direct request to configure proxy
                # This is a workaround for Selenium's limitations with authenticated proxies
                try:
                    # First try to access the target URL without the proxy to test if it works directly
                    direct_url = url
                    driver.get(direct_url)
                    
                    # If we're here, direct access worked - no need for proxy
                    logger.info(f"Direct access to {url} successful, not using proxy")
                except Exception as direct_error:
                    logger.warning(f"Direct access failed, falling back to regular scraping: {str(direct_error)}")
                    # Close the driver and fall back to regular scraping
                    driver.quit()
                    return self.scrape_url(url, method, headers, params, data)
                
                # Set page load timeout
                driver.set_page_load_timeout(60)  # 60 seconds timeout
                
                # Navigate to the URL
                driver.get(url)
                
                # Wait for the page to load completely
                # Wait for the document to be in ready state
                WebDriverWait(driver, 30).until(
                    lambda d: d.execute_script('return document.readyState') == 'complete'
                )
                
                # Additional wait to allow JavaScript to render content
                time.sleep(5)
                
                # Get the page source
                page_source = driver.page_source
                
                # Close the driver
                driver.quit()
                driver = None
                
                return page_source
                
            except Exception as e:
                retry_count += 1
                logger.error(f"Error scraping URL with Selenium {url} (attempt {retry_count}/{max_retries}): {str(e)}")
                
                if driver:
                    try:
                        driver.quit()
                    except:
                        pass
                    driver = None
                
                if retry_count >= max_retries:
                    raise
                
                time.sleep(2)  # Wait before retrying

    def save_response_to_file(self, html_content: str, filename: str) -> None:
        """
        Save response content to a file
        
        Args:
            html_content: HTML content to save
            filename: Name of file to save content to
        """
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(html_content)
        except IOError as e:
            logger.error(f"Error saving response to file {filename}: {str(e)}")
            raise
