"""
Search service module for Rayo application.
Provides proxy-based Google search functionality.
"""

from .proxy_google_search import (
    perform_google_search,
    GoogleSearchResult,
    extract_results_from_html,
    get_random_user_agent
)

__all__ = [
    'perform_google_search',
    'GoogleSearchResult',
    'extract_results_from_html',
    'get_random_user_agent'
]
