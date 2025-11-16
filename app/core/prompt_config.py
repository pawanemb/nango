"""
Centralized configuration for all prompt types used in the application.
This module defines all prompt types and their tracking configurations.
"""

from enum import Enum
from typing import Dict, Any


class PromptType(str, Enum):
    """Enumeration of all prompt types in the system"""
    
    # Service and audience detection
    SERVICE_DETECTION = "service_detection"
    AUDIENCE_DETECTION = "audience_detection"
    
    # Keyword related prompts
    KEYWORD_SUGGESTIONS = "keyword_suggestions"
    RELATED_KEYWORDS = "related_keywords"
    SECONDARY_KEYWORDS = "secondary_keywords"
    KEYWORD_INTENT_DETECTION = "keyword_intent_detection"
    
    # Content planning
    CATEGORY_SELECTION = "category_selection"
    TITLE_SELECTION = "title_selection"
    
    # Outline generation
    AI_OUTLINE_GENERATION = "ai_outline_generation"
    OUTLINE_FROM_GOOGLE = "outline_from_google"
    
    # Word count allocation
    WORD_COUNT_SECTIONS = "word_count_sections"
    WORD_COUNT_HEADINGS = "word_count_headings"
    
    # Content generation
    GOOGLE_SEARCH_SCRAPING = "google_search_scraping"
    SECTION_GENERATION = "section_generation"
    AI_BLOG_SECTION_GENERATION = "ai_blog_section_generation"
    
    # Blog content generation steps  
    AI_BLOG_INTRODUCTION_GENERATION = "ai_blog_introduction_generation"
    AI_BLOG_CONCLUSION_GENERATION = "ai_blog_conclusion_generation"
    AI_BLOG_FAQ_GENERATION = "ai_blog_faq_generation"
    AI_TITLE_GENERATION = "ai_title_generation"
    
    # Enhancement passes
    AI_BLOG_ENHANCEMENT = "ai_blog_enhancement"
    ENHANCE_1 = "enhance_1"
    ENHANCE_2 = "enhance_2"
    ENHANCE_3 = "enhance_3"
    ENHANCE_4 = "enhance_4"
    ENHANCE_5 = "enhance_5"
    ENHANCE_6 = "enhance_6"
    
    # Meta content
    META_DESCRIPTION = "meta_description"


# Prompt configuration with human-readable names and descriptions
PROMPT_CONFIG: Dict[str, Dict[str, Any]] = {
    PromptType.SERVICE_DETECTION: {
        "name": "Service Detection",
        "description": "Detects services offered based on website content",
        "category": "analysis"
    },
    PromptType.AUDIENCE_DETECTION: {
        "name": "Audience Detection",
        "description": "Identifies target audience from website analysis",
        "category": "analysis"
    },
    PromptType.KEYWORD_SUGGESTIONS: {
        "name": "Keyword Suggestions",
        "description": "Generates primary keyword suggestions",
        "category": "keywords"
    },
    PromptType.RELATED_KEYWORDS: {
        "name": "Related Keywords (PKW Suggestions)",
        "description": "Generates related keywords based on primary keyword",
        "category": "keywords"
    },
    PromptType.SECONDARY_KEYWORDS: {
        "name": "Secondary Keyword Suggestions",
        "description": "Generates secondary keywords for content optimization",
        "category": "keywords"
    },
    PromptType.KEYWORD_INTENT_DETECTION: {
        "name": "Keyword Intent Detection",
        "description": "Detects search intent behind keywords",
        "category": "keywords"
    },
    PromptType.CATEGORY_SELECTION: {
        "name": "Category Selection",
        "description": "Selects appropriate content categories",
        "category": "planning"
    },
    PromptType.TITLE_SELECTION: {
        "name": "Title Selection",
        "description": "Generates and selects optimal titles",
        "category": "planning"
    },
    PromptType.AI_OUTLINE_GENERATION: {
        "name": "AI Outline Generation",
        "description": "Generates content outline using AI",
        "category": "outline"
    },
    PromptType.OUTLINE_FROM_GOOGLE: {
        "name": "Outline from Google Scraping",
        "description": "Generates outline based on Google search results",
        "category": "outline"
    },
    PromptType.WORD_COUNT_SECTIONS: {
        "name": "Word Count Allotment for Sections",
        "description": "Allocates word count to different sections",
        "category": "planning"
    },
    PromptType.WORD_COUNT_HEADINGS: {
        "name": "Word Count Allotment for Headings",
        "description": "Allocates word count to different headings",
        "category": "planning"
    },
    PromptType.GOOGLE_SEARCH_SCRAPING: {
        "name": "Google Search Results Scraping",
        "description": "Processes scraped Google search results",
        "category": "research"
    },
    PromptType.SECTION_GENERATION: {
        "name": "Section Generation",
        "description": "Generates individual content sections",
        "category": "content"
    },
    PromptType.AI_BLOG_SECTION_GENERATION: {
        "name": "AI Blog Section Generation",
        "description": "Generates individual blog sections using AI",
        "category": "content"
    },
    PromptType.AI_BLOG_INTRODUCTION_GENERATION: {
        "name": "AI Blog Introduction Generation",
        "description": "Generates AI-generated blog introductions",
        "category": "content"
    },
    PromptType.AI_BLOG_CONCLUSION_GENERATION: {
        "name": "AI Blog Conclusion Generation",
        "description": "Generates AI-generated blog conclusions",
        "category": "content"
    },
    PromptType.AI_BLOG_FAQ_GENERATION: {
        "name": "AI Blog FAQ Generation",
        "description": "Generates AI-generated blog FAQs",
        "category": "content"
    },
    PromptType.AI_TITLE_GENERATION: {
        "name": "AI Title Generation",
        "description": "Generates AI-generated titles for blog posts",
        "category": "content"
    },
    PromptType.AI_BLOG_ENHANCEMENT: {
        "name": "AI Blog Enhancement",
        "description": "Enhances AI-generated blog content",
        "category": "enhancement"
    },
    PromptType.ENHANCE_1: {
        "name": "Enhancement Pass 1",
        "description": "First content enhancement iteration",
        "category": "enhancement"
    },
    PromptType.ENHANCE_2: {
        "name": "Enhancement Pass 2",
        "description": "Second content enhancement iteration",
        "category": "enhancement"
    },
    PromptType.ENHANCE_3: {
        "name": "Enhancement Pass 3",
        "description": "Third content enhancement iteration",
        "category": "enhancement"
    },
    PromptType.ENHANCE_4: {
        "name": "Enhancement Pass 4",
        "description": "Fourth content enhancement iteration",
        "category": "enhancement"
    },
    PromptType.ENHANCE_5: {
        "name": "Enhancement Pass 5",
        "description": "Fifth content enhancement iteration",
        "category": "enhancement"
    },
    PromptType.ENHANCE_6: {
        "name": "Enhancement Pass 6",
        "description": "Sixth content enhancement iteration",
        "category": "enhancement"
    },
    PromptType.META_DESCRIPTION: {
        "name": "Meta Description Generation",
        "description": "Generates SEO meta descriptions",
        "category": "meta"
    }
}


def get_prompt_name(prompt_type: str) -> str:
    """Get human-readable name for a prompt type"""
    config = PROMPT_CONFIG.get(prompt_type, {})
    return config.get("name", prompt_type)


def get_prompt_category(prompt_type: str) -> str:
    """Get category for a prompt type"""
    config = PROMPT_CONFIG.get(prompt_type, {})
    return config.get("category", "other") 