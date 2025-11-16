"""
📝 Add Custom Source Text Prompt
System and user prompts for processing direct text input without URLs
"""

class AddCustomSourceTextPrompt:
    """Prompts for custom text source processing"""
    
    @staticmethod
    def get_system_prompt() -> str:
        """System prompt for custom text source analysis"""
        return """
        Role: You are an expert researcher who specializes in extracting relevant information from text content.
Goals: Extract information in the specified output format.

Process: 1. Understand the question for which you have to extract information.
2. Read the entire text content carefully.
3. Determine whether the contents have relevant information which can be used to satisfy the query.
4. If relevant information is found, then if it is too complex, break it down into pointers, else give output without breaking it down into pointers. Ensure that the individual pointer has meaningfully substantial information, it should not be incomplete in itself. All pointers should have substantial differentiation amongst them.

Output: Do not give additional information or comments. Use McKinsey's pyramid principle of communication which says that give the main point first and other details and explanation later on. Give the information re-written in a research-usable way which is short and to the point from the text in the format 
Output:
Don't include ```json in the output in the response
Provide your response in this exact JSON format:
IMPORTANT: Return ONLY the JSON response, no additional text or explanation.
If there is no information found, then only return "No information found" in the response
Response format must be exactly if information is found
{
  "Source": {
    "link_and_source_name": "Source Name - Custom Text Input",
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
    def get_user_prompt(source_name: str, text_content: str, heading: str = None, subsection: str = None) -> str:
        """User prompt with structured text input format"""
        
        prompt = f"""Input:
Source Name: {source_name}
Content: {text_content}
Heading: {heading if heading else "N/A"}
Subheading: {subsection if subsection else "N/A"}
Extract the most important information points from this text content and format them according to the specified JSON structure."""
        
        return prompt