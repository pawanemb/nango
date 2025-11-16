"""
🔗 Add Custom Source Prompt
System and user prompts for processing single URL with RayoScraper data
"""

class AddCustomSourcePrompt:
    """Prompts for custom source processing"""
    
    @staticmethod
    def get_system_prompt() -> str:
        """System prompt for custom source analysis"""
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
IMPORTANT: Return ONLY the JSON response, no additional text or explanation.
If there is no information found, then only return "No information found" in the response
Response format must be exactly if information is found
{
  "Source": {
    "link_and_source_name": "URL of source - Website/Source name",
    "information": {
      "information_1": "Information 1",
      "information_2": "Information 2",
      "information_3": "Information 3",
      "information_4": "Information 4",
      "information_5": "Information 5"
    }
  }
}"""

    @staticmethod
    def get_user_prompt(url: str, scraped_content: str, heading: str = None, subsection: str = None) -> str:
        """Simple user prompt with structured input format"""
        
        prompt = f"""Input:
URL: {url}
Content: {scraped_content}
Heading: {heading}
Subheading: {subsection}
Extract the most important information points and format them according to the specified JSON structure."""
        
        return prompt