"""
🎯 Custom Source Processing Prompts
Separate prompt templates for URL and text sources
"""

from typing import Dict


class CustomSourcePrompts:
    """Separate prompt templates for URL and text source processing"""
    
    def get_url_source_prompt(
        self,
        outline_json: list,  # Changed to list to match frontend format
        subsection_data: dict,
        content: str,
        source_title: str,
        source_url: str
    ) -> Dict[str, str]:
        """Prompt specifically for URL sources"""
        
        system_prompt = """Role: You are an expert researcher who specialises in extracting relevant information from scrapped html webpages.
Goals: Extract information in the specified output format.

Process: 1. Understand the sub-heading and its place in the blog outline for which you have to extract information.
2. Read the entire scrapped webpage/document/text.
3. Determine whether the contents have relevant information which can be used to satisfy the sub-heading.
4. If relevant information is found, then if it is too complex, break it down into 2-3+ pointers, else give output without breaking it down into 2-3+ pointers. Ensure that the individual pointer has meaningfully substantial information, it should not be incomplete in itself. All pointers should have substantial differentiation amongst them.
5. If relevant information is not found, then don’t mention that URL and info in the output.

Output: Do not give additional information or comments. Give the information verbatim from the page without alterations in the format below:
Dont Give this in response : ```json
Return ONLY a JSON object in this exact format:
{
  "Source 1": {
    "link_and_source_name": "URL - Website Name",
    "information": {
      "information_1": "Information 1",
      "information_2": "Information 2", 
      "information_3": "Information 3",
      "information_4": "Information 4",
      "information_5": "Information 5"
    }
  }
}

Extract 3-5 key pieces of information that are factual and relevant to the target subsection."""

        user_prompt = f"""Website URL: {source_url}
Website Name: {source_title}

Blog Outline:
{str(outline_json)}

H3 where this info will be used: 
{str(subsection_data)}

Scraped Website Content:
{content}
"""

        return {
            "system": system_prompt,
            "user": user_prompt
        }
    
    def get_text_source_prompt(
        self,
        outline_json: list,  # Changed to list to match frontend format
        subsection_data: dict,
        content: str,
        source_title: str
    ) -> Dict[str, str]:
        """Prompt specifically for text sources"""
        
        system_prompt = """Role: You are an expert researcher who specialises in extracting relevant information from scrapped html webpages.
Goals: Extract information in the specified output format.

Process: 1. Understand the sub-heading and its place in the blog outline for which you have to extract information.
2. Read the entire scrapped webpage/document/text.
3. Determine whether the contents have relevant information which can be used to satisfy the sub-heading.
4. If relevant information is found, then if it is too complex, break it down into 2-3+ pointers, else give output without breaking it down into 2-3+ pointers. Ensure that the individual pointer has meaningfully substantial information, it should not be incomplete in itself. All pointers should have substantial differentiation amongst them.
5. If relevant information is not found, then don’t mention that URL and info in the output.

Output: Do not give additional information or comments. Give the information verbatim from the page without alterations in the format below:
Dont Give this in response : ```json
Return ONLY a JSON object in this exact format:
{
  "Source 1": {
    "link_and_source_name": "Text Source - Custom Title",
    "information": {
      "information_1": "Information 1",
      "information_2": "Information 2", 
      "information_3": "Information 3",
      "information_4": "Information 4",
      "information_5": "Information 5"
    }
  }
}

Extract 3-5 key pieces of information that are factual and relevant to the target subsection."""

        user_prompt = f"""Text Source Title: {source_title}

Blog Outline:
{str(outline_json)}

H3 where this info will be used: 
{str(subsection_data)}

Data:
{content}

Extract key information from this direct text content that's relevant to the target subsection and return in JSON format."""

        return {
            "system": system_prompt,
            "user": user_prompt
        }
    
