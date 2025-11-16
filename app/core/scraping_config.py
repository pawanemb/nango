"""
Scraping Configuration Module
Centralized configuration for Enhanced Scraping Service and MagicScraper
"""

from typing import Dict, Any
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)


class ScrapingConfig:
    """Configuration class for Enhanced Scraping Service"""
    
    # Enhanced Scraping Settings
    USE_ENHANCED_SCRAPING = settings.USE_ENHANCED_SCRAPING
    
    # MagicScraper Settings
    MAGIC_SCRAPER_ENABLED = settings.MAGIC_SCRAPER_ENABLED
    MAGIC_SCRAPER_HEADLESS = settings.MAGIC_SCRAPER_HEADLESS
    MAGIC_SCRAPER_VERBOSE = settings.MAGIC_SCRAPER_VERBOSE
    MAGIC_SCRAPER_SKIP_IMAGES = settings.MAGIC_SCRAPER_SKIP_IMAGES
    MAGIC_SCRAPER_MAX_STRATEGIES = settings.MAGIC_SCRAPER_MAX_STRATEGIES
    
    # Fallback Settings
    FALLBACK_TIMEOUT_DEFAULT = settings.FALLBACK_TIMEOUT_DEFAULT
    FALLBACK_TIMEOUT_PROBLEMATIC = settings.FALLBACK_TIMEOUT_PROBLEMATIC
    PROBLEMATIC_DOMAINS = [
        domain.strip() for domain in settings.PROBLEMATIC_DOMAINS.split(",")
        if domain.strip()
    ]
    
    # Content Limits
    MIN_CONTENT_LENGTH = settings.MIN_CONTENT_LENGTH
    MAX_CONTENT_LENGTH = settings.MAX_CONTENT_LENGTH
    
    # Performance Settings
    MAX_CONCURRENT_SCRAPING = settings.MAX_CONCURRENT_SCRAPING
    SCRAPING_RETRY_COUNT = settings.SCRAPING_RETRY_COUNT
    
    @classmethod
    def get_magic_scraper_config(cls) -> Dict[str, Any]:
        """Get MagicScraper configuration dictionary"""
        return {
            "enabled": cls.MAGIC_SCRAPER_ENABLED,
            "headless": cls.MAGIC_SCRAPER_HEADLESS,
            "verbose": cls.MAGIC_SCRAPER_VERBOSE,
            "skip_images": cls.MAGIC_SCRAPER_SKIP_IMAGES,
            "max_strategies": cls.MAGIC_SCRAPER_MAX_STRATEGIES
        }
    
    @classmethod
    def get_fallback_config(cls) -> Dict[str, Any]:
        """Get fallback scraper configuration dictionary"""
        return {
            "timeout_default": cls.FALLBACK_TIMEOUT_DEFAULT,
            "timeout_problematic": cls.FALLBACK_TIMEOUT_PROBLEMATIC,
            "problematic_domains": cls.PROBLEMATIC_DOMAINS,
            "retry_count": cls.SCRAPING_RETRY_COUNT
        }
    
    @classmethod
    def get_content_config(cls) -> Dict[str, Any]:
        """Get content processing configuration dictionary"""
        return {
            "min_length": cls.MIN_CONTENT_LENGTH,
            "max_length": cls.MAX_CONTENT_LENGTH,
            "max_concurrent": cls.MAX_CONCURRENT_SCRAPING
        }
    
    @classmethod
    def is_problematic_domain(cls, domain: str) -> bool:
        """Check if domain is in the problematic domains list"""
        domain_lower = domain.lower()
        return any(prob_domain in domain_lower for prob_domain in cls.PROBLEMATIC_DOMAINS)
    
    @classmethod
    def get_timeout_for_domain(cls, domain: str) -> int:
        """Get appropriate timeout for a domain"""
        return cls.FALLBACK_TIMEOUT_PROBLEMATIC if cls.is_problematic_domain(domain) else cls.FALLBACK_TIMEOUT_DEFAULT
    
    @classmethod
    def log_configuration(cls):
        """Log current configuration for debugging"""
        logger.info("🔧 Scraping Configuration:")
        logger.info(f"   Enhanced Scraping: {'✅ Enabled' if cls.USE_ENHANCED_SCRAPING else '❌ Disabled'}")
        logger.info(f"   MagicScraper: {'✅ Enabled' if cls.MAGIC_SCRAPER_ENABLED else '❌ Disabled'}")
        logger.info(f"   Headless Mode: {'✅ Yes' if cls.MAGIC_SCRAPER_HEADLESS else '❌ No'}")
        logger.info(f"   Skip Images: {'✅ Yes' if cls.MAGIC_SCRAPER_SKIP_IMAGES else '❌ No'}")
        logger.info(f"   Max Strategies: {cls.MAGIC_SCRAPER_MAX_STRATEGIES}")
        logger.info(f"   Content Limits: {cls.MIN_CONTENT_LENGTH} - {cls.MAX_CONTENT_LENGTH} chars")
        logger.info(f"   Timeouts: {cls.FALLBACK_TIMEOUT_DEFAULT}s normal, {cls.FALLBACK_TIMEOUT_PROBLEMATIC}s problematic")
        logger.info(f"   Problematic Domains: {', '.join(cls.PROBLEMATIC_DOMAINS)}")


# Initialize configuration on module import
scraping_config = ScrapingConfig()

# Export commonly used configurations
ENHANCED_SCRAPING_ENABLED = scraping_config.USE_ENHANCED_SCRAPING
MAGIC_SCRAPER_CONFIG = scraping_config.get_magic_scraper_config()
FALLBACK_CONFIG = scraping_config.get_fallback_config()
CONTENT_CONFIG = scraping_config.get_content_config()

# Log configuration when module is imported
if settings.LOG_SCRAPING_CONFIG:
    scraping_config.log_configuration()