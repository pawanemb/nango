from typing import Dict, Any
from sqlalchemy.orm import Session
from app.services.openai_service import OpenAIService
from app.core.logging_config import logger
import json
import re
import logging
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.services.openai_service import OpenAI
from app.core.config import settings
from datetime import datetime
import os

logger = logging.getLogger(__name__)

class BrandToneAnalysisService:
    """Service for analyzing brand tone from text paragraphs"""
    
    def __init__(self, db: Session, user_id: str, project_id: str = None):
        self.db = db
        self.user_id = user_id
        self.project_id = project_id
        # Create direct OpenAI client for detailed logging
        self.openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
        # Keep the original service for fallback
        from app.services.openai_service import OpenAIService
        self.openai_service = OpenAIService(db=db, user_id=user_id, project_id=project_id)
        
        # Ensure logs directory exists
        os.makedirs("logs/api_payloads", exist_ok=True)

    def analyze_brand_tone(self, paragraph: str) -> Dict[str, Any]:
        """
        Analyze brand tone from a paragraph using OpenAI
        
        Args:
            paragraph (str): The text paragraph to analyze
            
        Returns:
            Dict containing the tone analysis results
        """
        try:
            logger.info(f"🎨 Starting brand tone analysis for paragraph of length: {len(paragraph)}")
            
            # Create the brand tone analysis prompt
            brand_tone_prompt = f"""
Input:
{paragraph}
Goals: 
List the brand tonality preferences for the mentioned website by listing one most suitable spectrum for each of these dimensions: 
Formality
Attitude
Energy
Clarity

Process
1. Refer to the paragraph mentioned in the input to list the most apt branding spectrums applicable :
a. Formality Spectrum
i) Ceremonial – Highly structured, protocol-driven (e.g., royal communication)
ii) Formal – Professional, precise, objective (e.g., financial reports)
iii) Neutral – Clear, concise, balanced (e.g., Wikipedia)
iv) Conversational – Friendly, semi-casual (e.g., Apple)
v) Colloquial – Relatable, uses idioms/slang (e.g., Innocent Drinks)

b. Attitude Spectrum
i) Reverent – Deeply respectful and deferential (e.g., military comms)
ii) Respectful – Polite and courteous (e.g., IBM)
iii) Direct – Honest, clear, unembellished (e.g., Basecamp)
iv) Witty – Smart, playful, clever (e.g., Oatly)
v) Bold – Unapologetic, confident (e.g., Liquid Death)
vi) Irreverent – Rebellious, sarcastic, edgy (e.g., Cards Against Humanity)

c. Energy Spectrum
i) Serene – Calm, composed (e.g., meditation apps)
ii) Grounded – Thoughtful, steady (e.g., Patagonia)
iii) Upbeat – Energetic and positive (e.g., Canva)
iv) Excitable – High-pitched enthusiasm (e.g., youth brands)
v) Hype-driven – Loud, urgent, all caps (e.g., Gymshark drops)

d. Clarity Spectrum
i) Technical – Jargon-heavy, expert-level (e.g., engineering docs)
ii) Precise – Detailed but easy to follow (e.g., The Verge)
iii) Clear – No jargon, plain language (e.g., Google)
iv) Simplified – Chunked, dumbed-down for speed (e.g., Buzzfeed)
v) Abstract – Conceptual, metaphor-driven (e.g., high-end fashion)
vi) Poetic – Evocative, aesthetic-focused (e.g., Aesop skincare)
 

Give the final verdict on the most applicable brand tonality preferences of the input paragraph across these spectrums. Include the one most apt dimension for all the spectrums.
Don't include your subjective understanding about the brand and branding to give the output. 

Output: 

Give the output in the json format.
Do not write ```json in your response. 
List only one response for each spectrum. 
Do not acknowledge your response. 
Do not give any comments in your response. 



"""
            
            # Generate unique identifier for this analysis
            analysis_id = f"brand_tone_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
            
            # Log request payload to file
            try:
                with open(f"logs/api_payloads/brand_tone_request_{analysis_id}.txt", "w", encoding="utf-8") as f:
                    f.write("=== BRAND TONE ANALYSIS - OPENAI REQUEST PAYLOAD ===\n")
                    f.write(f"Analysis ID: {analysis_id}\n")
                    f.write(f"User ID: {self.user_id}\n")
                    f.write(f"Project ID: {self.project_id}\n")
                    f.write(f"Timestamp: {datetime.now()}\n")
                    f.write(f"Input Paragraph Length: {len(paragraph)} characters\n")
                    f.write(f"Model: {settings.OPENAI_MODEL}\n")
                    f.write(f"Temperature: {settings.OPENAI_TEMPERATURE}\n")
                    f.write(f"Max Tokens: {settings.OPENAI_MAX_TOKENS}\n")
                    f.write("\n--- INPUT PARAGRAPH ---\n")
                    f.write(paragraph)
                    f.write("\n\n--- FULL PROMPT ---\n")
                    f.write(brand_tone_prompt)
                    f.write("\n\n--- REQUEST MESSAGES ---\n")
                    f.write(json.dumps([
                        {"role": "system", "content": "Role: You are a branding analyst who can analyse the branding attributes by reading a paragraph. "},
                        {"role": "user", "content": brand_tone_prompt}
                    ], indent=2))
            except Exception as e:
                logger.warning(f"Failed to save brand tone request payload: {str(e)}")
            
            # Log detailed request info to console
            logger.info(f"🔍 BRAND TONE ANALYSIS REQUEST:")
            logger.info(f"  📋 Analysis ID: {analysis_id}")
            logger.info(f"  👤 User ID: {self.user_id}")
            logger.info(f"  📁 Project ID: {self.project_id}")
            logger.info(f"  📝 Input Length: {len(paragraph)} characters")
            logger.info(f"  🤖 Model: {settings.OPENAI_MODEL}")
            logger.info(f"  🌡️ Temperature: {settings.OPENAI_TEMPERATURE}")
            logger.info(f"  🎯 Max Tokens: {settings.OPENAI_MAX_TOKENS}")
            logger.info(f"  📄 Input Preview: {paragraph[:100]}{'...' if len(paragraph) > 100 else ''}")
            
            # Call OpenAI API directly for detailed logging
            try:
                logger.info(f"🚀 Making OpenAI API call for brand tone analysis...")
                
                response = self.openai_client.responses.create(
                    model=settings.OPENAI_MODEL,
                     input=[
                        {"role": "system", "content": "You are a branding analyst who can analyse the branding attributes by reading a paragraph."},
                        {"role": "user", "content": brand_tone_prompt}
                    ],
                    temperature=settings.OPENAI_TEMPERATURE,
                    max_output_tokens=settings.OPENAI_MAX_TOKENS
                )
                
                # Extract response content
                response_content = response.output_text
                
                # Log response payload to file
                try:
                    with open(f"logs/api_payloads/brand_tone_response_{analysis_id}.txt", "w", encoding="utf-8") as f:
                        f.write("=== BRAND TONE ANALYSIS - OPENAI RESPONSE PAYLOAD ===\n")
                        f.write(f"Analysis ID: {analysis_id}\n")
                        f.write(f"Timestamp: {datetime.now()}\n")
                        f.write(f"Model: {response.model}\n")
                        f.write(f"Tokens Used: {response.usage.total_tokens}\n")
                        f.write(f"Input Tokens: {response.usage.input_tokens}\n")
                        f.write(f"Output Tokens: {response.usage.output_tokens}\n")
                        f.write(f"Response Length: {len(response_content)} characters\n")
                        f.write("\n--- RAW RESPONSE CONTENT ---\n")
                        f.write(response_content)
                        f.write("\n\n--- FULL RESPONSE OBJECT ---\n")
                        f.write(str(response))
                except Exception as e:
                    logger.warning(f"Failed to save brand tone response payload: {str(e)}")
                
                # Log detailed response info to console
                logger.info(f"✅ BRAND TONE ANALYSIS RESPONSE:")
                logger.info(f"  📋 Analysis ID: {analysis_id}")
                logger.info(f"  🤖 Model Used: {response.model}")
                logger.info(f"  🔢 Total Tokens: {response.usage.total_tokens}")
                logger.info(f"  📥 Input Tokens: {response.usage.input_tokens}")
                logger.info(f"  📤 Output Tokens: {response.usage.output_tokens}")
                logger.info(f"  📄 Response Length: {len(response_content)} characters")
                logger.info(f"  🎯 Raw Response Preview: {response_content[:100]}{'...' if len(response_content) > 100 else ''}")
                
                # Process the response
                try:
                    # Clean and parse the JSON response
                    json_text = response_content.strip()
                    
                    logger.info(f"🔍 Processing JSON response...")
                    
                    # Remove any markdown formatting if present
                    json_text = re.sub(r'^```json\s*', '', json_text, flags=re.IGNORECASE)
                    json_text = re.sub(r'\s*```$', '', json_text)
                    json_text = re.sub(r'^```\s*', '', json_text)
                    
                    # Find the JSON part - look for the first { and last }
                    start_idx = json_text.find('{')
                    end_idx = json_text.rfind('}')
                    
                    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                        json_text = json_text[start_idx:end_idx+1]
                    
                    logger.info(f"🧹 Cleaned JSON: {json_text[:200]}...")
                    
                    # Parse JSON
                    parsed_data = json.loads(json_text)
                    logger.info(f"✅ Successfully parsed JSON response")
                    
                    # Validate that we have all required fields
                    required_fields = ["formality", "attitude", "energy", "clarity"]
                    tone_analysis = {}
                    
                    for field in required_fields:
                        # Try different case variations
                        value = (parsed_data.get(field) or 
                                parsed_data.get(field.capitalize()) or 
                                parsed_data.get(field.upper()) or 
                                parsed_data.get(field.lower()))
                        
                        if value:
                            tone_analysis[field] = str(value).strip()
                        else:
                            logger.warning(f"Missing field {field} in response, using default")
                            tone_analysis[field] = self._get_default_tone_value(field)
                    
                    logger.info(f"✅ Successfully analyzed brand tone: {tone_analysis}")
                    
                    return {
                        "status": "success",
                        "tone_analysis": tone_analysis,
                        "message": "Brand tone analysis completed successfully"
                    }
                    
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON response: {str(e)}")
                    logger.error(f"Raw response: {response_content}")
                    
                    # Try to extract tone values manually using regex
                    fallback_analysis = self._extract_tone_manually(response_content)
                    
                    return {
                        "status": "success",
                        "tone_analysis": fallback_analysis,
                        "message": "Brand tone analysis completed with manual parsing"
                    }
                    
            except Exception as e:
                logger.error(f"OpenAI analysis failed: {str(e)}")
                
                # Return default tone analysis
                default_analysis = self._get_default_tone_analysis()
                
                return {
                    "status": "success",
                    "tone_analysis": default_analysis,
                    "message": "Brand tone analysis completed with default values"
                }
            
        except Exception as e:
            logger.error(f"❌ Error in brand tone analysis: {str(e)}")
            
            # Return default tone analysis on error
            default_analysis = self._get_default_tone_analysis()
            
            return {
                "status": "error",
                "tone_analysis": default_analysis,
                "message": f"Brand tone analysis failed: {str(e)}"
            }
    
    def _extract_tone_manually(self, text: str) -> Dict[str, str]:
        """Extract tone values manually using regex patterns"""
        
        tone_analysis = {}
        
        # Define patterns for each tone dimension
        patterns = {
            "formality": r"(?:formality|formal)[\s\w]*?:\s*([a-zA-Z]+)",
            "attitude": r"(?:attitude)[\s\w]*?:\s*([a-zA-Z]+)",
            "energy": r"(?:energy)[\s\w]*?:\s*([a-zA-Z]+)",
            "clarity": r"(?:clarity)[\s\w]*?:\s*([a-zA-Z]+)"
        }
        
        for field, pattern in patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                tone_analysis[field] = match.group(1).strip().capitalize()
            else:
                tone_analysis[field] = self._get_default_tone_value(field)
        
        return tone_analysis
    
    def _get_default_tone_value(self, field: str) -> str:
        """Get default tone value for a field"""
        defaults = {
            "formality": "Neutral",
            "attitude": "Direct", 
            "energy": "Grounded",
            "clarity": "Clear"
        }
        return defaults.get(field, "Neutral")
    
    def _get_default_tone_analysis(self) -> Dict[str, str]:
        """Get complete default tone analysis"""
        return {
            "formality": "Neutral",
            "attitude": "Direct",
            "energy": "Grounded", 
            "clarity": "Clear" 
        }

    def store_brand_tone_settings(self, project_id: str, brand_tone_settings: Dict[str, str], person_tone: str = None) -> Dict[str, Any]:
        """
        Store brand tone settings for a project in the database
        
        Args:
            project_id (str): The project ID
            brand_tone_settings (Dict[str, str]): The 4-axis tone settings (formality, attitude, energy, clarity)
            person_tone (str): The person tone setting (First Person, Second Person, Third Person)
            
        Returns:
            Dict containing the store operation result
        """
        try:
            logger.info(f"🎨 Storing brand tone settings for project {project_id}")
            
            # Find the project
            from app.models.project import Project
            project = self.db.query(Project).filter(Project.id == project_id).first()
            
            if not project:
                logger.error(f"Project {project_id} not found")
                return {
                    "status": "error",
                    "message": f"Project {project_id} not found"
                }
            
            # Validate brand tone settings structure (4-axis only)
            required_fields = ["formality", "attitude", "energy", "clarity"]
            for field in required_fields:
                if field not in brand_tone_settings:
                    logger.error(f"Missing required field: {field}")
                    return {
                        "status": "error",
                        "message": f"Missing required field: {field}"
                    }
            
            # Log current project state before update
            logger.info(f"📊 BEFORE UPDATE - Project {project_id}:")
            logger.info(f"  🎨 Current brand_tone_settings: {project.brand_tone_settings}")
            logger.info(f"  👤 Current person_tone: '{project.person_tone}' (type: {type(project.person_tone)})")
            
            # Store the 4-axis brand tone settings in JSONB column
            project.brand_tone_settings = brand_tone_settings
            logger.info(f"✅ Updated brand_tone_settings to: {brand_tone_settings}")
            
            # Store person_tone in separate VARCHAR column
            logger.info(f"📝 Processing person_tone: '{person_tone}' (type: {type(person_tone)})")
            if person_tone is not None:  # Changed from 'if person_tone:' to handle empty strings
                project.person_tone = person_tone
                logger.info(f"✅ Updated person_tone to: '{person_tone}' in VARCHAR column")
            else:
                logger.info(f"⚠️ person_tone is None, keeping current value: '{project.person_tone}'")

            # Log project state after update but before commit
            logger.info(f"📊 AFTER UPDATE (before commit) - Project {project_id}:")
            logger.info(f"  🎨 Project.brand_tone_settings: {project.brand_tone_settings}")
            logger.info(f"  👤 Project.person_tone: '{project.person_tone}' (type: {type(project.person_tone)})")

            self.db.commit()
            logger.info(f"💾 Database commit completed for project {project_id}")
            
            # Verify data was actually saved by refreshing from database
            self.db.refresh(project)
            logger.info(f"🔍 POST-COMMIT VERIFICATION - Project {project_id}:")
            logger.info(f"  🎨 Saved brand_tone_settings: {project.brand_tone_settings}")
            logger.info(f"  👤 Saved person_tone: '{project.person_tone}' (type: {type(project.person_tone)})")
            
            logger.info(f"✅ Successfully stored brand tone settings for project {project_id}")
            
            # Combine for response (API compatibility)
            combined_settings = {
                **brand_tone_settings
            }
            if person_tone:
                combined_settings["person_tone"] = person_tone
            
            return {
                "status": "success",
                "message": "Brand tone settings stored successfully",
                "project_id": project_id,
                "brand_tone_settings": combined_settings
            }
            
        except Exception as e:
            logger.error(f"❌ Error storing brand tone settings: {str(e)}")
            self.db.rollback()
            
            return {
                "status": "error",
                "message": f"Failed to store brand tone settings: {str(e)}"
            }
    
    def fetch_brand_tone_settings(self, project_id: str) -> Dict[str, Any]:
        """
        Fetch brand tone settings for a project from the database
        
        Args:
            project_id (str): The project ID
            
        Returns:
            Dict containing the fetched tone settings
        """
        try:
            logger.info(f"🎨 Fetching brand tone settings for project {project_id}")
            
            # Find the project
            from app.models.project import Project
            project = self.db.query(Project).filter(Project.id == project_id).first()
            
            if not project:
                logger.error(f"Project {project_id} not found")
                return {
                    "status": "error",
                    "message": f"Project {project_id} not found"
                }
            
            # Get the 4-axis brand tone settings from JSONB column
            brand_tone_settings = project.brand_tone_settings
            
            # Get person_tone from VARCHAR column
            person_tone = getattr(project, 'person_tone', None)
            
            # Combine both for API response
            if brand_tone_settings:
                tone_settings = dict(brand_tone_settings)  # Copy JSONB data
                if person_tone:
                    tone_settings["person_tone"] = person_tone
            else:
                tone_settings = None

            if tone_settings is None:
                logger.info(f"No brand tone settings found for project {project_id}")
                return {
                    "status": "success",
                    "message": "No brand tone settings found for this project",
                    "project_id": project_id,
                    "brand_tone_settings": None
                }

            logger.info(f"✅ Successfully fetched brand tone settings for project {project_id}")

            return {
                "status": "success",
                "message": "Brand tone settings retrieved successfully",
                "project_id": project_id,
                "brand_tone_settings": tone_settings
            }
            
        except Exception as e:
            logger.error(f"❌ Error fetching brand tone settings: {str(e)}")
            
            return {
                "status": "error",
                "message": f"Failed to fetch brand tone settings: {str(e)}"
            }
