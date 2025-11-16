from typing import Dict, List, Any, Union
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def gpt_keyword_intent_prompt(
    keywords: List[str],
) -> dict[str, str]:
    """
    Generate the FAQ prompt for blog content generation.
    
    Args:
        keywords: List of keywords for the blog post
    
    Returns:
        dict[str, str]: Dictionary containing system and user prompts with keys 'system' and 'user'
    """
    keywords = ', '.join(keywords)

    system_prompt = f"""Act as an SEO expert with the proficient knowlege about keywords. Your job is to accurately give the search intent of the keywords you receive in the input by understanding the goals and process for doing this."""

    user_prompt = f"""
    
Input:

Keywords: {keywords}

Goals: 

Suggest the intent of the keywords properly: Classify the keywords as falling into any one of these search intent categories:

Informational, Commercial, Transactional, Navigational

Process:

1. Step 1, Understand the explanation of the keyword intents described below:
Informational: The keyword indicates the user is seeking information or answers to a specific question. Example: 'How to apply for a visa.'
Navigational: The keyword suggests the user is trying to find a specific website, brand, or entity. Example: 'Facebook login.'
Transactional: The keyword shows the user intends to perform a specific action, such as making a purchase or signing up for a service. Example: 'Buy iPhone 14 online.'
Commercial: The keyword reflects pre-purchase research where the user is comparing products, services, or brands. Example: 'Best laptops under $1000.'

2. Step 2, Process the list of the keywords provided to you in input: Process all the keywords received by you in the input and run this prompt for all of them. Give the response for all the keywords and do not skip any keyword. 

3. Step 3, Classify the keyword with an appropriate search intent by understanding the classification criteria:
- Keywords with verbs like "how to," "guide," or "tips" ---> Informational.
- Keywords with a brand or website name directly ---> Navigational.
- Keywords with terms like "buy," "discount," or "book" ---> Transactional.
- Keywords with qualifiers like "best," "top," or "compare" ---> Commercial.

4. Step 4, Give the respective search intent for the keywords respective to them. 

5. Step 5, Respond only with the full name of the intent :
'Informational,' 'Navigational,' 'Transactional,' or 'Commercial'. 

Output:

Give the output in the single line string format seperated by commas.
Do not acknowledge the completion of the task. 
Do not make any additional comments to your response. 
Give only the search intent corresponding to the mentioned keyword(s) in your output. 
Include only one must-suited intent for one keyword. For keywords which can have mixed intent, suggest only the most suited one. 
Include the response for all the keywords strictly. 
    """

    return {
        "system": system_prompt,
        "user": user_prompt
    }
