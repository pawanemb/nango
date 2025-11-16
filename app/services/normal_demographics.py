from typing import Dict, Any, List
from app.services.openai_service import OpenAIService
from app.services.mongodb_service import MongoDBService
import logging
import json
import re

logger = logging.getLogger(__name__)

def extract_json_from_markdown(text: str) -> Dict[str, Any]:
    """
    Extract and parse JSON content from markdown code blocks.
    """
    # Try to find JSON code block
    json_pattern = r"```(?:json)?\n([\s\S]*?)\n```"
    match = re.search(json_pattern, text)
    
    if match:
        json_str = match.group(1).strip()
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {str(e)}")
            raise ValueError(f"Invalid JSON format: {str(e)}")
    else:
        # If no code block found, try parsing the text directly
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {str(e)}")
            raise ValueError(f"Invalid JSON format: {str(e)}")

def analyze_demographics(
    project_id: str,
    url: str,
    services: List[str],
    business_type: str,
    html_content: str,
    user_id: str = None  # Add user_id parameter with default None
) -> Dict[str, Any]:
    """
    Analyze website content to determine target demographics using OpenAI.
    
    Args:
        project_id: The project ID
        url: The website URL
        services: List of identified services
        business_type: Type of business
        html_content: The website HTML content
        user_id: User ID for token tracking (optional, defaults to "system")
        
    Returns:
        Dict containing demographic analysis
    """
    try:
        # Import here to avoid circular imports
        from app.db.session import get_db_session
        
        # Use provided user_id or default to "system"
        effective_user_id = user_id if user_id else "system"
        
        # Create OpenAI service with proper database session
        with get_db_session() as db_session:
            openai_service = OpenAIService(
                db=db_session, 
                user_id=effective_user_id,
                project_id=project_id
            )
            
            # Get demographic analysis from OpenAI
            analysis_result = openai_service.analyze_demographics(
                html_content=html_content,
                services=services,
                business_type=business_type
            )
            
            if analysis_result.get("status") == "error":
                logger.error("OpenAI analysis failed: " + str(analysis_result.get('error')))
                return {
                    "status": "error",
                    "error": analysis_result.get("error"),
                    "error_type": analysis_result.get("error_type")
                }
            
            # Parse the demographics JSON from markdown
            demographics_str = analysis_result.get("analysis")
            try:
                demographics_data = extract_json_from_markdown(demographics_str)
            except ValueError as e:
                logger.error("Failed to parse demographics JSON: " + str(e))
                return {
                    "status": "error",
                    "error": f"Failed to parse demographics data: {str(e)}",
                    "error_type": "JSONParseError"
                }
                
            # Store results in MongoDB
            try:
                mongodb_service = MongoDBService()
                content = mongodb_service.get_content_by_url_sync(project_id=project_id, url=url)
                if content:
                    content.demographics = demographics_data
                    MongoDBService.update_content(content)
                    
            except Exception as e:
                logger.error("Failed to store demographics in MongoDB: " + str(e))
                # Continue execution as this is not critical
                
            return {
                "status": "success",
                "project_id": project_id,
                "url": url,
                "demographics": demographics_data,
                "ai_meta": {
                    "model": analysis_result.get("model"),
                    "tokens_used": analysis_result.get("tokens_used")
                }
            }
        
    except Exception as e:
        logger.error("Demographics analysis failed: " + str(e))
        return {
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__
        }

# Example usage
async def main():
    try:
        result = await analyze_demographics(
            project_id="test_project",
            url="http://example.com",
            services=["web design", "digital marketing"],
            business_type="Technology",
            html_content="<html>Test content</html>"
        )
        print(json.dumps(result, indent=2))
    except Exception as e:
        logger.error(f"Demographics analysis failed: {str(e)}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
