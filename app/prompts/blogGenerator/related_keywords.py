from app.models.project import Project
from app.services.country_service import CountryService
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def related_keywords_prompt(primary_keyword: str, country: str, project: Project) -> dict[str, str]:
    """
    Generate the related keywords prompt for keyword suggestions with country context.
    
    Args:
        primary_keyword: Main keyword to find related keywords for
        country: Country code (e.g., 'in', 'us', 'gb') for localization - converted to full name
        project: Project object containing website and other details
    
    Returns:
        dict[str, str]: Dictionary containing system and user prompts with country context
    """
    # Extract language preference from project
    language_preference = "English (USA)"  # Default fallback
    project_languages = project.languages if project.languages else []
    if project_languages and len(project_languages) > 0:
        # Project stores: ["English (USA)"] or ["English (UK)"]
        language_preference = project_languages[0]  # Take first language
        logger.info(f"Extracted language preference from project: '{language_preference}'")
    else:
        logger.warning(f"No language preference found in project {project.id}, using default: '{language_preference}'")
    
    # Convert country code to full country name
    try:
        target_country = CountryService.get_country_name(country)
        logger.info(f"Converted country code '{country}' to '{target_country}'")
    except ValueError as e:
        logger.warning(f"Failed to convert country code '{country}': {str(e)}")
        target_country = country.upper()  # Fallback to uppercase country code
    
    website = project.url
    target_audience = ", ".join(project.age_groups) if project.age_groups else "general audience"
    industry = ", ".join(project.industries) if project.industries else "general"
    current_date = datetime.now().strftime("%Y-%m-%d")
    system_prompt = """Role: You are the world’s most experienced and passionate SEO Manager. Your speciality is that you are great at keyword strategy and research."""

    user_prompt = f"""
    Input:
User Keyword Search: {primary_keyword}
Language preference: {language_preference}
Target Country: {target_country}
Current Date: {current_date}
  
Goal:
Find similar keywords: Find keywords that are similar to the one entered by the user.
High search volume: Suggest related popular keywords.
Target Country Context: Consider the target country for localized keyword suggestions. Generate keywords that are relevant and popular in the specified country market.
Understand Language Preference: Understand the language preference of the website between English (UK) and English (USA). You must give the keyword suggestions based on this only. For example, if the user has selected English (UK) as their language preference, then words like 'recognize' must be written as 'recognise' to support the preference.
Process:
Step 1, Understand Input Keyword’s meaning: Understand the meaning of the input keyword and ensure that your suggestions are of a very similar meaning.
Step 2, Understand Intent: Understand the intent (commercial, informational, navigational, transactional) of the keyword. Suggest keywords of the same intent.
Step 3, Understand Branded vs Non-Branded nature: Branded keywords contain a brand name and non-branded keywords don’t contain a brand name. Detect the nature of the keyword and suggest the same nature of keywords.
Step 4, Optimise for volume: Suggest shorter keywords as they tend to have a higher volume than longtail keywords.
Output:
Give a list of keywords in JSON format.
Do not give any other comments.
Give a minimum of 3 keyword suggestions and a maximum of 7.
Only give keywords in output. Nothing else at all. This is very critical.
Don't give ```json in the output

[
  "first keyword example",
  "second keyword example",
  "third keyword example"
]

IMPORTANT: Your entire response should be just the JSON array. No other text or formatting."""

    return {
        "system": system_prompt,
        "user": user_prompt
    }
