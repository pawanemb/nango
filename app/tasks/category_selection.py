from typing import Dict, List, Optional
from celery import chain
from app.celery_config import celery_app as celery
from app.core.config import settings
from app.core.logging_config import logger
from datetime import datetime
import openai
from openai import OpenAI
import httpx
from app.models.project import Project
from sqlalchemy.orm import Session
from app.db.session import SessionLocal

# Initialize OpenAI client
client = OpenAI(api_key=settings.OPENAI_API_KEY)

def generate_intent_prompt(keyword: str) -> str:
    """Generate prompt for determining keyword intent."""
    
    prompt = f"""Act as an SEO expert with the proficient knowlege about keywords. Classify the given keyword into one of the following categories based on its search intent:

1. **Informational**: The keyword indicates the user is seeking information or answers to a specific question. Example: 'How to apply for a visa.'
2. **Navigational**: The keyword suggests the user is trying to find a specific website, brand, or entity. Example: 'Facebook login.'
3. **Transactional**: The keyword shows the user intends to perform a specific action, such as making a purchase or signing up for a service. Example: 'Buy iPhone 14 online.'
4. **Commercial**: The keyword reflects pre-purchase research where the user is comparing products, services, or brands. Example: 'Best laptops under $1000.'

**Classification Criteria**:
- Keywords with verbs like "how to," "guide," or "tips" → **Informational**.
- Keywords with a brand or website name directly → **Navigational**.
- Keywords with terms like "buy," "discount," or "book" → **Transactional**.
- Keywords with qualifiers like "best," "top," or "compare" → **Commercial**.

**Instruction**: Respond only with the full name of the intent -'Informational,' 'Navigational,' 'Transactional,' or 'Commercial'. Do not include anything else in your response.

**Keyword**: {keyword}"""

    return prompt

def generate_category_prompt(
    primary_keyword: str,
    intent: str,
    secondary_keywords: List[str],
    industry: str,
    target_audience: str
) -> str:
    """Generate prompt for determining content categories."""
    
    secondary_keywords_str = ", ".join(secondary_keywords) if secondary_keywords else ""
    
    prompt = f"""Act as an SEO expert specializing in writing SEO-friendly content pieces and well-versed with the concepts of keywords and SEO-friendly blog titles. Based on the given primary keyword, provide options to select the most relevant blog post title categories, aligned with the keyword's intent.

Input Details:
Primary Keyword: {primary_keyword}
Intent: {intent}
Secondary Keywords (for reference): {secondary_keywords_str}
Industry (for context): {industry}
Target Audience (for reference): {target_audience}

Output Instructions:
1. Suggest only the most relevant categories and subcategories corresponding to the keyword's intent.
2. Group subcategories under their respective Blog Categories.
3. Do not give comma-separated values in the sub-categories.
4. Give the output in tabular format only with headers: Intent, Blog Category, Subcategories.
5. Avoid repetition of values across the table.
6. Do not provide blog titles unless explicitly asked.
7. Do not make any additional comments & do not acknowledge the task."""

    return prompt

@celery.task(name="category_selection.get_keyword_intent", queue="category_selection")
def get_keyword_intent(keyword: str) -> str:
    """Get the intent classification for a keyword using OpenAI."""
    try:
        prompt = generate_intent_prompt(keyword)
        
        response = client.responses.create(
            model=settings.OPENAI_MODEL_MINI,
             input=[
                {"role": "system", "content": "You are an expert SEO specialist."},
                {"role": "user", "content": prompt}
            ],
            temperature=settings.OPENAI_TEMPERATURE,
            max_output_tokens=settings.OPENAI_MAX_TOKENS
        )
        
        intent = response.output_text.strip()
        if intent not in ["Informational", "Navigational", "Transactional", "Commercial"]:
            raise ValueError(f"Invalid intent classification: {intent}")
            
        return intent
        
    except Exception as e:
        logger.error(f"Error getting keyword intent: {str(e)}")
        raise

@celery.task(name="category_selection.get_content_categories", queue="category_selection")
def get_content_categories(
    intent: str,
    primary_keyword: str,
    secondary_keywords: List[str],
    project_id: str
) -> Dict:
    """Get content categories based on keyword and intent.
    
    Args:
        intent: The search intent from get_keyword_intent task
        primary_keyword: The main keyword
        secondary_keywords: List of related keywords
        project_id: Project ID
    """
    try:
        # Get project details
        db = SessionLocal()
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise ValueError(f"Project not found with id: {project_id}")
            
        # Join all industries with comma
        industry = ", ".join(project.industries) if project.industries else "general"
        # Use age_groups as target audience
        target_audience = ", ".join(project.age_groups) if project.age_groups else "general audience"
        
        prompt = generate_category_prompt(
            primary_keyword=primary_keyword,
            intent=intent,
            secondary_keywords=secondary_keywords,
            industry=industry,
            target_audience=target_audience
        )
        
        response = client.responses.create(
            model=settings.OPENAI_MODEL,
             input=[
                {"role": "system", "content": "You are an expert SEO content strategist."},
                {"role": "user", "content": prompt}
            ],
            temperature=settings.OPENAI_TEMPERATURE,
            max_output_tokens=settings.OPENAI_MAX_TOKENS
        )
        
        categories_table = response.output_text.strip()
        
        return {
            "primary_keyword": primary_keyword,
            "intent": intent,
            "categories_table": categories_table
        }
        
    except Exception as e:
        logger.error(f"Error getting content categories: {str(e)}")
        raise
    finally:
        db.close()

@celery.task(name="category_selection.parse_categories_table", queue="category_selection")
def parse_categories_table(result: Dict) -> Dict:
    """Parse the categories table into a structured JSON format.
    
    Args:
        result: The result dictionary containing the categories table
    """
    try:
        table_str = result["categories_table"]
        lines = table_str.strip().split('\n')
        
        # Remove the header and separator lines
        content_lines = [line for line in lines[2:] if line.strip()]  # Skip header and separator
        
        categories = []
        current_category = None
        current_subcategories = []
        
        for line in content_lines:
            # Split the line by | and remove empty spaces
            columns = [col.strip() for col in line.split('|')[1:-1]]  # Remove first and last empty elements
            
            intent = columns[0]
            category = columns[1]
            subcategory = columns[2]
            
            if category:  # New category
                if current_category:  # Save previous category
                    categories.append({
                        "category": current_category,
                        "subcategories": current_subcategories
                    })
                current_category = category
                current_subcategories = [subcategory] if subcategory else []
            else:  # Continue with current category
                if subcategory:
                    current_subcategories.append(subcategory)
        
        # Add the last category
        if current_category:
            categories.append({
                "category": current_category,
                "subcategories": current_subcategories
            })
        
        return {
            "primary_keyword": result["primary_keyword"],
            "intent": result["intent"],
            "categories": categories
        }
        
    except Exception as e:
        logger.error(f"Error parsing categories table: {str(e)}")
        raise

def create_category_selection_chain(
    primary_keyword: str,
    secondary_keywords: List[str],
    project_id: str
):
    """Create a chain of tasks for category selection process."""
    # Create and apply the chain
    task_chain = chain(
        get_keyword_intent.s(primary_keyword),
        get_content_categories.s(primary_keyword=primary_keyword, secondary_keywords=secondary_keywords, project_id=project_id),
        parse_categories_table.s()
    )
    
    # Apply the chain to get a result that can be tracked
    result = task_chain.apply_async()
    return result
