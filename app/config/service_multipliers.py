"""
Service-Specific Multipliers Configuration
Hardcoded multipliers for different services using LLM
"""

# Service-specific multipliers (business markup per service)
SERVICE_MULTIPLIERS = {
    "category_selection": {
        "multiplier": 5.0,
        "description": "Blog content generation service",
        "category": "content_creation"
    },
    "meta_description": {
        "multiplier": 5.0,
        "description": "Meta description generation service",
        "category": "content_creation"
    },  
    "keyword_research": {
        "multiplier": 5.0,
        "description": "SEO keyword research service",
        "category": "seo_tools"
    },
    "content_analysis": {
        "multiplier": 5.0,
        "description": "Content analysis and optimization",
        "category": "content_optimization"
    },
    "title_generation": {
        "multiplier": 5.0,
        "description": "Title and headline generation",
        "category": "content_creation"
    },
    "outline_creation": {
        "multiplier": 5.0,
        "description": "Content outline creation",
        "category": "content_planning"
    },
    "outline_generation": {
        "multiplier": 0.2,
        "description": "Basic outline generation service (divided by 5)",
        "category": "content_planning"
    },
    "outline_generation_suggestion": {
        "multiplier": 5.0,
        "description": "Advanced outline generation with web research",
        "category": "content_planning"
    },
    "outline_generation_claude": {
        "multiplier": 8.0,
        "description": "Premium outline generation using Claude Opus with advanced reasoning",
        "category": "content_planning"
    },
    "secondary_keywords_generation": {
        "multiplier": 5.0,
        "description": "AI-powered secondary keyword generation with intent analysis",
        "category": "seo_tools"
    },
    "secondary_keywords_manual": {
        "multiplier": 5.0,
        "description": "Manual secondary keyword analysis and intent classification",
        "category": "seo_tools"
    },
    "add_custom_source": {
        "multiplier": 5.0,
        "description": "Custom source addition and processing with AI analysis",
        "category": "content_research"
    },
    "add_custom_source": {
        "multiplier": 5.0,
        "description": "Custom text source processing with AI analysis",
        "category": "content_research"
    },
    "Sources_upload_doc": {
        "multiplier": 5.0,
        "description": "Document upload and AI-powered content extraction",
        "category": "content_research"
    },
    "sources_generation": {
        "multiplier": 5.0,
        "description": "High-volume streaming source collection with batch OpenAI processing",
        "category": "content_research"
    },
    "primary_keywords": {
        "multiplier": 5.0,
        "description": "Primary keyword search with AI intent analysis",
        "category": "seo_tools"
    },
    "primary_related_keywords": {
        "multiplier": 5.0,
        "description": "Related keyword research with batch AI intent analysis",
        "category": "seo_tools"
    },
    "blog_generation": {
        "multiplier": 5.0,
        "description": "Full blog generation with specialty detection and content processing",
        "category": "content_creation"
    },
    "plagiarism_checker": {
        "multiplier": 5.0,
        "description": "Plagiarism detection and content originality analysis",
        "category": "content_optimization"
    },
    "outline_generation_streaming": {
        "multiplier": 5.0,
        "description": "Streaming outline generation with real-time AI processing",
        "category": "content_planning"
    },
    "text_shortening": {
        "multiplier": 5.0,
        "description": "AI-powered text shortening with SEO preservation and brand voice maintenance",
        "category": "content_optimization"
    },
    "convert_to_table": {
        "multiplier": 5.0,
        "description": "AI-powered convert to table with SEO preservation and brand voice maintenance",
        "category": "content_optimization"
    },
    "featured_image_generation": {
        "multiplier": 8.0,
        "description": "AI-powered featured image generation using Google Gemini Imagen",
        "category": "content_creation"
    }
}

# Category-based default multipliers (fallback)
CATEGORY_DEFAULT_MULTIPLIERS = {
    "content_creation": 5.0,
    "seo_tools": 5.0,
    "content_optimization": 5.0,
    "content_planning": 5.0,
    "social_media": 5.0,
    "email_marketing": 5.0,
    "ecommerce": 5.0,
    "advertising": 5.0,
    "market_research": 5.0,
    "content_research": 5.0
}

# Default multiplier if service not found
DEFAULT_MULTIPLIER = 5.0


def get_service_multiplier(service_name: str) -> dict:
    """
    Get multiplier for a specific service
    
    Args:
        service_name: Name of the service
        
    Returns:
        Dict with multiplier and service info
    """
    if service_name in SERVICE_MULTIPLIERS:
        return SERVICE_MULTIPLIERS[service_name]
    
    # Return default
    return {
        "multiplier": DEFAULT_MULTIPLIER,
        "description": f"Unknown service: {service_name}",
        "category": "unknown"
    }


def get_category_services(category: str) -> list:
    """
    Get all services in a specific category
    
    Args:
        category: Category name
        
    Returns:
        List of service names in the category
    """
    return [
        service for service, config in SERVICE_MULTIPLIERS.items()
        if config["category"] == category
    ]


def get_all_categories() -> list:
    """Get all available categories"""
    categories = set()
    for config in SERVICE_MULTIPLIERS.values():
        categories.add(config["category"])
    return sorted(list(categories))


def get_services_by_multiplier_range(min_multiplier: float, max_multiplier: float) -> list:
    """
    Get services within a multiplier range
    
    Args:
        min_multiplier: Minimum multiplier
        max_multiplier: Maximum multiplier
        
    Returns:
        List of service names within the range
    """
    return [
        service for service, config in SERVICE_MULTIPLIERS.items()
        if min_multiplier <= config["multiplier"] <= max_multiplier
    ]
