"""
Brand tone analysis prompts for OpenAI service.
"""

BRAND_TONE_SYSTEM_PROMPT = """You are a content scanner whose job is to fetch the brand copy of the website from the scraped homepage mentioned in the input."""

BRAND_TONE_USER_PROMPT = """Goal:
 You need to return a brand copy verbatim from the website, such that it can be analysed to understand its tonality. Do not write one yourself.

Process:
 Step 1: Read through the entire HTML of the page. 
Step 2: Find brand copies from the HTML text. 
Step 3: Decide which copy reflects the brand.
 Step 4: Give output as per my output instructions.

Output:
Instruction 1- Do not give multiple copies but one single copy. 
Instruction 2: Do not give images or links.
 Instruction 3-Do not give any UI labels in your response.
 Instruction 4-Do not return multiple unassociated copies but a single copy. 
Instruction 5-Do not write a copy from your end. 
Instruction 6- Copy should be a minimum of 15 words. Follow this instruction very strictly as it is critical for the success of the task. 
Instruction 7 - Keep the letter case of the response the same as mentioned in the original copy in the input website homepage.

Input:
Scrapped website homepage: {html_content}
"""

def get_brand_tone_prompts(html_content: str) -> tuple[str, str]:
    """
    Get system and user prompts for brand tone analysis.
    
    Args:
        html_content: The website HTML content to analyze
        
    Returns:
        tuple: (system_prompt, user_prompt)
    """
    system_prompt = BRAND_TONE_SYSTEM_PROMPT
    user_prompt = BRAND_TONE_USER_PROMPT.format(html_content=html_content[:8000])
    
    return system_prompt, user_prompt