from typing import Dict, Any, List, Optional
from openai import OpenAI
from app.core.config import settings
import logging
from urllib.parse import urlparse
from sqlalchemy.orm import Session
from app.utils.token_tracking import TokenTracker
from app.core.prompt_config import PromptType


logger = logging.getLogger(__name__)


class OpenAIService:
    def __init__(self, db: Session, user_id: str, project_id: Optional[str] = None):
        self.db = db
        self.user_id = user_id
        self.project_id = project_id
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)

    def analyze_demographics(
        self,
        html_content: str,
        services: List[str],
        business_type: str = None
    ) -> Dict[str, Any]:
        """
        Analyze website content to determine target demographics.
        
        Args:
            html_content: The website HTML content
            services: List of services offered
            business_type: Type of business
            
        Returns:
            Dict containing demographic analysis
        """
        try:
            system_prompt = "Based on the content and structure of the following scrapped homepage, the services the organization offers, and the type of business, build a customer profile for the organization. Choose the most appropriate option from the provided lists under each attribute: Age, Gender, Language(s) Spoken, and Country. The profile should reflect the primary target audience of the organization."
            
            # Use string concatenation to avoid f-string issues with curly braces in html_content
            user_prompt = """
Inputs:
Input of scrapped homepage: """ + html_content + """
Input of the services offered by the organisation: """ + ', '.join(services) + """

Goals:
Process and Understand the Scrapped Homepage: You must thoroughly understand the scrapped homepage of the website to understand the target audience attributes: Age, Gender, Language(s) Spoken, and Country.
Reflect the primary target audience of the organization: Based on the scrapped homepage of the website, you must accurately suggest its target audience to build their customer profile.
Process
Step 1, Process the scrapped homepage: Process the scrapped homepage thoroughly to accurately suggest its target audience for building the customer profile.
Step 2, Suggest Age Group: Suggest the target age group of the website by selecting from the following:
Step 3, Age: [Select from Toddlers (1-3 years old), Preschoolers (4-5 years old), School-Age Children (6-12 years old), Teenagers (13-17 years old), Young Adults (18-24 years old), Adults (25-49 years old), Mature Adults (50-69 years old), Seniors (70+ years old)]
Step 4, Suggest the Gender Profile: Suggest the target age group of the website by selecting from the following:
Gender: [Select from Male, Female, Non-binary, and All]
Step 5, Suggest Language Preference: Suggest the language preference of the audience by suggesting only one from the following: English (UK), English (USA).
To get an idea about this, you can take the reference from the scrapped homepage of the website in the input. 
Step 6, Give the response of Language Preference in the format: Language(s) Spoken: Select only one from English (UK), English (USA).
Step 7, Suggest Target Location(s): Suggest the location of the website's target audience by selecting country/countries from the following:
Country: [Select from United States, United Kingdom, India, Canada, Australia, Germany, France, Japan, China, Brazil, Russia, South Africa, Singapore, United Arab Emirates, Mexico, Spain, Italy, Netherlands, Sweden, Israel, Worldwide]
If the website is clearly recognizable as a global enterprise (e.g., Apple, Microsoft, Amazon, Google, etc.) with offerings across multiple regions and continents, or includes global shopping/support/language options, set "Country" to ["Worldwide"].
For all other businesses, even if they operate in more than one country, list the specific countries they target or operate in, based on the homepage content or regional links.
Step 8, Do not give the output of any other location if the response is Worldwide: Do not suggest any other country for the instances in which the response is ‘Worldwide’. This is critical for the success of the task.
Output
1. Do not add any remarks of your own.
2. Do not apologize or emote.
3. Give output as just values separated by commas.
4. Choose multiple options under every single attribute, if applicable.
5. Give output in JSON table format.
6. Use the following keys for the output formatting: Age, Gender, Language(s) Spoken, Country.
7. Each key value should be an array.
8. Do not write ```json in your response.
"""

            with TokenTracker(
                db=self.db,
                user_id=self.user_id,
                prompt_type=PromptType.AUDIENCE_DETECTION,
                prompt_name="Analyze Demographics",
                project_id=self.project_id,
                extra_metadata={
                    "services_count": len(services),
                    "business_type": business_type
                }
            ) as tracker:
                response = self.client.responses.create(
                    model=settings.OPENAI_MODEL,
                     input=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=1,
                    max_output_tokens=settings.OPENAI_MAX_TOKENS
                )
                tracker.set_response(response)

            return {
                "status": "success",
                "analysis": response.output_text,
                "model": settings.OPENAI_MODEL,
                "tokens_used": response.usage.total_tokens
            }

        except Exception as e:
            logger.error("Error in demographic analysis: " + str(e))
            return {
                "status": "error",
                "error": str(e),
                "error_type": type(e).__name__
            }

    def analyze_services(self, url: str, html_content: str) -> Dict[str, Any]:
        """
        Analyze website content to identify services and business category.
        
        Args:
            url: The website URL
            html_content: The cleaned HTML content of the website
            
        Returns:
            Dict containing services and business category
        """
        try:
            # Get clean domain for context
            clean_url = urlparse(url).netloc
            
            system_prompt = """Role: You are a seasoned business analyst. The main skill which you have to use is Reasoning."""

            # Use string concatenation to avoid f-string issues with curly braces in html_content
            user_prompt = """
Input:
Scrapped homepage of a website: """ + html_content + """

Goal:
Create an exhaustive list of services and or products: Your primary job is to give an exhaustive list of services and or products provided by a business.

Process
Step 1, Understand business: You have to understand what the business does by reading the scrapped homepage of its website which will be provided to you as input.
Step 2, Identify Useful and Useless information: There is a lot of clutter on a website homepage. In order to be able to effectively determine the right services and or products, you must be able to ignore all irrelevant information. Examples of irrelevant information, contact information, blog links, privacy policy links, discounts and sales, error messages, USPs etc. Whereas examples of relevant information, list of services, service categories listing,
Step 3, Identify Products and or Services: Basis the understanding of the business and decluttered information, you have to create a list of products and or services. One critical factor for job success is that you have to not include features in the list of products and or services. Features are not a product or service in themselves. They are just a part of a larger product or service.
Step 4, Understand the nature of service and or product: Some services and or products are monetised by a business whereas others are provided to ensure a good customer experience. The latter set of products and or services are not directly sold by the business. The set of products and or services which are not directly sold by the business must be ignored and not shown in the final output.
Step 5, Ignore SEO-oriented tools: Sometimes businesses create free tools for the sole purpose of ranking on google. These tools vaguely relate to the business domain and are generally offered free of charge. These tools are not a part of the main business lines and hence must be ignored in the output.
Step 6, Ignore free courses: If the business does not fall in the education domain, ignore any free courses or videos which it may provide as they are not monetised.
Step 7, Categorisation: You must categorise the products and or services by business lines so that they are easier to read and understand.

Output
Give output in json format.
Do not add any of your own comments or suggestions. Just give the categoried list of products and or services and the industry of business.
Only give unique services and or products in output. Do not repeat in the exact same or similar form.
Give the response mandatorily and do not leave it empty.
Do not give any descriptions of products and or services.
Give the output in the array format.
While listing, do not break down a category further into a sub-category.
Give the output in this format:

{
 "products_services": ["service1", "service2", "service3"],
 "business_category": "E-Commerce|SaaS|Others"
}"""

            with TokenTracker(
                db=self.db,
                user_id=self.user_id,
                prompt_type=PromptType.SERVICE_DETECTION,
                prompt_name="Analyze Services",
                project_id=self.project_id,
                extra_metadata={
                    "url": clean_url
                }
            ) as tracker:
                response = self.client.responses.create(
                    model=settings.OPENAI_MODEL,
                     input=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=1,
                    max_output_tokens=settings.OPENAI_MAX_TOKENS
                )
                tracker.set_response(response)

            return {
                "status": "success",
                "analysis": response.output_text,
                "model": settings.OPENAI_MODEL,
                "tokens_used": response.usage.total_tokens
            }

        except Exception as e:
            logger.error("Error in service analysis: " + str(e))
            return {
                "status": "error",
                "error": str(e),
                "error_type": type(e).__name__
            }

    def analyze_with_custom_prompt(self, custom_prompt: str) -> Dict[str, Any]:
        """
        Analyze content using a custom prompt with OpenAI API.
        Returns a dictionary containing analysis results.
        """
        try:
            with TokenTracker(
                db=self.db,
                user_id=self.user_id,
                prompt_type=PromptType.SERVICE_DETECTION,
                prompt_name="Custom Prompt Analysis",
                project_id=self.project_id
            ) as tracker:
                response = self.client.responses.create(
                    model=settings.OPENAI_MODEL,
                     input=[
                        {"role": "user", "content": custom_prompt}
                    ],
                    temperature=settings.OPENAI_TEMPERATURE,
                    max_output_tokens=settings.OPENAI_MAX_TOKENS
                )
                tracker.set_response(response)

            return {
                "status": "success",
                "analysis": response.output_text,
                "model": settings.OPENAI_MODEL,
                "tokens_used": response.usage.total_tokens
            }

        except Exception as e:
            logger.error("Error in OpenAI custom prompt analysis: " + str(e))
            return {
                "status": "error",
                "error": str(e),
                "error_type": type(e).__name__
            }

    def analyze_content(self, content: str) -> Dict[str, Any]:
        """
        Analyze content using OpenAI API to extract key information.
        Returns a dictionary containing analysis results.
        """
        try:
            system_prompt = """
            Analyze the provided content and extract the following information:
            1. Main topics discussed
            2. Key insights or findings
            3. Important entities (companies, people, products)
            4. Overall sentiment
            5. Key action items or recommendations
            Format the response as a JSON object.
            """

            with TokenTracker(
                db=self.db,
                user_id=self.user_id,
                prompt_type=PromptType.SERVICE_DETECTION,
                prompt_name="Analyze Content",
                project_id=self.project_id
            ) as tracker:
                response = self.client.responses.create(
                    model=settings.OPENAI_MODEL,
                     input=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": content}
                    ],
                    temperature=settings.OPENAI_TEMPERATURE,
                    max_output_tokens=settings.OPENAI_MAX_TOKENS
                )
                tracker.set_response(response)

            return {
                "status": "success",
                "analysis": response.output_text,
                "model": settings.OPENAI_MODEL,
                "tokens_used": response.usage.total_tokens
            }

        except Exception as e:
            logger.error("Error in OpenAI analysis: " + str(e))
            return {
                "status": "error",
                "error": str(e),
                "error_type": type(e).__name__
            }

    def generate_summary(self, content: str) -> Dict[str, Any]:
        """
        Generate a concise summary of the content using OpenAI.
        """
        try:
            system_prompt = """
            Generate a concise summary of the provided content. The summary should:
            1. Be no more than 3 paragraphs
            2. Highlight the most important points
            3. Maintain the key message and context
            4. Be written in a professional tone
            """

            with TokenTracker(
                db=self.db,
                user_id=self.user_id,
                prompt_type=PromptType.META_DESCRIPTION,
                prompt_name="Generate Summary",
                project_id=self.project_id
            ) as tracker:
                response = self.client.responses.create(
                    model=settings.OPENAI_MODEL,
                     input=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": content}
                    ],
                    temperature=settings.OPENAI_TEMPERATURE,
                    max_output_tokens=settings.OPENAI_MAX_TOKENS
                )
                tracker.set_response(response)

            return {
                "status": "success",
                "summary": response.output_text,
                "model": settings.OPENAI_MODEL,
                "tokens_used": response.usage.total_tokens
            }

        except Exception as e:
            logger.error("Error in summary generation: " + str(e))
            return {
                "status": "error",
                "error": str(e),
                "error_type": type(e).__name__
            }

    def extract_keywords(self, content: str) -> Dict[str, Any]:
        """
        Extract important keywords and phrases from the content.
        """
        try:
            system_prompt = """
            Extract important keywords and phrases from the content. Focus on:
            1. Technical terms
            2. Product names
            3. Company names
            4. Industry-specific terminology
            Format the response as a comma-separated list.
            """

            with TokenTracker(
                db=self.db,
                user_id=self.user_id,
                prompt_type=PromptType.PRIMARY_KEYWORDS,
                prompt_name="Extract Keywords",
                project_id=self.project_id
            ) as tracker:
                response = self.client.responses.create(
                    model=settings.OPENAI_MODEL,
                     input=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": content}
                    ],
                    temperature=settings.OPENAI_TEMPERATURE,
                    max_output_tokens=settings.OPENAI_MAX_TOKENS
                )
                tracker.set_response(response)

            return {
                "status": "success",
                "keywords": response.output_text,
                "model": settings.OPENAI_MODEL,
                "tokens_used": response.usage.total_tokens
            }

        except Exception as e:
            logger.error("Error in keyword extraction: " + str(e))
            return {
                "status": "error",
                "error": str(e),
                "error_type": type(e).__name__
            }

    def get_brand_tone_lines(self, html_content: str) -> Dict[str, Any]:
        """
        Simple OpenAI call to get brand tone analysis lines (minimum 10 words each).
        
        Args:
            html_content: The website HTML content to analyze
            
        Returns:
            Dict containing status and brand tone analysis lines
        """
        try:
            from app.prompts.brand_tone_prompts import get_brand_tone_prompts
            
            system_prompt, user_prompt = get_brand_tone_prompts(html_content)
            
            response = self.client.responses.create(
                model="gpt-4.1-mini",
                input=[
                    {
                        "role": "system",
                        "content": [
                            {
                                "type": "input_text",
                                "text": system_prompt
                            }
                        ]
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_text", 
                                "text": user_prompt
                            }
                        ]
                    }
                ],
                text={
    "format": {
      "type": "text"
    }
  },
  reasoning={},
  tools=[],
  temperature=1,
  max_output_tokens=32768,
  top_p=1,
  store=True
            )
            
            return {
                "status": "success",
                "brand_tone_lines": response.output_text
            }
            
        except Exception as e:
            logger.error(f"Brand tone analysis error: {str(e)}")
            return {
                "status": "error",
                "error": str(e)
            }



