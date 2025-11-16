from typing import Dict, List, Optional
from app.models.project import Project
from app.core.config import settings
from openai import OpenAI
import logging
import json
import re
from app.prompts.blogGenerator.outline_prompt import generate_outline_prompt
from typing import List
import uuid
from sqlalchemy.orm import Session
from app.utils.token_tracking import TokenTracker
from app.core.prompt_config import PromptType
from app.services.country_service import CountryService
from app.services.enhanced_llm_usage_service import EnhancedLLMUsageService


def get_outline_prompt_template(blog_title,
                primary_keyword,
                secondary_keywords,
                keyword_intent,
                industry,
                word_count,
                country,
                category,
                subcategory,
                # target_audience,
                project) -> str:
    """
    Retrieve the appropriate prompt template based on the subcategory.
    
    Args:
        subcategory (str, optional): The subcategory of the blog post. 
                                     Defaults to "default".
    
    Returns:
        str: The prompt template for the given subcategory
    """
    
    # Convert country code to full country name using CountryService
    logger = logging.getLogger(__name__)
    
    logger.info(f"=== OUTLINE GENERATION - COUNTRY CONVERSION ===")
    logger.info(f"Original country input: {country}")
    
    # Convert country code to full country name using classmethod
    converted_country = CountryService.get_country_name(country)
    
    logger.info(f"Converted country: {converted_country}")
    logger.info(f"Country conversion completed for outline generation")
    
    # Use the converted country name for all prompt templates
    country = converted_country
    from app.prompts.blogGenerator.outline.action_oriented import action_oriented_prompt
    if category=="Action-Oriented":
        myprompt = action_oriented_prompt(
            blog_title=blog_title,primary_keyword=primary_keyword,secondary_keywords=secondary_keywords,keyword_intent=keyword_intent,industry=industry,word_count=word_count,country=country,category=category,subcategory=subcategory,project=project
        )
        # print(f"myprompt: {myprompt}")
        return myprompt
    if category=="Audience-Based":
        from app.prompts.blogGenerator.outline.audience_or_geographic import audience_or_geographic_prompt
        return audience_or_geographic_prompt(
            blog_title=blog_title,primary_keyword=primary_keyword,secondary_keywords=secondary_keywords,keyword_intent=keyword_intent,industry=industry,word_count=word_count,country=country,category=category,subcategory=subcategory,project=project
        )
    if category=="Benefit-Focused":
        from app.prompts.blogGenerator.outline.benefits_focused import benefits_focused_prompt
        return benefits_focused_prompt(
            blog_title=blog_title,primary_keyword=primary_keyword,secondary_keywords=secondary_keywords,keyword_intent=keyword_intent,industry=industry,word_count=word_count,country=country,category=category,subcategory=subcategory,project=project
        )
    if category=="Comparative":
        from app.prompts.blogGenerator.outline.comparative import comparative_prompt
        return comparative_prompt(
             blog_title=blog_title,primary_keyword=primary_keyword,secondary_keywords=secondary_keywords,keyword_intent=keyword_intent,industry=industry,word_count=word_count,country=country,category=category,subcategory=subcategory,project=project
        )
    if category=="Creative and Unconventional":
        from app.prompts.blogGenerator.outline.creative_and_unique import creative_and_unique_prompt
        return creative_and_unique_prompt(
             blog_title=blog_title,primary_keyword=primary_keyword,secondary_keywords=secondary_keywords,keyword_intent=keyword_intent,industry=industry,word_count=word_count,country=country,category=category,subcategory=subcategory,project=project
        )
    if category=="Educational":
        from app.prompts.blogGenerator.outline.educational import educational_prompt
        return educational_prompt(
             blog_title=blog_title,primary_keyword=primary_keyword,secondary_keywords=secondary_keywords,keyword_intent=keyword_intent,industry=industry,word_count=word_count,country=country,category=category,subcategory=subcategory,project=project
        )
    if category=="Exploratory" or category=="Evaluative":
        from app.prompts.blogGenerator.outline.evaluative import evaluative_prompt
        return evaluative_prompt(
             blog_title=blog_title,primary_keyword=primary_keyword,secondary_keywords=secondary_keywords,keyword_intent=keyword_intent,industry=industry,word_count=word_count,country=country,category=category,subcategory=subcategory,project=project
        )
    if category=="Explanatory":
        from app.prompts.blogGenerator.outline.explanatory import explanatory_prompt
        return explanatory_prompt(
             blog_title=blog_title,primary_keyword=primary_keyword,secondary_keywords=secondary_keywords,keyword_intent=keyword_intent,industry=industry,word_count=word_count,country=country,category=category,subcategory=subcategory,project=project
        )
    if category=="Problem-Solving":
        from app.prompts.blogGenerator.outline.focus_or_problem_solving import focus_or_problem_solving_prompt
        return focus_or_problem_solving_prompt(
             blog_title=blog_title,primary_keyword=primary_keyword,secondary_keywords=secondary_keywords,keyword_intent=keyword_intent,industry=industry,word_count=word_count,country=country,category=category,subcategory=subcategory,project=project
        )
    if category=="Inspirational and Creative":
        from app.prompts.blogGenerator.outline.inspiration_and_creative import inspiration_and_creative_prompt
        return inspiration_and_creative_prompt(
             blog_title=blog_title,primary_keyword=primary_keyword,secondary_keywords=secondary_keywords,keyword_intent=keyword_intent,industry=industry,word_count=word_count,country=country,category=category,subcategory=subcategory,project=project
        )
    if category=="Predictive":
        from app.prompts.blogGenerator.outline.predictive import predictive_prompt
        return predictive_prompt(
             blog_title=blog_title,primary_keyword=primary_keyword,secondary_keywords=secondary_keywords,keyword_intent=keyword_intent,industry=industry,word_count=word_count,country=country,category=category,subcategory=subcategory,project=project
        )
    if category=="Strategic":
        from app.prompts.blogGenerator.outline.strategic_and_analytical import strategic_and_analytical_prompt
        return strategic_and_analytical_prompt(
             blog_title=blog_title,primary_keyword=primary_keyword,secondary_keywords=secondary_keywords,keyword_intent=keyword_intent,industry=industry,word_count=word_count,country=country,category=category,subcategory=subcategory,project=project
        )
    return action_oriented_prompt(
             blog_title=blog_title,primary_keyword=primary_keyword,secondary_keywords=secondary_keywords,keyword_intent=keyword_intent,industry=industry,word_count=word_count,country=country,category=category,subcategory=subcategory,project=project
        )


class OutlineGenerationService:
    def __init__(self, db: Session, user_id: str, project_id: Optional[str] = None):
        self.db = db
        self.user_id = user_id
        self.project_id = project_id
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.logger = logging.getLogger(__name__)
        
        # Initialize enhanced LLM usage service for billing
        self.llm_usage_service = EnhancedLLMUsageService(db)

    def parse_outline_to_json(self, outline_text: str) -> Dict:
        try:
            # If input is already a dictionary, return it directly
            if isinstance(outline_text, dict):
                return outline_text

            # Remove escape characters and clean the text
            cleaned_text = outline_text.replace('\\n', '').replace('\\"', '"').strip()
            
            # Try parsing the 'outline' field if it's a nested structure
            try:
                # If it's a nested dictionary with 'data' key
                if isinstance(outline_text, str):
                    parsed_dict = json.loads(outline_text)
                    if 'data' in parsed_dict and 'outline' in parsed_dict['data']:
                        cleaned_text = parsed_dict['data']['outline']
            except (json.JSONDecodeError, TypeError):
                pass

            # Parse the cleaned text as JSON
            try:
                outline_json = json.loads(cleaned_text)
            except json.JSONDecodeError:
                # If direct parsing fails, try to parse the nested string
                try:
                    outline_json = json.loads(cleaned_text.replace('\n', '').replace(' ', ''))
                except json.JSONDecodeError:
                    # Last resort: return a minimal valid structure
                    outline_json = {
                        "sections": [],
                        "conclusion": "",
                        "faqs": []
                    }

            # Ensure the structure has the required keys
            if not isinstance(outline_json, dict):
                outline_json = {
                    "sections": [],
                    "conclusion": "",
                    "faqs": []
                }

            # Validate and clean the structure
            if "sections" not in outline_json:
                outline_json["sections"] = []
            if "conclusion" not in outline_json:
                outline_json["conclusion"] = ""
            if "faqs" not in outline_json:
                outline_json["faqs"] = []

            # Return the parsed JSON with a consistent structure
            return {
                "status": "success",
                "message": "Outline generated successfully",
                "data": {
                    "status": "success",
                    "outline": cleaned_text,
                    "outline_json": outline_json,
                    "project_id": str(uuid.uuid4())
                }
            }

        except Exception as e:
            self.logger.error(f"Unexpected error parsing outline JSON: {str(e)}")
            return {
                "status": "error",
                "message": f"Failed to parse outline JSON: {str(e)}",
                "data": {
                    "status": "error",
                    "outline": outline_text,
                    "outline_json": {
                        "sections": [],
                        "conclusion": "",
                        "faqs": []
                    },
                    "project_id": str(uuid.uuid4())
                }
            }

    def generate_blog_outline(
        self,
        blog_title: str,
        primary_keyword: str,
        secondary_keywords: List[str],
        keyword_intent: str,
        industry: str,
        word_count: str,
        category: str,
        subcategory: str,
        project_id: str
    ) -> Dict:
        """Generate SEO-optimized blog outline."""
        try:
            # Update project_id if provided
            if project_id:
                self.project_id = project_id
            
            # Generate the outline prompt
            prompt = generate_outline_prompt(
                blog_title=blog_title,
                primary_keyword=primary_keyword,
                secondary_keywords=secondary_keywords,
                keyword_intent=keyword_intent,
                industry=industry,
                word_count=word_count,
                category=category,
                subcategory=subcategory
            )

            if prompt is None:
                # return error and status code
                return {"error": "Failed to generate outline prompt"}, 400

            # Call OpenAI to generate outline and record usage
            response = self.client.responses.create(
                model=settings.OPENAI_MODEL,
                 input=[
                    {"role": "system", "content": """You are the world’s most experienced and passionate SEO content writer. You write content which users love and thereby ranks highly on Google as well. Your role is to produce the content outline based on the inputs mentioned below for achieving the goals mentioned below and following the processes mentioned below. Ensure that the number of H2s strictly matches the word count criteria. 
Sub-heading Count Based on Word Count:
For 350 words:  
Sritctly include only 1 H2.
Include  a maximum of 3 most important H3s, directly addressing the concept or query mentioned in the title. 
Do not cover the foundational understanding of the topic unless required.
For 850 words: Strictly include only 1-2 H2s 
For 1250 words: Strictly include only 2-3 H2s 
For 2000 words: Strictly include only 3-5 H2s
For all blogs with titles that include words such as “steps”, “process”, “guide”, "how to", “do's and don'ts”, “shortcuts”, “benefits”, “advantages”, “impact”, “usp”, “strategies”, “techniques”, “game plans”, “roadmaps”, “principles”, “best practices”, “challenges”, “common pitfalls”, “mistakes to avoid”, “step-by-step resolutions”, “opportunities”, “risks”, “innovation”, “evolution”, or “consumer behavior changes”, “trends”, “predictions” and all the sub-categories falling under Comparitive category - DO NOT include any introduction-style or top-of-the-funnel explainers. For these, strictly avoid any top-of-the-funnel section headings such as attempt to explain ‘why it is important’, ‘what it is’, or ‘why you should do it’ as separate H2s.
Start ONLY with the main process or the first relevant step. Skip any and all conceptual outlines for these unless very necessary."""},
                    {"role": "user", "content": prompt}
                ],
                temperature=settings.OPENAI_TEMPERATURE,
                max_output_tokens=settings.OPENAI_MAX_TOKENS
            )
            
            # Record LLM usage with billing
            outline_metadata = {
                "outline_generation": {
                    "blog_title": blog_title,
                    "primary_keyword": primary_keyword,
                    "category": category,
                    "subcategory": subcategory
                }
            }
            
            result = self.llm_usage_service.record_llm_usage(
                user_id=self.user_id,
                service_name="outline_generation",
                model_name=response.model,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                service_description="Blog outline generation using OpenAI",
                project_id=self.project_id,
                additional_metadata=outline_metadata
            )
            
            self.logger.info(f"✅ Recorded outline generation usage: {result}")

            outline_text = response.output_text
            
            # Parse outline to JSON
            try:
                outline_json = json.loads(outline_text)
            except json.JSONDecodeError:
                # If direct JSON parsing fails, try to extract JSON from text
                import re
                
                # Look for JSON-like content between {{ }}
                json_match = re.search(r'\{\{(.*?)\}\}', outline_text, re.DOTALL)
                if json_match:
                    try:
                        outline_json = json.loads(json_match.group(1).strip())
                    except json.JSONDecodeError:
                        # If still no luck, fall back to text parsing
                        outline_json = self.parse_outline_to_json(outline_text)
                else:
                    # If still no luck, fall back to text parsing
                    outline_json = self.parse_outline_to_json(outline_text)
            

            return {
                "status": "success",
                "outline": outline_text,
                "outline_json": outline_json,
                "project_id": project_id
            }

        except Exception as e:
            self.logger.error(f"Error generating outline: {str(e)}")
            return {
                "status": "error",
                "message": str(e)
            }
        finally:
            self.logger.info("Executed generate_blog_outline")


    def generate_blog_outline_updated(
        self,
        blog_title: str,
        primary_keyword: str,
        secondary_keywords: List[str],
        keyword_intent: str,
        industry: str,
        word_count: str,
        country: str,
        category: str,
        subcategory: str,
        project_id: str,
        project: Dict
    ) -> Dict:
        """Generate SEO-optimized blog outline."""
        try:
            # Log outline generation parameters including country
            self.logger.info(f"=== OUTLINE GENERATION SERVICE - PARAMETERS ===")
            self.logger.info(f"Blog title: {blog_title}")
            self.logger.info(f"Primary keyword: {primary_keyword}")
            self.logger.info(f"Country parameter: {country}")
            self.logger.info(f"Category: {category}")
            self.logger.info(f"Subcategory: {subcategory}")
            
            # Update project_id if provided
            if project_id:
                self.project_id = project_id

            prompt = get_outline_prompt_template(
                blog_title=blog_title,
                primary_keyword=primary_keyword,
                secondary_keywords=secondary_keywords,
                keyword_intent=keyword_intent,
                industry=industry,
                word_count=word_count,
                country=country,
                category=category,
                subcategory=subcategory,
                # target_audience=project.age_groups,
                project=project
            )

            # self.logger.info(f"prompt: {prompt}")

            # Call OpenAI to generate outline and record usage
            response = self.client.responses.create(
                model=settings.OPENAI_MODEL,
                 input=[
                        {"role": "system", "content": """You are the world’s most experienced and passionate SEO content writer. You write content which users love and thereby ranks highly on Google as well. Your role is to produce the content outline based on the inputs mentioned below for achieving the goals mentioned below and following the processes mentioned below. Ensure that the number of H2s strictly matches the word count criteria. 
Sub-heading Count Based on Word Count:
For 350 words:  
Sritctly include only 1 H2.
Include  a maximum of 3 most important H3s, directly addressing the concept or query mentioned in the title. 
Do not cover the foundational understanding of the topic unless required.
For 850 words: Strictly include only 1-2 H2s 
For 1250 words: Strictly include only 2-3 H2s 
For 2000 words: Strictly include only 3-5 H2s
For all blogs with titles that include words such as “steps”, “process”, “guide”, "how to", “do's and don'ts”, “shortcuts”, “benefits”, “advantages”, “impact”, “usp”, “strategies”, “techniques”, “game plans”, “roadmaps”, “principles”, “best practices”, “challenges”, “common pitfalls”, “mistakes to avoid”, “step-by-step resolutions”, “opportunities”, “risks”, “innovation”, “evolution”, or “consumer behavior changes”, “trends”, “predictions” and all the sub-categories falling under Comparitive category - DO NOT include any introduction-style or top-of-the-funnel explainers. For these, strictly avoid any top-of-the-funnel section headings such as attempt to explain ‘why it is important’, ‘what it is’, or ‘why you should do it’ as separate H2s.
Start ONLY with the main process or the first relevant step. Skip any and all conceptual outlines for these unless very necessary.
 """},
                    {"role": "user", "content": prompt}
                ],
                temperature=settings.OPENAI_TEMPERATURE,
                max_output_tokens=settings.OPENAI_MAX_TOKENS
            )
                
            # Record LLM usage with billing
            outline_metadata = {
                "outline_generation": {
                    "blog_title": blog_title,
                    "primary_keyword": primary_keyword,
                    "category": category,
                    "subcategory": subcategory,
                    "word_count": word_count,
                    "country": country
                }
            }
            
            result = self.llm_usage_service.record_llm_usage(
                user_id=self.user_id,
                service_name="outline_generation",
                model_name=response.model,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                service_description="Blog outline generation using OpenAI (Updated)",
                project_id=self.project_id,
                additional_metadata=outline_metadata
            )
            
            self.logger.info(f"✅ Recorded outline generation usage: {result}")

            outline_text = response.output_text
            
            # Parse outline to JSON
            try:
                outline_json = json.loads(outline_text)
            except json.JSONDecodeError:
                # If direct JSON parsing fails, try to extract JSON from text
                import re
                
                # Look for JSON-like content between {{ }}
                json_match = re.search(r'\{\{(.*?)\}\}', outline_text, re.DOTALL)
                if json_match:
                    try:
                        outline_json = json.loads(json_match.group(1).strip())
                    except json.JSONDecodeError:
                        # If still no luck, fall back to text parsing
                        outline_json = self.parse_outline_to_json(outline_text)
                else:
                    # If still no luck, fall back to text parsing
                    outline_json = self.parse_outline_to_json(outline_text)
            

            return {
                "status": "success",
                "outline": outline_text,
                "outline_json": outline_json,
                "project_id": project_id
            }

        except Exception as e:
            self.logger.error(f"Error generating outline: {str(e)}")
            return {
                "status": "error",
                "message": str(e)
            }
        finally:
            self.logger.info("Executed generate_blog_outline")