from typing import List, Dict, Optional
from datetime import datetime
import os
import re
import json
import logging
from urllib.parse import urlparse
import requests
from dataclasses import dataclass

@dataclass
class SearchResult:
    title: str
    link: str
    snippet: str
    date_published: Optional[str] = None

class EnhancedSearchService:
    def __init__(self, additional_blocked_domains: List[str] = None):
        self.blocked_domains = [
            # Social Media
            'reddit.com', 'quora.com', 'tumblr.com', 'twitter.com',
            'facebook.com', 'instagram.com', 'tiktok.com', 'snapchat.com',
            'pinterest.com', 'discord.com',
            
            # Forums & Discussion
            '4chan.org', '8chan.org', 'somethingawful.com',
            'stackexchange.com', 'stackoverflow.com', 'ask.fm',
            
            # Blogging Platforms
            'medium.com', 'wordpress.com', 'blogger.com', 'blogspot.com',
            
            # Wiki & Fan Sites
            'fandom.com', 'tvtropes.org', 'wikia.com',
            
            # Content Farms & Low Quality
            'buzzfeed.com', 'ranker.com', 'upworthy.com', 'boredpanda.com',
            'ezinearticles.com', 'hubpages.com', 'infobarrel.com',
            'ehow.com', 'thoughtco.com',
            
            # User-Generated Content
            'deviantart.com', 'boardgamegeek.com', 'myanimelist.net',
            'goodreads.com',
            
            # File Sharing & Torrents
            'thepiratebay.org', 'limetorrents.info',
            
            # Outdated/Defunct
            'geocities.com', 'angelfire.com',
            
            # Unreliable News/Info
            'naturalnews.com', 'infowars.com', 'beforeitsnews.com',
            
            # Development
            'github.com',
            
            # Maps
            'openstreetmap.org'
        ]
        if additional_blocked_domains:
            self.blocked_domains.extend(additional_blocked_domains)

    async def search_with_credible_sources(self, query: str) -> List[SearchResult]:
        results = await self.search_google(query)
        return self.filter_and_rank_results(results)

    def filter_and_rank_results(self, results: List[SearchResult]) -> List[SearchResult]:
        unique_results = {}
        
        for result in results:
            if self.is_blocked_domain(result.link):
                logging.info(f"Filtered out blocked domain: {result.link}")
                continue

            if result.link not in unique_results:
                unique_results[result.link] = result

        # Convert to list and sort by relevance
        sorted_results = sorted(
            unique_results.values(),
            key=lambda x: self.calculate_relevance(x),
            reverse=True
        )
        return sorted_results[:10]  # Top 10 results

    def is_blocked_domain(self, url: str) -> bool:
        try:
            domain = urlparse(url).netloc.lower()
            return any(
                domain == blocked_domain.lower() or
                domain.endswith('.' + blocked_domain.lower()) or
                domain.replace('www.', '') == blocked_domain.lower()
                for blocked_domain in self.blocked_domains
            )
        except:
            return False

    def calculate_relevance(self, result: SearchResult) -> float:
        score = 0.0
        trustworthy_domains = [
            'edu', 'gov', 'forbes.com', 'harvard.edu', 'mit.edu',
            'stanford.edu', 'nature.com', 'sciencedirect.com',
            'springer.com', 'wiley.com'
        ]

        try:
            domain = urlparse(result.link).netloc.lower()
            if any(td in domain for td in trustworthy_domains):
                score += 20
        except:
            pass

        # Content quality indicators
        if 'research' in result.snippet or 'study' in result.snippet:
            score += 10
        if 'analysis' in result.snippet or 'data' in result.snippet:
            score += 10
        if re.search(r'\d+%|\d+\s*people', result.snippet):
            score += 15

        # Freshness
        if result.date_published:
            try:
                published_date = datetime.fromisoformat(result.date_published.replace('Z', '+00:00'))
                age_in_days = (datetime.now() - published_date).days
                score += max(0, 30 - (age_in_days / 30))
            except:
                pass

        return score

    def analyze_title_type(self, title: str) -> List[str]:
        patterns = {
            'howTo': r'how\s+to|guide|ways|steps',
            'comparison': r'vs|versus|compare|difference',
            'problem': r'problem|issue|challenge|solve',
            'benefits': r'benefits|advantages|why|improve',
            'definition': r'what\s+is|define|meaning'
        }

        return [
            title_type for title_type, pattern in patterns.items()
            if re.search(pattern, title, re.IGNORECASE)
        ]

    def generate_search_queries(
        self,
        title: str,
        primary_keyword: str,
        category: Dict,
        title_types: List[str]
    ) -> List[str]:
        current_year = datetime.now().year
        queries = [
            f"{primary_keyword} statistics {current_year}",
            f"{primary_keyword} market research {current_year}",
            f"{title} expert analysis"
        ]

        type_queries = {
            'howTo': [
                f"{title} expert methodology",
                f"{primary_keyword} best practices research",
                f"{title} case studies success stories"
            ],
            'comparison': [
                f"{title} detailed analysis",
                f"{primary_keyword} comparative study",
                f"{title} expert comparison"
            ],
            'problem': [
                f"{title} solution research",
                f"{primary_keyword} problem analysis",
                f"{title} expert solutions"
            ],
            'benefits': [
                f"{title} proven advantages",
                f"{primary_keyword} impact study",
                f"{title} research benefits"
            ],
            'definition': [
                f"{title} comprehensive explanation",
                f"{primary_keyword} industry definition",
                f"{title} expert analysis"
            ]
        }

        for title_type in title_types:
            if title_type in type_queries:
                queries.extend(type_queries[title_type])

        if category and 'Blog Category' in category:
            queries.extend([
                f"{title} {category['Blog Category']} research",
                f"{primary_keyword} {category['Blog Category']} analysis {current_year}"
            ])

        return queries

    async def search_google(self, query: str) -> List[SearchResult]:
        api_key = os.getenv('GOOGLE_API_KEY')
        search_engine_id = os.getenv('GOOGLE_CSE_ID')

        if not api_key or not search_engine_id:
            logging.error('Google API key or Search Engine ID not configured')
            return []

        try:
            endpoint = (
                f"https://www.googleapis.com/customsearch/v1"
                f"?key={api_key}&cx={search_engine_id}"
                f"&q={requests.utils.quote(query)}"
            )
            response = await requests.get(endpoint)
            data = response.json()

            if response.status_code != 200 or 'items' not in data:
                return []

            return [
                SearchResult(
                    title=item['title'],
                    link=item['link'],
                    snippet=item.get('snippet', ''),
                    date_published=item.get('pagemap', {})
                    .get('metatags', [{}])[0]
                    .get('article:published_time')
                )
                for item in data['items']
            ]
        except Exception as error:
            logging.error(f'Error in Google search: {error}')
            return []

    async def search_for_section(
        self,
        title: str,
        primary_keyword: str,
        heading: str,
        category: Dict
    ) -> List[SearchResult]:
        title_types = self.analyze_title_type(heading)
        queries = self.generate_search_queries(heading, primary_keyword, category, title_types)
        
        logging.info(f'Generated Queries: {json.dumps(queries, indent=2)}')
        
        all_results = []
        for query in queries:
            results = await self.search_with_credible_sources(query)
            logging.info(f'Raw Results for query "{query}": {json.dumps([vars(r) for r in results], indent=2)}')
            all_results.extend(results)

        logging.info(f'All Combined Results: {json.dumps([vars(r) for r in all_results], indent=2)}')

        filtered_results = self.filter_and_rank_results(all_results)
        logging.info(f'Final Filtered Results: {json.dumps([vars(r) for r in filtered_results], indent=2)}')
        
        return filtered_results

    async def search_for_introduction(
        self,
        title: str,
        primary_keyword: str,
        category: Dict
    ) -> List[SearchResult]:
        title_types = self.analyze_title_type(title)
        queries = self.generate_search_queries(title, primary_keyword, category, title_types)
        
        all_results = []
        for query in queries:
            results = await self.search_with_credible_sources(query)
            all_results.extend(results)

        return self.filter_and_rank_results(all_results)
