"""
Query Generation Prompts for Enhanced Search Optimization
Generate multiple optimized search queries for better source collection
"""

from typing import Dict, Any, Optional, List



class SourcesCollectionPrompts:
    """Centralized prompt management for sources collection and processing"""

    @staticmethod
    def get_information_user_prompt(
        blog_title: str,
        heading_title: str,
        subsection_title: str,
        combined_sources: List[Dict[str, str]],
        outline_json: str = None
    ) -> str:
        """
        Generate prompt for extracting knowledge from multiple combined sources
        
        Args:
            blog_title: The main blog title for context
            heading_title: The heading title for context
            subsection_title: The specific subsection being processed
            combined_sources: List of dicts with 'url', 'title', 'content' keys
            outline_json: The full blog outline structure for context
            
        Returns:
            str: Formatted prompt string for OpenAI processing of combined sources
        """
        # Build the sources content section
        sources_content = ""
        for i, source in enumerate(combined_sources, 1):
            sources_content += f"""
SOURCE {i}: {source['url']} - {source['title']}
CONTENT:
{source['content'][:1500]}  

"""

        # Add outline context if provided
        outline_context = ""
        if outline_json:
            outline_context = f"""
Blog Outline Structure:
{outline_json}

"""

        prompt = f"""
Input: 
 H3 where this info will be used: {subsection_title}
Outline:{outline_context}

Sources data: {sources_content}

"""
        return prompt


    @staticmethod
    def get_information_system_prompt() -> str:
        """Get system message for query generation"""
        return """
        Role: You are an expert researcher who specialises in extracting relevant information from scrapped html webpages.
Goals: Extract information in the specified output format.

Process: 1. Understand the question for which you have to extract information.
2. Read the entire scrapped webpage.
3. Determine whether the contents have relevant information which can be used to satisfy the query.
4. If relevant information is found, then if it is too complex, break it down into pointers, else give output without breaking it down into pointers. Ensure that the individual pointer has meaningfully substantial information, it should not be incomplete in itself. All pointers should have substantial differentiation amongst them.

Output: Do not give additional information or comments. Use Mckinsey's pyramid principle of communication which says that give the main point first and other details and explanation later on. Give the information re-written in a research-usable way which is short and to the point from the page in the format 
Output:
Dont include ```json in the output in the response
Provide your response in this exact JSON format:

{{
  "Source_1": {{
    "link_and_source_name": "URL of source 1 - Website/Source name",
    "information": {{
      "information_1": "Information 1",
      "information_2": "Information 2", 
      "information_n": "Information n"
    }}
  }},
  "Source_2": {{
    "link_and_source_name": "URL of source 2 - Website/Source name",
    "information": {{
      "information_1": "Information 1",
      "information_2": "Information 2", 
      "information_n": "Information n"
    }}
  }},
  "Source_3": {{
    "link_and_source_name": "URL of source 3 - Website/Source name",
    "information": {{
      "information_1": "Information 1",
      "information_2": "Information 2", 
      "information_n": "Information n"
    }}
  }}
  "Source_n": {{
    "link_and_source_name": "URL of source n - Website/Source name",
    "information": {{
      "information_1": "Information 1",
      "information_2": "Information 2", 
      "information_n": "Information n"
    }}
  }}
}}"""
