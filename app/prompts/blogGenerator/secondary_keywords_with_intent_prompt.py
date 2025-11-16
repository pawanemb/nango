from typing import List, Dict
from app.models.project import Project

def secondary_keywords_with_intent_prompt(
    primary_keyword: str,
    project: Project,
    country: str,
    intent: str,
    language_preference: str = "en"
) -> Dict[str, str]:
    """
    Generate prompt for creating secondary keywords WITH intent classification in single call.
    
    Returns both keywords and their intents in structured format to eliminate the need
    for a second AI call for intent analysis.
    """

    system_prompt = f"""Act as world’s best SEO manager who is well versed with the concepts of keywords and knows its importance in improving the quality of the blog. Your task is to suggest the right combination of secondary keywords based on the primary keyword entered by the user by understanding the goals for the same. 
"""

    user_prompt = f"""Input:
Primary Keyword: {primary_keyword}
Intent Hint: {intent}
Language Preference: {language_preference}
Target Location: {country}
Project Industries: {', '.join(project.industries) if project.industries else 'general'}
Target Age Groups: {', '.join(project.age_groups) if project.age_groups else 'all ages'}
Goals:
Understand the primary keyword: The primary keyword will be the main focus of the blog generation. You must understand it to give the relevant secondary keyword suggestions to the users. Based on the primary keyword selection, you must understand the purpose of blog creation and give suggestions accordingly which complements it.
Understand the intent of the primary keyword: Understand the intent of the primary keyword to give the secondary keyword suggestions. The intent of the secondary keywords can be different from the intent of the primary keyword (basically they can be combined). You must take reference to the explanation of the intent:
Informational: The keyword indicates the user is seeking information or answers to a specific question. Example: 'How to apply for a visa.'
Navigational: The keyword suggests the user is trying to find a specific website, brand, or entity. Example: 'Facebook login.'
Transactional: The keyword shows the user intends to perform a specific action, such as making a purchase or signing up for a service. Example: 'Buy iPhone 14 online.'
Commercial: The keyword reflects pre-purchase research where the user is comparing products, services, or brands. Example: 'Best laptops under $1000.'
Keep a mix of short and long tail keywords: Keep a mix of short tail and long tail keywords for giving the suggestions of secondary keywords. Short tail keywords which are equal or less than three words. For example - digital marketing. Long tail keywords on the other hand are made with phrase specific searches and are longer. For example - what is digital marketing.
High search volume: Suggest related popular keywords as the secondary keywords suggestion.
Keep a mix of synonyms, subtopics, related keywords and long tail keywords: Keep a mix of keywords which are synonyms, subtopics, related keywords and long tail keywords of the primary keyword. This will offer users a better choice of keywords to select.
Understand Language Preference: Understand the language preference of the website between English (UK) and English (USA). You must give the keyword suggestions based on this only. For example, if the user has selected English (UK) as their language preference, then words like 'recognize' must be written as 'recognise' to support the preference.
Incorporate real-time web search data: Perform a real-time web search to gather the most relevant secondary keywords based on the primary keyword. This includes mining Google's live "People Also Ask," "Related Searches," and Autocomplete results for the primary keyword. Ensure that the secondary keywords reflect current trends and user queries.
Steps:
Step 1, Understand the primary keyword and intent: Understand the meaning of the input keyword and ensure that your suggestions are a mix of synonyms, subtopics, related keywords and long tail keywords that can be clustered with the primary keyword.
Step 2, Understand Intent: Understand the intent (commercial, informational, navigational, transactional) of the keyword. Suggest keywords of the same intent.
Step 3, Understand Branded vs Non-Branded nature: Branded keywords contain a brand name and non-branded keywords don’t contain a brand name. Detect the nature of the keyword and suggest the same nature of keywords.
Step 4, Optimise for volume (MANDATORY): Suggest popular keywords as secondary keywords that are closely searched by the users searching the primary keyword as they would have higher search volumes. Apply a strict commercial-intent filter, prioritizing keywords that target broad, mainstream problems or purchase-intent questions, as these inherently have higher search demand than niche or obscure queries.
Step 5, Integrate real-time search insights (MANDATORY): Conduct a real-time web search (for the primary keyword) to extract the most relevant secondary keywords from Google's "People Also Ask," "Related Searches," and Autocomplete results. This ensures the suggestions are aligned with current user interests and search behaviours. (eg. If I search google pixel, and a new model X has just come out the previous day, then one of the secondary keywords should be "Google pixel X"). This step is very important and is a direct test of your ability to follow prompts perfectly.
Output (STRICT):
Give the final output in a single line, with each keyword immediately followed by its intent in parentheses (See 8.)
1. Give output in a single line with values separated by commas.
2. Do not include any explanation or any other details apart from the secondary keywords in the response. 
3. The list of secondary keywords should be a maximum of 20 and a minimum of 10 keywords. 
4. Curate the list to be a strategic blend of suggestions derived from both Step 4 and Step 5. You must include foundational, high-volume commercial keywords alongside timely, real-time keywords that reflect the most current search trends and user questions.
5. Do not mention the primary keyword in the output.
6. Do not acknowledge the completion of the task. 
7. Do not make any additional comments. 

Output Format (CRITICAL - Follow Exactly):
Return a JSON object with this exact structure:

{{
  "keywords": [
    {{"keyword": "keyword 1", "intent": "Commercial"}},
    {{"keyword": "keyword 2", "intent": "Informational"}},
    {{"keyword": "keyword 3", "intent": "Transactional"}},
    {{"keyword": "keyword 4", "intent": "Informational"}}
  ]
}}
"""

    return {"system": system_prompt, "user": user_prompt}