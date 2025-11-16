from typing import Dict, List, Optional
from datetime import datetime
import os
import json

from openai import OpenAI
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging_config import logger
from fastapi import HTTPException
from app.services.enhanced_llm_usage_service import EnhancedLLMUsageService

class MetaDescriptionService:
    def __init__(self, 
                 db: Session,
                 user_id: str,
                 project_id: Optional[str] = None,
                 openai_api_key: Optional[str] = None, 
                 database_uri: Optional[str] = None):
        """
        Initialize MetaDescriptionService.
        
        :param db: Database session
        :param user_id: User ID for tracking
        :param project_id: Project ID for tracking
        :param openai_api_key: OpenAI API key. If not provided, uses settings.
        :param database_uri: Optional database URI. If not provided, tries to get from settings or environment.
        """
        self.db = db
        self.user_id = user_id
        self.project_id = project_id
        self.openai_client = OpenAI(
            api_key=openai_api_key or getattr(settings, 'OPENAI_API_KEY', 
                                              os.getenv('OPENAI_API_KEY'))
        )
        self.logger = logger
        
        # Initialize enhanced LLM usage service for billing
        self.llm_usage_service = EnhancedLLMUsageService(db)
        

    def generate_meta_description_prompt(
        self,
        primary_keyword: str,
        title: str,
        intent: Optional[str] = None,
        secondary_keywords: Optional[List[str]] = None,
        language_preference: Optional[str] = None,
        project: Optional[object] = None
    ) -> str:
        """
        Generate prompt for creating meta descriptions.
        
        :param primary_keyword: Primary keyword for SEO optimization
        :param title: The blog/page title
        :param intent: Search intent (optional)
        :param secondary_keywords: Optional list of secondary keywords
        :param language_preference: Optional language preference
        :param project: Project object with additional context
        :return: Formatted prompt string
        """
        secondary_keywords_str = ", ".join(secondary_keywords) if secondary_keywords else ""
        current_date = datetime.now().strftime("%Y-%m-%d")
        
        # Get project context if available
        industry = "general"
        target_audience = "general audience"
        languages = ["English"]
        
        if project:
            industry = getattr(project, 'industry', 'general')
            target_audience = getattr(project, 'target_audience', 'general audience')
            languages = getattr(project, 'languages', ['English'])
        
        # Use language preference if provided, otherwise use project languages
        if language_preference:
            language_context = language_preference
        else:
            language_context = ", ".join(languages) if languages else "English"

        prompt = f"""
INPUT DETAILS:
Primary Keyword: {primary_keyword}
Title: {title}
Intent: {intent or 'Not specified'}
Secondary Keywords: {secondary_keywords_str or 'Not provided'}
Language Preference: {language_context}
Industry: {industry}
- Target Audience: {target_audience}
- Current Date: {current_date}

Goals:


Create a SEO-friendly meta description 
Write naturally and avoid keyword stuffing
Align with the title and search intent of the blog
Incorporate secondary keywords wherever applicable
Avoid cliches and keep it engaging for the users to read
Understand the Language Preference in the input as English (UK), or English (USA), and give the meta description content accordingly. 
Do not exceed more than 160 characters strictly for any meta description in your response.

Process:


Understand the primary keyword and its search intent: 
Understand the primary keyword and its intent to know about the kind of information the blog has covered. For example, if the blog is of Informational intent, then it will provide clarity, explanations, or background of the concepts. For e.g., if the blog is about “What is Digital Marketing”, then the blog sub-headings must be to explain the concepts related to it. Similarly, if it is of Navigational intent, then it must guide users to specific and targeted solutions. For eg., if the blog title is about ‘iPhone pricing’, then the user must receive the various pricing options as the user is already beyond the need for getting surface-level explanations. For Commercial intent, it must help users compare, evaluate, or make decisions. For e.g., for the blog topic "SEO vs. SEM: Which Strategy Suits Your Business?", blog sub-headings must list the advantages and disadvantages for both as the users are in the decision-making stage. For Transactional intent, the content must direct users toward action-oriented content. For e.g., "How to Optimize Your Website for SEO in 5 Steps", provides clear steps for achieving this in the sub-headings.
Understand the secondary keywords to build the context: Understand the secondary keywords to understand the context in which the information of the primary keyword has to be covered. For example, for the primary keyword ‘email marketing benefits’, the secondary keyword ‘automation in email marketing’, establishes the need for highlighting the benefits of email marketing and gives a special emphasis on ‘automation’, as one of the benefits of email marketing. This will help you ensure that you don’t give the meta description content out of context and readers are able to build a natural relation of section content with the overall content. 
Understand the title of the blog to understand what it is about:  You must factor the title of the blog to directly understand the user’s expectations from the meta description. The title of the blog clearly set the goal of what, why and how the content should be written. The meta description content should align with the title of the blog to give a natural understanding of the concept in the entire blog post to the reader.
 Keep the meta description content within 155-160 characters: You must keep the meta description length to maximum 155-160 characters only. 
Avoid using fillers, modifiers and unnecessary adjectives in your content: Fillers are words that add context or create a more natural flow, while modifiers enhance the description by adding detail or emphasis. However, the usage of fillers, modifiers and unnecessary adjectives must be avoided while writing meta description to prioritise important information within the character limits. 
Prioritise the usage of the active voice in sentence structuring: Prioritise the usage of the active voice in making the sentences of the section content. Verbs have two voices—active and passive. When the verb is active, the subject of the sentence acts. When the voice is passive, the subject is acted upon. In the active voice, the subject is also the actor (the agent of the action). Their usage makes the sentences more dynamic and engaging. For example, the sentence, "The company launched a new AI tool." (Active), is direct and communicates the idea clearly in shorter words. This is not the case with the sentence, "A new AI tool was launched by the company." (Passive).
Prioritise the usage of the action verbs over thinking verbs: The verb usage in the section content must prioritise ‘action verbs’ over ‘thinking verbs’. Action verbs are those that depict a visible action. Their usage brings more clarity and impact on the readers. Their usage is ideal for blogs as it resonates more with the readers as they are more persuasive and dynamic. Some examples of action verbs are - think, analyze, decide, imagine, remember, understand, predict, solve, plan etc. Thinking verbs on the other hand depict cognitive processes. They are used for analyzing, reasoning, understanding, and making decisions. These verbs often refer to mental actions rather than physical ones. However, their usage is ideal only for highly analytical posts and research, as they give a more formal and critical tone to writing. Hence, they are ideal for academic writing and not blog posts. Some examples of thinking verbs are - understand, recognize, comprehend, realize, interpret, identify, distinguish etc. 



Output: 
Give the output in the plain text format. 
Don’t acknowledge the completion of the task. 
Don’t mention word count in your response. 
Don’t include any other additional details in your response and only give the meta description content. 
Do not exceed more than 160 characters strictly in your response. This is critical for the success of the task. 
Give the response in json format like this {{
      "meta_description": "your meta description content here"
  }}

"""
        return prompt

    def _get_intent_guidance(self, intent: str) -> str:
        """Get specific guidance based on search intent."""
        intent_guidance = {
            "informational": "Focus on learning, discovering, and understanding. Use words like 'learn', 'discover', 'understand', 'guide', 'tips'.",
            "navigational": "Help users find specific information or navigate to particular content. Use clear, direct language.",
            "commercial": "Highlight comparisons, reviews, best options. Use words like 'best', 'top', 'compare', 'review', 'choose'.",
            "transactional": "Encourage action and conversion. Use strong CTAs like 'get', 'buy', 'download', 'start', 'try'."
        }
        return intent_guidance.get(intent.lower(), "Focus on providing clear value and encouraging clicks to learn more.")


    def generate_meta_description_workflow(
        self,
        primary_keyword: str,
        title: str,
        intent: Optional[str] = None,
        secondary_keywords: Optional[List[str]] = None,
        language_preference: Optional[str] = None,
        project_id: Optional[str] = None,
        project: Optional[object] = None
    ) -> Dict:
        """
        Complete workflow for generating meta descriptions.
        
        :param primary_keyword: Primary keyword for SEO optimization
        :param title: The blog/page title
        :param intent: Search intent (optional)
        :param secondary_keywords: Optional list of secondary keywords
        :param language_preference: Optional language preference
        :param project_id: Project ID for tracking
        :param project: Project object with additional context
        :return: Generated meta descriptions and metadata
        """
        try:
            self.logger.info(f"🚀 Starting meta description generation workflow")
            self.logger.info(f"Primary Keyword: {primary_keyword}")
            self.logger.info(f"Title: {title}")
            self.logger.info(f"Intent: {intent}")
            self.logger.info(f"Secondary Keywords: {secondary_keywords}")
            self.logger.info(f"Language Preference: {language_preference}")
            
            # Generate the prompt
            self.logger.info(f"📝 Generating meta description prompt...")
            prompt = self.generate_meta_description_prompt(
                primary_keyword=primary_keyword,
                title=title,
                intent=intent,
                secondary_keywords=secondary_keywords,
                language_preference=language_preference,
                project=project
            )
            self.logger.info(f"✅ Prompt generated successfully")
            
            # Call OpenAI API
            self.logger.info(f"🤖 Calling OpenAI API...")
            response = self.openai_client.responses.create(
                model="gpt-4o-mini-2024-07-18",
                input=[
                    {"role": "system", "content": "Role: You are an expert SEO content writer. Based on the following blog details, write a compelling and SEO-friendly meta description following the goals and process mentioned below."},
                    {"role": "user", "content": prompt}
                ],
                temperature=1.0,
                max_output_tokens=16384
            )
            self.logger.info(f"✅ OpenAI API call completed")
            
            # Parse response
            response_content = response.output_text.strip()
            self.logger.info(f"Raw OpenAI response: {response_content}")
            
            try:
                openai_response = json.loads(response_content)
                self.logger.info(f"✅ JSON parsing successful")
            except json.JSONDecodeError as json_error:
                self.logger.error(f"❌ JSON parsing failed: {json_error}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to parse OpenAI response as JSON: {str(json_error)}"
                )
            
            # Extract meta description
            meta_description = openai_response.get('meta_description', '')
            self.logger.info(f"📊 Generated meta description: {meta_description}")
            
            # Validate results
            if not meta_description:
                raise HTTPException(
                    status_code=500,
                    detail="No meta description was generated"
                )
            
            # Log usage to the enhanced LLM service
            try:
                self.logger.info(f"📊 Logging usage to EnhancedLLMUsageService...")
                
                # Debug: Log response object structure
                self.logger.info(f"🔍 Response object type: {type(response)}")
                self.logger.info(f"🔍 Response attributes: {dir(response)}")
                
                # Get model name safely
                model_name = getattr(response, 'model', 'gpt-4o-mini')
                self.logger.info(f"📊 Model name: {model_name}")
                
                # Get usage data safely
                usage_data = getattr(response, 'usage', None)
                if usage_data:
                    input_tokens = getattr(usage_data, 'input_tokens', 0)
                    output_tokens = getattr(usage_data, 'output_tokens', 0)
                    self.logger.info(f"📊 Usage data found - Input: {input_tokens}, Output: {output_tokens}")
                else:
                    # Fallback to estimated tokens
                    input_tokens = len(prompt) // 4
                    output_tokens = len(meta_description) // 4
                    self.logger.warning(f"⚠️ No usage data found, using estimates - Input: {input_tokens}, Output: {output_tokens}")
                
                usage_metadata = {
                    "meta_description": {
                        "primary_keyword": primary_keyword,
                        "title": title,
                        "intent": intent,
                        "secondary_keywords": secondary_keywords,
                        "language_preference": language_preference
                    }
                }
                
                # Record LLM usage with actual response data
                result = self.llm_usage_service.record_llm_usage(
                    user_id=self.user_id,
                    service_name="meta_description",
                    model_name=model_name,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    service_description="Meta description generation using OpenAI",
                    project_id=project_id,
                    additional_metadata=usage_metadata
                )
                self.logger.info(f"✅ Usage logged successfully: {result}")
                
            except Exception as usage_error:
                self.logger.error(f"⚠️ Failed to log usage (non-critical): {usage_error}")
                self.logger.error(f"⚠️ Usage error details: {str(usage_error)}", exc_info=True)
            
            # Return results
            result = {
                "meta_description": meta_description,
                "metadata": {
                    "primary_keyword": primary_keyword,
                    "title": title,
                    "intent": intent,
                    "secondary_keywords": secondary_keywords,
                    "language_preference": language_preference,
                    "generated_count": 1,
                    "generated_at": datetime.now().isoformat()
                }
            }
            
            self.logger.info(f"🎉 Meta description generation workflow completed successfully")
            return result
            
        except HTTPException:
            # Re-raise HTTP exceptions as-is
            raise
        except Exception as workflow_error:
            self.logger.error(f"❌ Meta description workflow failed: {workflow_error}")
            self.logger.error(f"❌ Error type: {type(workflow_error)}")
            raise HTTPException(
                status_code=500,
                detail=f"Meta description generation workflow error: {str(workflow_error)}"
            )