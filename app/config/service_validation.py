# Service Validation Configuration
# Fast balance checking before hitting endpoints

SERVICE_REQUIREMENTS = {
    "primary_keywords": {
        "min_balance": 0.50,  # $2 minimum balance required
        "service_name": "primary_keywords",
        "description": "Primary keyword research"
    },
    "primary_related_keywords": {
        "min_balance": 5,  # $2 minimum balance required
        "service_name": "primary_related_keywords",
        "description": "Related keyword research"
    },
    "secondary_keywords": {
        "min_balance": 5,  # $0.50 minimum balance required (increased for AI generation + intent)
        "service_name": "secondary_keywords_generation",  # Maps to billing service name
        "description": "AI-powered secondary keyword generation with intent analysis"
    },
    "secondary_keywords_manual": {
        "min_balance": 3,  # $0.35 minimum balance required
        "service_name": "secondary_keywords_manual",  # Already matches billing service name
        "description": "Manual secondary keyword analysis with intent classification"
    },
    "category_selection": {
        "min_balance": 3,  # $4000 minimum balance required
        "service_name": "category_selection",
        "description": "Category selection service"
    },
    "title_generation": {
        "min_balance": 3,  # $1.00 minimum balance required
        "service_name": "title_generation",
        "description": "Title generation service"
    },
    "outline_generation": {
        "min_balance": 3,  # $0.30 minimum balance required
        "service_name": "outline_generation",
        "description": "Outline generation service"
    },
    "outline_generation_suggestion": {
        "min_balance": 3,  # $0.30 minimum balance required
        "service_name": "outline_generation_suggestion",
        "description": "Advanced outline generation service"
    },
    "outline_generation_claude": {
        "min_balance": 5,  # $5.00 minimum balance required for premium Claude Opus
        "service_name": "outline_generation_claude",
        "description": "Premium outline generation using Claude Opus with advanced reasoning"
    },
    "sources_generation": {
        "min_balance": 3,  # $5.00 minimum balance required for high-volume streaming
        "service_name": "sources_generation",
        "description": "High-volume streaming source collection service"
    },  
    "Sources_upload_doc": {
        "min_balance": 3,  # $2000 minimum balance required
        "service_name": "Sources_upload_doc",
        "description": "Document upload service"
    },
        "add_custom_source": {
            "min_balance": 3,  # $0.30 minimum balance required
            "service_name": "add_custom_source",
            "description": "Custom source addition service"
        },
    "blog_generation": {
        "min_balance": 2,  # $3.25 minimum balance required
        "service_name": "blog_generation", 
        "description": "AI blog generation"
    },
    "meta_description": {
        "min_balance": 0.001,  # $0.001 minimum balance required
        "service_name": "meta_description", 
        "description": "AI meta description generation"
    },
    "plagiarism_detection": {
        "min_balance": 1,  # $1 minimum balance required
        "service_name": "plagiarism_checker", 
        "description": "Plagiarism detection using Winston AI"
    },
    "outline_generation_streaming": {
        "min_balance": 3,  # $3 minimum balance required for streaming service
        "service_name": "outline_generation_streaming",
        "description": "Real-time streaming outline generation with AI processing"
    },
    "text_shortening": {
        "min_balance": 1.0,  # $1.00 minimum balance required for text shortening
        "service_name": "text_shortening",
        "description": "AI-powered text shortening with SEO preservation and brand voice maintenance"
    },
    "convert_to_table": {
        "min_balance": 1.0,  # $1.00 minimum balance required for convert to table
        "service_name": "convert_to_table",
        "description": "AI-powered convert to table with SEO preservation and brand voice maintenance"
    },
    "convert_to_list": {
        "min_balance": 1.0,  # $1.00 minimum balance required for convert to list
        "service_name": "convert_to_list",
        "description": "AI-powered convert to list with SEO preservation and brand voice maintenance"
    },
}

def get_service_requirement(service_key: str):
    """Get service requirements by key"""
    return SERVICE_REQUIREMENTS.get(service_key)

def get_min_balance(service_key: str) -> float:
    """Get minimum balance required for a service"""
    service = SERVICE_REQUIREMENTS.get(service_key)
    return service["min_balance"] if service else 0.0
