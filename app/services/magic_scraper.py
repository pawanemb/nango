#!/usr/bin/env python3

import asyncio
import argparse
import json
import sys
from typing import Optional, Dict, Any

# Try to import the working config classes, fallback if not available
# DEBUG: Add detailed import debugging
print(f"🔍 [DEBUG] Python executable: {sys.executable}")
print(f"🔍 [DEBUG] Python path: {sys.path[:3]}...")  # Show first 3 paths
print(f"🔍 [DEBUG] Attempting to import crawl4ai...")

try:
    print(f"🔍 [DEBUG] Step 1: Importing AsyncWebCrawler from crawl4ai...")
    from crawl4ai import AsyncWebCrawler
    print(f"✅ [DEBUG] AsyncWebCrawler imported successfully")
    
    print(f"🔍 [DEBUG] Step 2: Importing async_configs...")
    from crawl4ai.async_configs import BrowserConfig, CrawlerRunConfig, CacheMode
    print(f"✅ [DEBUG] async_configs imported successfully")
    
    CRAWL4AI_AVAILABLE = True
    USING_ASYNC_CONFIGS = True
    print(f"✅ [DEBUG] crawl4ai fully available with async_configs")
    
except ImportError as e1:
    print(f"⚠️ [DEBUG] async_configs import failed: {e1}")
    print(f"🔍 [DEBUG] Trying fallback import without async_configs...")
    
    try:
        print(f"🔍 [DEBUG] Step 3: Importing basic crawl4ai components...")
        from crawl4ai import AsyncWebCrawler, CacheMode
        print(f"✅ [DEBUG] Basic crawl4ai imported successfully")
        
        CRAWL4AI_AVAILABLE = True
        USING_ASYNC_CONFIGS = False
        print(f"⚠️ [DEBUG] crawl4ai available but without async_configs")
        
        # Mock the config classes for fallback
        class BrowserConfig:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)
        
        class CrawlerRunConfig:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)
                    
        print(f"✅ [DEBUG] Mock config classes created")
        
    except ImportError as e2:
        print(f"❌ [DEBUG] All crawl4ai imports failed!")
        print(f"❌ [DEBUG] First error (async_configs): {e1}")
        print(f"❌ [DEBUG] Second error (basic): {e2}")
        print(f"🔍 [DEBUG] Checking if crawl4ai package exists...")
        
        try:
            import crawl4ai
            print(f"✅ [DEBUG] crawl4ai package found at: {crawl4ai.__file__}")
            print(f"🔍 [DEBUG] crawl4ai version: {getattr(crawl4ai, '__version__', 'unknown')}")
            print(f"🔍 [DEBUG] crawl4ai dir contents: {dir(crawl4ai)}")
        except ImportError as e3:
            print(f"❌ [DEBUG] crawl4ai package not found: {e3}")
            
        # Check pip list
        import subprocess
        try:
            print(f"🔍 [DEBUG] Checking pip list for crawl4ai...")
            result = subprocess.run([sys.executable, '-m', 'pip', 'list'], 
                                  capture_output=True, text=True, timeout=30)
            pip_output = result.stdout
            if 'crawl4ai' in pip_output.lower():
                print(f"✅ [DEBUG] Found crawl4ai in pip list:")
                for line in pip_output.split('\n'):
                    if 'crawl4ai' in line.lower():
                        print(f"    {line}")
            else:
                print(f"❌ [DEBUG] crawl4ai not found in pip list")
                print(f"🔍 [DEBUG] Showing all installed packages with 'crawl' in name:")
                for line in pip_output.split('\n'):
                    if 'crawl' in line.lower():
                        print(f"    {line}")
        except Exception as pip_error:
            print(f"❌ [DEBUG] Error checking pip list: {pip_error}")
        
        AsyncWebCrawler = None
        BrowserConfig = None
        CrawlerRunConfig = None
        CacheMode = None
        CRAWL4AI_AVAILABLE = False
        USING_ASYNC_CONFIGS = False
        print(f"❌ [DEBUG] crawl4ai marked as unavailable")

class EnhancedMagicScraper:
    """Enhanced web scraper with multiple fallback strategies"""
    
    def __init__(self, verbose: bool = False, headless: bool = True, skip_images: bool = True):
        if not CRAWL4AI_AVAILABLE:
            raise ImportError("crawl4ai is not properly installed or configured")
        
        print(f"🔍 [DEBUG] Initializing EnhancedMagicScraper...")
        print(f"🔍 [DEBUG] Checking Playwright installation...")
        
        # Check Playwright installation
        try:
            import subprocess
            print(f"🔍 [DEBUG] Checking if Playwright browsers are installed...")
            
            # First check if playwright command is available
            result = subprocess.run([sys.executable, '-m', 'playwright', '--version'], 
                                  capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                print(f"✅ [DEBUG] Playwright version: {result.stdout.strip()}")
                
                # Check if browsers are installed by testing a simple command
                print(f"🔍 [DEBUG] Checking browser installations...")
                browser_check = subprocess.run([sys.executable, '-m', 'playwright', 'install', '--dry-run'], 
                                             capture_output=True, text=True, timeout=30)
                print(f"🔍 [DEBUG] Browser check output: {browser_check.stdout[:200]}...")
                
                # If browsers are missing, install them
                if 'would install' in browser_check.stdout.lower() or browser_check.returncode != 0:
                    print(f"⚠️ [DEBUG] Playwright browsers not installed, attempting installation...")
                    install_result = subprocess.run([sys.executable, '-m', 'playwright', 'install'], 
                                                   capture_output=True, text=True, timeout=300)  # 5 minute timeout
                    if install_result.returncode == 0:
                        print(f"✅ [DEBUG] Playwright browsers installed successfully")
                    else:
                        print(f"❌ [DEBUG] Playwright browser installation failed: {install_result.stderr}")
                else:
                    print(f"✅ [DEBUG] Playwright browsers are already installed")
            else:
                print(f"❌ [DEBUG] Playwright not available: {result.stderr}")
                
        except Exception as e:
            print(f"⚠️ [DEBUG] Playwright setup check failed: {e}")
            print(f"🔍 [DEBUG] This may cause crawl4ai to fail with missing node binary error")
            
        # Check crawl4ai setup
        try:
            print(f"🔍 [DEBUG] Testing AsyncWebCrawler initialization...")
            # Don't actually create the crawler yet, just test the imports work
            print(f"✅ [DEBUG] AsyncWebCrawler class available: {AsyncWebCrawler is not None}")
        except Exception as e:
            print(f"❌ [DEBUG] AsyncWebCrawler test failed: {e}")
            
        self.verbose = verbose
        self.headless = headless
        self.skip_images = skip_images
        print(f"✅ [DEBUG] EnhancedMagicScraper initialized successfully")
        
    async def scrape_with_magic_mode(self, url: str, skip_images: bool = True) -> Optional[Dict[str, Any]]:
        """
        Basic Magic Mode scraping - handles most cases
        """
        if self.verbose:
            print(f"🪄 Attempting Magic Mode scraping: {url}")
            if skip_images:
                print("🖼️ Skipping images for faster loading...")
        
        if USING_ASYNC_CONFIGS:
            # Use the working async_configs approach
            browser_config = BrowserConfig(
                headless=self.headless,
                verbose=self.verbose
            )
            
            run_config = CrawlerRunConfig(
                magic=True,  # Enables ALL anti-detection features
                exclude_external_images=skip_images,
                wait_for_images=not skip_images,  # Don't wait for images if skipping
                cache_mode=CacheMode.BYPASS
            )
            
            async with AsyncWebCrawler(config=browser_config) as crawler:
                try:
                    result = await crawler.arun(url, config=run_config)
                    
                    if result.success and len(result.markdown or "") > 100:
                        return {
                            "success": True,
                            "content": result.markdown,
                            "title": getattr(result, 'title', 'N/A'),
                            "method": "Magic Mode"
                        }
                        
                except Exception as e:
                    if self.verbose:
                        print(f"⚠️ Magic Mode error: {e}")
        else:
            # Fallback to direct API
            async with AsyncWebCrawler(verbose=self.verbose) as crawler:
                try:
                    result = await crawler.arun(
                        url=url,
                        cache_mode=CacheMode.BYPASS,
                        word_count_threshold=10,
                        delay_before_return_html=2.0,
                        wait_for="domcontentloaded"
                    )
                    
                    if result.success and result.markdown and len(result.markdown.strip()) > 100:
                        return {
                            "success": True,
                            "content": result.markdown.strip(),
                            "title": getattr(result, 'title', 'N/A'),
                            "method": "Magic Mode"
                        }
                        
                except Exception as e:
                    if self.verbose:
                        print(f"⚠️ Magic Mode error: {e}")
                        
        return None
    
    async def scrape_with_enhanced_wait(self, url: str, skip_images: bool = True) -> Optional[Dict[str, Any]]:
        """
        Enhanced waiting strategy using working implementation
        """
        if self.verbose:
            print(f"⏳ Attempting enhanced wait strategy: {url}")
        
        # Use the working JavaScript code from WorkingMagicScraper
        js_code = """
        // Wait for loading indicators to disappear and content to load
        async function waitForContent() {
            const maxWaitTime = 30000; // 30 seconds max
            const checkInterval = 500; // Check every 500ms
            let elapsed = 0;
            
            while (elapsed < maxWaitTime) {
                // Check if common loading indicators are gone
                const loadingElements = document.querySelectorAll(
                    '.loading, .spinner, .loader, [class*="loading"], [class*="spinner"]'
                );
                
                const visibleLoaders = Array.from(loadingElements).filter(el => {
                    const style = window.getComputedStyle(el);
                    return style.display !== 'none' && style.visibility !== 'hidden';
                });
                
                // Check if we have meaningful content
                const bodyText = document.body ? document.body.innerText.trim() : '';
                const hasContent = bodyText.length > 100;
                
                // If no visible loaders and we have content, we're done
                if (visibleLoaders.length === 0 && hasContent) {
                    console.log('Content loaded successfully');
                    break;
                }
                
                await new Promise(resolve => setTimeout(resolve, checkInterval));
                elapsed += checkInterval;
            }
            
            // Scroll to trigger any lazy loading
            window.scrollTo(0, document.body.scrollHeight);
            await new Promise(resolve => setTimeout(resolve, 1000));
            window.scrollTo(0, 0);
            
            return 'Content ready';
        }
        
        return await waitForContent();
        """
        
        async with AsyncWebCrawler(verbose=self.verbose) as crawler:
            try:
                result = await crawler.arun(
                    url=url,
                    cache_mode=CacheMode.BYPASS,
                    js_code=js_code,
                    wait_for="networkidle",  # Wait for network to be idle
                    delay_before_return_html=3.0,  # Wait 3 seconds after JS execution
                    word_count_threshold=10  # Low threshold to capture content
                )
                
                if result.success and result.markdown and len(result.markdown.strip()) > 50:
                    if self.verbose:
                        print(f"✅ Enhanced wait success: {len(result.markdown)} chars")
                    
                    return {
                        "success": True,
                        "content": result.markdown.strip(),
                        "title": getattr(result, 'title', 'N/A'),
                        "method": "Enhanced Wait"
                    }
                elif self.verbose:
                    print(f"⚠️ Content too short: {len(result.markdown or '')} chars")
                    print(f"Raw markdown: {repr(result.markdown)}")
                    
            except Exception as e:
                if self.verbose:
                    print(f"❌ Enhanced wait error: {e}")
                        
        return None
    
    async def scrape_with_progressive_scroll(self, url: str, skip_images: bool = True) -> Optional[Dict[str, Any]]:
        """
        Progressive scrolling for infinite scroll or lazy-loaded content
        """
        if self.verbose:
            print(f"📜 Attempting progressive scroll strategy: {url}")
        
        if USING_ASYNC_CONFIGS:
            # Use the working async_configs approach
            browser_config = BrowserConfig(
                headless=self.headless,
                verbose=self.verbose
            )
            
            # JavaScript for progressive scrolling
            js_scroll_code = """
            (async () => {
                const scrollStep = 300;
                const scrollDelay = 500;
                let lastHeight = 0;
                let sameHeightCount = 0;
                
                while (sameHeightCount < 3) {
                    // Scroll down
                    window.scrollBy(0, scrollStep);
                    await new Promise(r => setTimeout(r, scrollDelay));
                    
                    // Check if new content loaded
                    const currentHeight = document.body.scrollHeight;
                    if (currentHeight === lastHeight) {
                        sameHeightCount++;
                    } else {
                        sameHeightCount = 0;
                        lastHeight = currentHeight;
                    }
                }
                
                // Scroll back to top
                window.scrollTo(0, 0);
                await new Promise(r => setTimeout(r, 1000));
            })();
            """
            
            run_config = CrawlerRunConfig(
                magic=True,
                js_code=js_scroll_code,
                wait_until="networkidle",
                delay_before_return_html=3.0,
                scan_full_page=True,
                cache_mode=CacheMode.BYPASS
            )
            
            async with AsyncWebCrawler(config=browser_config) as crawler:
                try:
                    result = await crawler.arun(url, config=run_config)
                    
                    if result.success and len(result.markdown or "") > 100:
                        return {
                            "success": True,
                            "content": result.markdown,
                            "title": getattr(result, 'title', 'N/A'),
                            "method": "Progressive Scroll"
                        }
                        
                except Exception as e:
                    if self.verbose:
                        print(f"⚠️ Progressive scroll error: {e}")
        else:
            # Fallback with simple scroll
            js_scroll_code = """
            window.scrollTo(0, document.body.scrollHeight);
            await new Promise(r => setTimeout(r, 2000));
            window.scrollTo(0, 0);
            """
            
            async with AsyncWebCrawler(verbose=self.verbose) as crawler:
                try:
                    result = await crawler.arun(
                        url=url,
                        cache_mode=CacheMode.BYPASS,
                        word_count_threshold=10,
                        js_code=js_scroll_code,
                        delay_before_return_html=5.0,
                        wait_for="networkidle"
                    )
                    
                    if result.success and result.markdown and len(result.markdown.strip()) > 100:
                        return {
                            "success": True,
                            "content": result.markdown.strip(),
                            "title": getattr(result, 'title', 'N/A'),
                            "method": "Progressive Scroll"
                        }
                        
                except Exception as e:
                    if self.verbose:
                        print(f"⚠️ Progressive scroll error: {e}")
                        
        return None
    
    async def scrape_with_persistent_session(self, url: str, skip_images: bool = True) -> Optional[Dict[str, Any]]:
        """
        Use persistent browser session for sites requiring cookies/session
        """
        if self.verbose:
            print(f"🍪 Attempting persistent session strategy: {url}")
        
        if USING_ASYNC_CONFIGS:
            # Use the working async_configs approach
            browser_config = BrowserConfig(
                headless=self.headless,
                verbose=self.verbose,
                use_persistent_context=True,
                user_data_dir="./browser_profile"
            )
            
            run_config = CrawlerRunConfig(
                magic=True,
                wait_until="networkidle",
                delay_before_return_html=10.0,  # Longer delay for session-based sites
                simulate_user=True,
                override_navigator=True,
                cache_mode=CacheMode.BYPASS
            )
            
            async with AsyncWebCrawler(config=browser_config) as crawler:
                try:
                    result = await crawler.arun(url, config=run_config)
                    
                    if result.success and len(result.markdown or "") > 100:
                        return {
                            "success": True,
                            "content": result.markdown,
                            "title": getattr(result, 'title', 'N/A'),
                            "method": "Persistent Session"
                        }
                        
                except Exception as e:
                    if self.verbose:
                        print(f"⚠️ Persistent session error: {e}")
        else:
            # Fallback to simple session
            async with AsyncWebCrawler(verbose=self.verbose) as crawler:
                try:
                    result = await crawler.arun(
                        url=url,
                        cache_mode=CacheMode.BYPASS,
                        word_count_threshold=5,
                        delay_before_return_html=10.0,
                        wait_for="load"
                    )
                    
                    if result.success and result.markdown and len(result.markdown.strip()) > 50:
                        return {
                            "success": True,
                            "content": result.markdown.strip(),
                            "title": getattr(result, 'title', 'N/A'),
                            "method": "Persistent Session"
                        }
                        
                except Exception as e:
                    if self.verbose:
                        print(f"⚠️ Persistent session error: {e}")
                        
        return None
    
    async def scrape_with_simple_delay(self, url: str, skip_images: bool = True) -> Optional[Dict[str, Any]]:
        """
        Simple delay-based strategy (working implementation)
        """
        if self.verbose:
            print(f"⏰ Attempting delay strategy: {url}")
        
        async with AsyncWebCrawler(verbose=self.verbose) as crawler:
            try:
                result = await crawler.arun(
                    url=url,
                    cache_mode=CacheMode.BYPASS,
                    delay_before_return_html=3.0,  # Wait 3 seconds for content to load
                    word_count_threshold=5  # Very low threshold
                )
                
                if result.success and result.markdown and len(result.markdown.strip()) > 30:
                    if self.verbose:
                        print(f"✅ Delay success: {len(result.markdown)} chars")
                    
                    return {
                        "success": True,
                        "content": result.markdown.strip(),
                        "title": getattr(result, 'title', 'N/A'),
                        "method": "Simple Delay"
                    }
                elif self.verbose:
                    print(f"⚠️ Content too short: {len(result.markdown or '')} chars")
                    
            except Exception as e:
                if self.verbose:
                    print(f"❌ Delay strategy error: {e}")
                    
        return None
    
    async def scrape_with_all_strategies(self, url: str, skip_images: bool = True) -> Optional[Dict[str, Any]]:
        """
        Try all strategies in order until one succeeds
        """
        strategies = [
            ("Simple Delay", lambda u: self.scrape_with_simple_delay(u, skip_images)),
            ("Enhanced Wait", lambda u: self.scrape_with_enhanced_wait(u, skip_images)),
            ("Magic Mode", lambda u: self.scrape_with_magic_mode(u, skip_images)),
            ("Progressive Scroll", lambda u: self.scrape_with_progressive_scroll(u, skip_images)),
            ("Persistent Session", lambda u: self.scrape_with_persistent_session(u, skip_images))
        ]
        
        for name, strategy in strategies:
            if self.verbose:
                print(f"\n{'='*50}")
                print(f"Trying strategy: {name}")
                print('='*50)
                
            result = await strategy(url)
            
            if result:
                result["strategy_used"] = name
                return result
            
            if self.verbose:
                print(f"❌ {name} failed, trying next strategy...")
                
        return None

async def main_scrape(url: str, output_file: Optional[str] = None, 
                     verbose: bool = False, headless: bool = True,
                     strategy: str = "auto", format: str = "markdown",
                     skip_images: bool = True) -> Optional[str]:
    """
    Main scraping function with multiple strategies
    """
    if not CRAWL4AI_AVAILABLE:
        print("❌ ERROR: crawl4ai is not properly installed or configured")
        print("Please install with: pip install crawl4ai playwright")
        print("Then run: playwright install")
        return None
        
    print(f"\n🎯 Starting enhanced scraping for: {url}")
    print(f"Strategy: {strategy}, Format: {format}, Headless: {headless}")
    print(f"Using async_configs: {USING_ASYNC_CONFIGS}")
    if skip_images:
        print("🖼️ Images: SKIPPED (faster loading)")
    else:
        print("🖼️ Images: ENABLED")
    
    scraper = EnhancedMagicScraper(verbose=verbose, headless=headless, skip_images=skip_images)
    
    # Choose strategy
    result = None
    if strategy == "auto":
        result = await scraper.scrape_with_all_strategies(url, skip_images)
    elif strategy == "magic":
        result = await scraper.scrape_with_magic_mode(url, skip_images)
    elif strategy == "wait":
        result = await scraper.scrape_with_enhanced_wait(url, skip_images)
    elif strategy == "scroll":
        result = await scraper.scrape_with_progressive_scroll(url, skip_images)
    elif strategy == "session":
        result = await scraper.scrape_with_persistent_session(url, skip_images)
    else:
        print(f"❌ Unknown strategy: {strategy}")
        return None
    
    if result and result["success"]:
        print(f"\n✅ Scraping successful using: {result.get('strategy_used', result['method'])}")
        print(f"📊 Title: {result['title']}")
        print(f"📏 Content length: {len(result['content'])} characters")
        
        # Show preview
        preview_length = 300
        preview = result['content'][:preview_length] + "..." if len(result['content']) > preview_length else result['content']
        print(f"\n📄 Preview:\n{'-'*50}\n{preview}\n{'-'*50}")
        
        # Save output
        if output_file:
            if format == "json":
                # Save as JSON with metadata
                output_data = {
                    "url": url,
                    "title": result['title'],
                    "method": result.get('strategy_used', result['method']),
                    "content_length": len(result['content']),
                    "content": result['content']
                }
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(output_data, f, indent=2, ensure_ascii=False)
            else:
                # Save as markdown
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(result['content'])
                    
            print(f"💾 Content saved to: {output_file}")
        else:
            if not verbose:
                print(f"\n{'='*60}")
                print("FULL CONTENT:")
                print('='*60)
                print(result['content'])
                
        return result['content']
    else:
        print(f"\n❌ All scraping strategies failed for: {url}")
        print("Possible reasons:")
        print("  1. The site has strong anti-bot protection")
        print("  2. The URL is incorrect or inaccessible")
        print("  3. The site requires authentication")
        print("  4. Network connectivity issues")
        print("\nSuggestions:")
        print("  • Try with --no-headless to see what's happening")
        print("  • Use --verbose for detailed debugging")
        print("  • Try a different strategy with --strategy")
        print("  • Consider using a proxy service")
        return None

def main():
    parser = argparse.ArgumentParser(
        description="Enhanced Magic Mode Web Scraper with multiple fallback strategies",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s https://example.com
  %(prog)s https://example.com -o output.md
  %(prog)s https://example.com --strategy wait --verbose
  %(prog)s https://example.com --no-headless --format json -o data.json
  
Strategies:
  auto     - Try all strategies until one works (default)
  magic    - Use Magic Mode only (fastest)
  wait     - Enhanced waiting for loading screens
  scroll   - Progressive scrolling for lazy-loaded content
  session  - Persistent browser session for cookie-based sites
        """
    )
    
    parser.add_argument("url", help="URL to scrape")
    parser.add_argument("-o", "--output", help="Output file for content")
    parser.add_argument("-v", "--verbose", action="store_true", 
                       help="Enable verbose output for debugging")
    parser.add_argument("--no-headless", action="store_true", 
                       help="Run browser in visible mode (useful for debugging)")
    parser.add_argument("-s", "--strategy", 
                       choices=["auto", "magic", "wait", "scroll", "session"],
                       default="auto",
                       help="Scraping strategy to use (default: auto)")
    parser.add_argument("-f", "--format",
                       choices=["markdown", "json"],
                       default="markdown",
                       help="Output format (default: markdown)")
    parser.add_argument("--with-images", action="store_true",
                       help="Include images in scraping (slower but complete)")
    
    args = parser.parse_args()
    
    try:
        asyncio.run(main_scrape(
            url=args.url,
            output_file=args.output,
            verbose=args.verbose,
            headless=not args.no_headless,
            strategy=args.strategy,
            format=args.format,
            skip_images=not args.with_images  # Skip images by default
        ))
    except KeyboardInterrupt:
        print("\n\n⚠️ Scraping interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()