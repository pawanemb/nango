"""
Query Generation Prompts for Enhanced Search Optimization
Generate multiple optimized search queries for better source collection
"""

from typing import Dict, Any, Optional, List


class QueryGenerationPrompts:
    """Centralized prompt management for search query generation"""

    @staticmethod
    def get_five_queries_generation_prompt(
        blog_title: str,
        heading_title: str,
        subsection_title: str,
        primary_keyword: str,
        country: str,
        outline_context: str,
        current_datetime: str = None
    ) -> str:
        """
        Generate prompt for creating 5 optimized search queries per subsection
        
        Args:
            blog_title: The main blog title for context
            heading_title: The heading title for context
            subsection_title: The specific subsection being processed
            primary_keyword: Primary SEO keyword
            country: Country for localized search
            outline_context: Full outline context for better understanding
            current_datetime: Current date and time for recent content focus
            
        Returns:
            str: Formatted prompt for OpenAI to generate 5 search queries
        """
        
        # Handle current datetime
        if current_datetime is None:
            from datetime import datetime
            current_datetime = datetime.now().strftime("%B %d, %Y at %I:%M %p")
        
        prompt = f"""
Input: {outline_context}, {subsection_title}
What you must keep in mind: Information must be specific to the H3 but tied to the overall blog as well. You must give 5 queries per H3. All five queries must be diverse but not too far away from the H3. The queries must not be around extremely basic info which you will already have in your memory but rather information which deserves real-time research. In case the query can be framed better using the location, the user is in {country} country. Today’s date is {current_datetime}.
Ensure that the queries are short-tail as very long queries do not return good results on google.
**Output Format:**
Respond with ONLY a JSON object in this exact format:
{{
  "query_1": "query angle 1",
  "query_2": "query angle 2", 
  "query_3": "query angle 3",
  "query_4": "query angle 4",
  "query_5": "query angle 5"
}}

**Example for a different topic:**
{{
  "query_1": "electric vehicle advantages benefits 2025",
  "query_2": "EV environmental impact cost savings latest",
  "query_3": "electric car vs gasoline comparison 2025",
  "query_4": "best electric vehicles 2025 reviews",
  "query_5": "electric vehicle charging infrastructure growth"
}}
"
"""
        return prompt

    @staticmethod
    def get_system_message() -> str:
        """Get system message for query generation"""
        return "You are an expert SEO research specialist who generates highly effective search queries to find the best web sources. You understand search engine optimization, user intent, and how to craft queries that return authoritative, comprehensive results."
