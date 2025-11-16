from pydantic_settings import BaseSettings
from typing import Optional, List
from pydantic import Field

class Settings(BaseSettings):
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "FastAPI Project"
    
    GEMINI_API_KEY: str = ""
    # Database settings
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_HOST: str = "db.ghhhascpgsbpqaetremm.supabase.co"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "postgres"
    DATABASE_URL: Optional[str] = None

    # Email settings
    MAIL_USERNAME: str = Field(default="", env="MAIL_USERNAME")
    MAIL_PASSWORD: str = Field(default="", env="MAIL_PASSWORD")
    MAIL_FROM: str = Field(default="no-reply@rayo.work", env="MAIL_FROM")
    MAIL_FROM_NAME: str = "Rayo Payment"
    MAIL_PORT: int = Field(default=587, env="MAIL_PORT")
    MAIL_SERVER: str = Field(default="smtp.azurecomm.net", env="MAIL_SERVER")
    MAIL_STARTTLS: bool = True
    MAIL_SSL_TLS: bool = False

    # Oxylabs settings
    OXYLABS_USERNAME: str = "USERNAME"  # Replace with actual username
    OXYLABS_PASSWORD: str = "PASSWORD"  # Replace with actual password

    # RapidAPI settings
    RAPIDAPI_KEY: str = "2c9d46aa1bmsd"

    # Celery settings
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"

    # Redis settings
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None

    # MongoDB settings
    MONGODB_URL: str = ""
    MONGODB_DB_NAME: str = ""
    MONGODB_USERNAME: str = ""
    MONGODB_PASSWORD: str = ""
    MONGODB_AUTH_SOURCE: str = ""
    MONGODB_MAX_POOL_SIZE: int = 10
    MONGODB_TIMEOUT_MS: int = 5000  # Connection timeout in milliseconds

    # Oxylabs proxy settings
    OXYLABS_PROXY_URL: str = ""
    
    # Razorpay settings
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    RAZORPAY_WEBHOOK_SECRET: str = ""
    
    # Supabase settings
    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""
    SUPABASE_JWT_SECRET: str
    FRONTEND_CALLBACK_URL: str
    FRONTEND_URL: str = "https://app.rayo.work"  # Default frontend URL
    
    # DigitalOcean Spaces settings (alternative to Supabase storage)
    DO_SPACES_KEY: str = ""
    DO_SPACES_SECRET: str = ""
    DO_SPACES_REGION: str = ""  # Default region
    DO_SPACES_ENDPOINT: str = ""  # Will be auto-generated if not provided
    DO_SPACES_BUCKET: str = ""  # Default bucket name
    
    # CDN settings for public URLs
    CDN_BASE_URL: str = "https://cdn.rayo.work"  # CDN URL for public image access
    
    # SEMrush API settings
    SEMRUSH_API_KEY: str = ""

    # OpenAI settings
    OPENAI_API_KEY: str
    OPENAI_MODEL: str = "chatgpt-4o-latest"
    OPENAI_MODEL_MINI: str = "gpt-4o-mini-2024-07-18"
    OPENAI_MODEL_4_1: str = "gpt-4.1-2025-04-14"
    OPENAI_MAX_TOKENS: int = 16384
    OPENAI_TEMPERATURE: float = 1.22
    
    # Anthropic Claude settings
    ANTHROPIC_API_KEY: str

    # OpenRouter settings (only for specific services)
    OPENROUTER_API_KEY: str = ""

    # Google API settings
    GOOGLE_API_KEY: str = ""
    GOOGLE_CSE_ID: str = ""
    
    # Serper API settings
    SERPER_API_KEY: str = ""
    
    # SerpAPI settings
    SERPAPI_KEY: str = Field(default="", env="SERPAPI_KEY")
    
    # Google OAuth2 settings for GSC
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    GOOGLE_OAUTH_REDIRECT_URI: str = "http://localhost:3000/oauth/callback"

    # Anthropic settings
    ANTHROPIC_API_KEY: str

    # Winston AI settings
    WINSTON_API_KEY: str

    # Sentry settings
    SENTRY_DSN: Optional[str] = None
    ENVIRONMENT: str = Field("development", env="ENVIRONMENT")

    # CORS settings
    BACKEND_CORS_ORIGINS: List[str] = ["*"]

    MONITORING_INTERVAL_MINUTES: int = Field(60, env="MONITORING_INTERVAL_MINUTES")

    # Cron API Key for secure monitoring updates
    CRON_API_KEY: str = Field("default-change-this-in-production", env="CRON_API_KEY")

    # Enhanced Scraping Configuration
    USE_ENHANCED_SCRAPING: bool = Field(True, env="USE_ENHANCED_SCRAPING")
    
    # MagicScraper Configuration
    MAGIC_SCRAPER_ENABLED: bool = Field(True, env="MAGIC_SCRAPER_ENABLED")
    MAGIC_SCRAPER_HEADLESS: bool = Field(True, env="MAGIC_SCRAPER_HEADLESS")
    MAGIC_SCRAPER_VERBOSE: bool = Field(False, env="MAGIC_SCRAPER_VERBOSE")
    MAGIC_SCRAPER_SKIP_IMAGES: bool = Field(True, env="MAGIC_SCRAPER_SKIP_IMAGES")
    MAGIC_SCRAPER_MAX_STRATEGIES: int = Field(4, env="MAGIC_SCRAPER_MAX_STRATEGIES")
    
    # Fallback Scraping Settings
    FALLBACK_TIMEOUT_DEFAULT: int = Field(15, env="FALLBACK_TIMEOUT_DEFAULT")
    FALLBACK_TIMEOUT_PROBLEMATIC: int = Field(25, env="FALLBACK_TIMEOUT_PROBLEMATIC")
    PROBLEMATIC_DOMAINS: str = Field("fedex.com,ups.com,dhl.com,tnt.com", env="PROBLEMATIC_DOMAINS")
    
    # Content Processing Settings
    MIN_CONTENT_LENGTH: int = Field(100, env="MIN_CONTENT_LENGTH")
    MAX_CONTENT_LENGTH: int = Field(500000, env="MAX_CONTENT_LENGTH")
    MAX_CONCURRENT_SCRAPING: int = Field(5, env="MAX_CONCURRENT_SCRAPING")
    SCRAPING_RETRY_COUNT: int = Field(3, env="SCRAPING_RETRY_COUNT")
    
    # Debug Settings
    LOG_SCRAPING_CONFIG: bool = Field(False, env="LOG_SCRAPING_CONFIG")
    
    # Rayo Scraper settings
    RAYO_SCRAPER_TOKEN: str = ""

    @property
    def get_database_url(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

settings = Settings()
