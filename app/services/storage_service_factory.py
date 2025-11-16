"""
Storage Service Factory
Provides a unified interface for different storage providers
"""
from typing import Optional, Union
from app.core.config import settings
from app.core.logging_config import logger

# Import storage services
from app.services.supabase_storage_service import SupabaseStorageService
from app.services.digitalocean_spaces_service import DigitalOceanSpacesService

class StorageServiceFactory:
    """
    Factory class to create storage services based on configuration
    """
    
    @staticmethod
    def create_storage_service(user_token: Optional[str] = None, provider: Optional[str] = None):
        """
        Create storage service based on configuration
        
        Args:
            user_token: Optional user token for authentication
            provider: Optional provider override ('supabase' or 'digitalocean')
            
        Returns:
            Storage service instance
        """
        # Determine which provider to use
        if provider:
            storage_provider = provider
        else:
            # Auto-detect based on configuration
            storage_provider = StorageServiceFactory._detect_storage_provider()
        
        logger.info(f"Creating storage service with provider: {storage_provider}")
        
        if storage_provider == "digitalocean":
            return DigitalOceanSpacesService(user_token=user_token)
        elif storage_provider == "supabase":
            return SupabaseStorageService(user_token=user_token)
        else:
            raise ValueError(f"Unsupported storage provider: {storage_provider}")
    
    @staticmethod
    def _detect_storage_provider() -> str:
        """
        Auto-detect storage provider based on available configuration
        
        Returns:
            Provider name ('supabase' or 'digitalocean')
        """
        # Check DigitalOcean Spaces configuration
        do_spaces_configured = all([
            getattr(settings, 'DO_SPACES_KEY', None),
            getattr(settings, 'DO_SPACES_SECRET', None)
        ])
        
        # Check Supabase configuration
        supabase_configured = all([
            getattr(settings, 'SUPABASE_URL', None),
            getattr(settings, 'SUPABASE_KEY', None)
        ])
        
        # Priority: DigitalOcean Spaces first, then Supabase
        if do_spaces_configured:
            logger.info("DigitalOcean Spaces configuration detected")
            return "digitalocean"
        elif supabase_configured:
            logger.info("Supabase configuration detected")
            return "supabase"
        else:
            # Default to Supabase if no configuration is found
            logger.warning("No storage configuration found, defaulting to Supabase")
            return "supabase"
    
    @staticmethod
    def get_available_providers() -> list:
        """
        Get list of available storage providers based on configuration
        
        Returns:
            List of available provider names
        """
        providers = []
        
        # Check DigitalOcean Spaces
        if all([
            getattr(settings, 'DO_SPACES_KEY', None),
            getattr(settings, 'DO_SPACES_SECRET', None)
        ]):
            providers.append("digitalocean")
        
        # Check Supabase
        if all([
            getattr(settings, 'SUPABASE_URL', None),
            getattr(settings, 'SUPABASE_KEY', None)
        ]):
            providers.append("supabase")
        
        return providers

# Convenience function for easy import
def get_storage_service(user_token: Optional[str] = None, provider: Optional[str] = None):
    """
    Convenience function to get storage service
    
    Args:
        user_token: Optional user token for authentication
        provider: Optional provider override
        
    Returns:
        Storage service instance
    """
    return StorageServiceFactory.create_storage_service(user_token=user_token, provider=provider)
