"""
Internal Linking Research Service
Generates search queries and finds internal linking opportunities using parallel OpenAI calls
"""

import logging
import json
import requests
import concurrent.futures
from typing import Dict, List, Any
from datetime import datetime
import uuid
import pytz
from app.core.config import settings

logger = logging.getLogger(__name__)

class InternalLinkingResearchService:
    """
    Service for generating internal linking research using parallel OpenAI calls
    and SerpAPI searches for site-specific URLs
    """
    
    def __init__(self):
        self.openai_api_key = settings.OPENAI_API_KEY
        self.serper_api_key = settings.SERPER_API_KEY
        
    def generate_internal_linking_research(self, blog_request: Dict[str, Any], project: Dict[str, Any]) -> List[str]:
        """
        Main function to generate internal linking research
        
        Args:
            blog_request: Blog generation request payload
            project: Project information including URL
            
        Returns:
            List of unique internal URLs for linking opportunities
        """
        try:
            # Extract data from payload
            blog_title = blog_request.get("blog_title", "")
            primary_keyword = blog_request.get("primary_keyword", "")
            secondary_keywords = blog_request.get("secondary_keywords", [])
            category = blog_request.get("category", "")
            
            # Get project website URL
            project_url = project.get("url", "")
            internal_linking_enabled = project.get("internal_linking_enabled", True)
            
            if not project_url:
                logger.warning("No website URL found for project, skipping internal linking research")
                return []
                
            if not internal_linking_enabled:
                logger.info("Internal linking disabled for this project, skipping research")
                return []
            
            logger.info(f"🔍 Starting internal linking research for {project_url}")
            
            # Get outline from blog request
            outline = blog_request.get("outline", [])
            
            # 1. Generate 5 different search queries using parallel OpenAI calls
            search_queries = self.generate_search_queries_parallel(
                blog_title, primary_keyword, secondary_keywords, category, outline
            )
            
            # 2. Perform 5 parallel SerpAPI searches  
            all_urls = []
            for query in search_queries:
                site_query = f"site:{project_url} {query}"
                urls = self.search_serper_api(site_query)
                all_urls.extend(urls)
            
            # 3. Remove duplicates and return clean list
            unique_urls = list(set(all_urls))
            logger.info(f"🔗 Found {len(unique_urls)} unique internal URLs for linking")
            
            return unique_urls[:50]  # Limit to 50 URLs
            
        except Exception as e:
            logger.error(f"Internal linking research failed: {str(e)}")
            return []  # Don't fail the whole blog generation
    
    def generate_search_queries_parallel(self, title: str, primary_keyword: str, secondary_keywords: List[str], category: str, outline: Any = None) -> List[str]:
        """
        Generate 5 different search queries using parallel OpenAI calls
        Each prompt uses a different strategy for finding internal linking opportunities
        
        Args:
            title: Blog title
            primary_keyword: Main keyword for the blog
            secondary_keywords: List of secondary keywords
            category: Blog category
            outline: Blog outline structure (list, dict, or string)
            
        Returns:
            List of 5 search queries generated in parallel
        """
        try:
            # Convert secondary keywords to string for prompts
            secondary_kw_str = ", ".join(secondary_keywords[:3])  # Limit to first 3
            
            # Convert outline to string for prompts
            outline_str = ""
            if outline:
                if isinstance(outline, list):
                    outline_str = "; ".join([str(item) for item in outline[:5]])  # Limit to first 5 items
                elif isinstance(outline, dict):
                    outline_str = "; ".join([f"{k}: {v}" for k, v in list(outline.items())[:5]])
                else:
                    outline_str = str(outline)[:200]  # Limit length
            
            # 5 different prompt strategies for query generation with full context
            prompts = [
                # Strategy 1: Related Content
                f"Based on this blog context: Title '{title}', Primary keyword '{primary_keyword}', Secondary keywords '{secondary_kw_str}', Outline '{outline_str}' - Generate ONE search query to find related articles about '{primary_keyword}'. Return only 3-5 search words.",
                
                # Strategy 2: Category Content  
                f"Based on this blog context: Title '{title}', Primary keyword '{primary_keyword}', Secondary keywords '{secondary_kw_str}', Outline '{outline_str}' - Generate ONE search query to find {category} content related to '{primary_keyword}'. Return only 3-5 search words.",
                
                # Strategy 3: Educational Content
                f"Based on this blog context: Title '{title}', Primary keyword '{primary_keyword}', Secondary keywords '{secondary_kw_str}', Outline '{outline_str}' - Generate ONE search query to find beginner guides or tutorials about '{primary_keyword}'. Return only 3-5 search words.",
                
                # Strategy 4: Advanced Content
                f"Based on this blog context: Title '{title}', Primary keyword '{primary_keyword}', Secondary keywords '{secondary_kw_str}', Outline '{outline_str}' - Generate ONE search query to find advanced content about '{primary_keyword}'. Return only 3-5 search words.",
                
                # Strategy 5: Practical Content
                f"Based on this blog context: Title '{title}', Primary keyword '{primary_keyword}', Secondary keywords '{secondary_kw_str}', Outline '{outline_str}' - Generate ONE search query to find case studies or examples about '{primary_keyword}'. Return only 3-5 search words."
            ]
            
            def call_openai_for_query(prompt):
                """Single OpenAI API call for query generation"""
                try:
                    headers = {
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.openai_api_key}"
                    }
                    
                    payload = {
                        "model": "gpt-4o-mini-2024-07-18",  # Fast and cheap model
                        "messages": [
                            {
                                "role": "system", 
                                "content": "You are an expert SEO strategist specialized in internal linking research. Generate ONE single search query (3-6 words) to find relevant content for internal linking. Return ONLY the search terms - no lists, no bullet points, no explanations, no site operators, no quotes. Just one clean search phrase."
                            },
                            {
                                "role": "user", 
                                "content": prompt
                            }
                        ],
                        "max_tokens": 50,
                        "temperature": 0.7
                    }
                    
                    response = requests.post(
                        "https://api.openai.com/v1/chat/completions",
                        headers=headers,
                        json=payload,
                        timeout=10
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        query = data["choices"][0]["message"]["content"].strip()
                        # Clean the query - remove quotes and extra text
                        query = query.replace('"', '').replace("'", "").strip()
                        
                        # Take only the first line if OpenAI returns multiple lines
                        if '\n' in query:
                            query = query.split('\n')[0].strip()
                        
                        # Remove any bullet points or numbering
                        if query.startswith(('- ', '• ', '1. ', '2. ', '3. ', '* ')):
                            query = query[2:].strip()
                        elif query.startswith(('1)', '2)', '3)')):
                            query = query[2:].strip()
                            
                        return query
                    else:
                        logger.warning(f"OpenAI API error: {response.status_code}")
                        return primary_keyword  # Fallback
                        
                except Exception as e:
                    logger.warning(f"OpenAI query generation failed: {e}")
                    return primary_keyword  # Fallback to primary keyword
            
            # Execute 5 OpenAI calls in parallel
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                queries = list(executor.map(call_openai_for_query, prompts))
            
            # Filter out empty or invalid queries
            valid_queries = [q for q in queries if q and len(q.strip()) > 0]
            
            logger.info(f"🤖 Generated {len(valid_queries)} search queries: {valid_queries}")
            return valid_queries
            
        except Exception as e:
            logger.error(f"Parallel query generation failed: {str(e)}")
            # Fallback to simple queries
            return [
                primary_keyword,
                f"{primary_keyword} guide",
                f"{primary_keyword} {category}",
                f"{primary_keyword} tutorial",
                f"{primary_keyword} tips"
            ]
    
    def search_serper_api(self, query: str, num_results: int = 10) -> List[str]:
        """
        Search using SerpAPI/Serper with site: operator
        
        Args:
            query: Search query with site: operator
            num_results: Number of results to fetch
            
        Returns:
            List of URLs found in search results
        """
        try:
            headers = {
                "X-API-KEY": self.serper_api_key,
                "Content-Type": "application/json"
            }
            
            payload = {
                "q": query,
                "num": num_results
            }
            
            response = requests.post(
                "https://google.serper.dev/search", 
                headers=headers,
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                urls = []
                
                # Extract URLs from organic results
                for result in data.get("organic", []):
                    url = result.get("link")
                    if url:
                        urls.append(url)
                
                logger.info(f"🔍 Found {len(urls)} URLs for query: {query}")
                return urls
            else:
                logger.warning(f"Serper API error: {response.status_code} - {response.text}")
                return []
                
        except Exception as e:
            logger.error(f"Serper API search failed: {str(e)}")
            return []
    
    def format_internal_links_for_prompt(self, urls: List[str]) -> str:
        """
        Format internal URLs for Claude prompt
        
        Args:
            urls: List of internal URLs
            
        Returns:
            Formatted string for Claude prompt
        """
        if not urls:
            return "No internal linking opportunities found."
        
        formatted_links = []
        for i, url in enumerate(urls[:50], 1):  # Limit to 50 URLs
            formatted_links.append(f"{i}. {url}")
        
        return "\n".join(formatted_links)
    
    def update_usage_tracker(self, usage_tracker: Dict[str, Any], queries_count: int, searches_count: int) -> Dict[str, Any]:
        """
        Update usage tracker with research API calls
        
        Args:
            usage_tracker: Existing usage tracker
            queries_count: Number of OpenAI query generation calls
            searches_count: Number of search API calls
            
        Returns:
            Updated usage tracker
        """
        try:
            # Estimate costs (approximate)
            openai_cost = queries_count * 0.001  # ~$0.001 per query call
            serper_cost = searches_count * 0.005  # ~$0.005 per search call
            
            # Add research tracking
            usage_tracker["research_calls"] = {
                "openai_queries": queries_count,
                "serper_searches": searches_count,
                "total_research_cost": openai_cost + serper_cost,
                "research_timestamp": datetime.now(pytz.timezone('Asia/Kolkata')).isoformat()
            }
            
            logger.info(f"📊 Research usage: {queries_count} queries + {searches_count} searches = ${openai_cost + serper_cost:.4f}")
            
            return usage_tracker
            
        except Exception as e:
            logger.warning(f"Failed to update usage tracker for research: {str(e)}")
            return usage_tracker


# Convenience function for easy import
def generate_internal_linking_research(blog_request: Dict[str, Any], project: Dict[str, Any]) -> List[str]:
    """
    Convenience function to generate internal linking research
    
    Args:
        blog_request: Blog generation request payload
        project: Project information
        
    Returns:
        List of internal URLs for linking
    """
    service = InternalLinkingResearchService()
    return service.generate_internal_linking_research(blog_request, project)


def format_internal_links_for_claude(urls: List[str]) -> str:
    """
    Convenience function to format URLs for Claude prompt
    
    Args:
        urls: List of internal URLs
        
    Returns:
        Formatted string for Claude prompt
    """
    service = InternalLinkingResearchService()
    return service.format_internal_links_for_prompt(urls)