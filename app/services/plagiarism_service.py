from typing import Dict, List, Optional
from datetime import datetime
import os
import json
import requests

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging_config import logger
from fastapi import HTTPException
from app.services.enhanced_llm_usage_service import EnhancedLLMUsageService

class PlagiarismService:
    def __init__(self, 
                 db: Session,
                 user_id: str,
                 project_id: Optional[str] = None,
                 winston_api_key: Optional[str] = None):
        """
        Initialize PlagiarismService.
        
        :param db: Database session
        :param user_id: User ID for tracking
        :param project_id: Project ID for tracking
        :param winston_api_key: Winston AI API key. If not provided, uses settings.
        """
        self.db = db
        self.user_id = user_id
        self.project_id = project_id
        self.winston_api_key = winston_api_key or getattr(settings, 'WINSTON_API_KEY', 
                                                          os.getenv('WINSTON_API_KEY'))
        self.winston_base_url = "https://api.gowinston.ai/v2"
        self.logger = logger
        
        # Initialize enhanced LLM usage service for billing
        self.llm_usage_service = EnhancedLLMUsageService(db)
        
        if not self.winston_api_key:
            raise HTTPException(
                status_code=500,
                detail="Winston AI API key not configured"
            )

    def check_plagiarism_workflow(
        self,
        text: str,
        language: Optional[str] = "en",
        country: Optional[str] = "us",
        project_id: Optional[str] = None,
        project: Optional[object] = None
    ) -> Dict:
        """
        Complete workflow for plagiarism detection.
        
        :param text: Text content to check for plagiarism
        :param language: Language code (default: "en")
        :param country: Country code (default: "us")
        :param project_id: Project ID for tracking
        :param project: Project object with additional context
        :return: Plagiarism detection results and metadata
        """
        try:
            self.logger.info(f"🚀 Starting plagiarism detection workflow")
            self.logger.info(f"Text length: {len(text)} characters")
            self.logger.info(f"Language: {language}")
            self.logger.info(f"Country: {country}")
            
            # Validate input text
            if not text or not text.strip():
                raise HTTPException(
                    status_code=400,
                    detail="Text content is required for plagiarism detection"
                )
            
            if len(text.strip()) < 10:
                raise HTTPException(
                    status_code=400,
                    detail="Text must be at least 10 characters long for meaningful plagiarism detection"
                )
            
            # Prepare Winston AI API request
            self.logger.info(f"📝 Preparing Winston AI API request...")
            
            headers = {
                "Authorization": f"Bearer {self.winston_api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "language": language,
                "country": country,
                "text": text.strip()
            }
            
            self.logger.info(f"🔍 Payload prepared - Language: {language}, Country: {country}")
            
            # Call Winston AI API
            self.logger.info(f"🤖 Calling Winston AI API...")
            try:
                response = requests.post(
                    f"{self.winston_base_url}/plagiarism",
                    headers=headers,
                    json=payload,
                    timeout=60  # 60 second timeout
                )
                self.logger.info(f"✅ Winston AI API call completed with status: {response.status_code}")
            except requests.exceptions.Timeout:
                self.logger.error(f"❌ Winston AI API timeout")
                raise HTTPException(
                    status_code=504,
                    detail="Plagiarism detection service timeout. Please try again."
                )
            except requests.exceptions.RequestException as req_error:
                self.logger.error(f"❌ Winston AI API request failed: {req_error}")
                raise HTTPException(
                    status_code=502,
                    detail=f"Plagiarism detection service error: {str(req_error)}"
                )
            
            # Handle API response
            if response.status_code != 200:
                self.logger.error(f"❌ Winston AI API error: {response.status_code} - {response.text}")
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Winston AI API error: {response.text}"
                )
            
            # Parse response
            try:
                winston_response = response.json()
                self.logger.info(f"✅ JSON parsing successful")
            except json.JSONDecodeError as json_error:
                self.logger.error(f"❌ JSON parsing failed: {json_error}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to parse Winston AI response as JSON: {str(json_error)}"
                )
            
            self.logger.info(f"Raw Winston AI response keys: {list(winston_response.keys())}")
            
            # Extract key results
            status = winston_response.get('status')
            result = winston_response.get('result', {})
            sources = winston_response.get('sources', [])
            credits_used = winston_response.get('credits_used', 0)
            credits_remaining = winston_response.get('credits_remaining', 0)
            
            plagiarism_score = result.get('score', 0)
            source_counts = result.get('sourceCounts', 0)
            total_plagiarism_words = result.get('totalPlagiarismWords', 0)
            
            self.logger.info(f"📊 Plagiarism Results:")
            self.logger.info(f"  - Score: {plagiarism_score}%")
            self.logger.info(f"  - Sources found: {source_counts}")
            self.logger.info(f"  - Plagiarized words: {total_plagiarism_words}")
            self.logger.info(f"  - Credits used: {credits_used}")
            self.logger.info(f"  - Credits remaining: {credits_remaining}")
            
            # Validate results
            if status is None:
                raise HTTPException(
                    status_code=500,
                    detail="Invalid response from plagiarism detection service"
                )
            
            # Log usage to the enhanced LLM service
            try:
                self.logger.info(f"📊 Logging usage to EnhancedLLMUsageService...")
                
                # Winston AI uses credits directly - pass credits_used as input_tokens
                # The token calculator will handle the credit-based pricing using credits_per_1k
                winston_credits = credits_used  # Direct credits from Winston AI (e.g., 1000)
                
                self.logger.info(f"Winston AI Credits Used: {winston_credits}")
                
                usage_metadata = {
                    "plagiarism_detection": {
                        "text_length": len(text),
                        "language": language,
                        "country": country,
                        "plagiarism_score": plagiarism_score,
                        "sources_found": source_counts,
                        "winston_credits_used": winston_credits,
                        "service_provider": "winston-ai"
                    }
                }
                
                # Record service usage - pass credits as input_tokens for Winston AI billing
                result_record = self.llm_usage_service.record_llm_usage(
                    user_id=self.user_id,
                    service_name="plagiarism_checker",
                    model_name="winston-ai-plagiarism",
                    input_tokens=int(winston_credits),  # Credits used by Winston AI
                    output_tokens=0,  # Winston AI doesn't separate input/output
                    service_description="Plagiarism detection and content originality analysis using Winston AI",
                    project_id=project_id,
                    additional_metadata=usage_metadata
                )
                self.logger.info(f"✅ Usage logged successfully: {result_record}")
                
            except Exception as usage_error:
                self.logger.error(f"⚠️ Failed to log usage (non-critical): {usage_error}")
                self.logger.error(f"⚠️ Usage error details: {str(usage_error)}", exc_info=True)
            
            # Return structured results
            result_data = {
                "plagiarism_score": plagiarism_score,
                "sources_found": source_counts,
                "total_words": result.get('textWordCounts', 0),
                "plagiarized_words": total_plagiarism_words,
                "identical_words": result.get('identicalWordCounts', 0),
                "similar_words": result.get('similarWordCounts', 0),
                "sources": sources,
                "scan_information": winston_response.get('scanInformation', {}),
                "attack_detected": winston_response.get('attackDetected', {}),
                "similar_words_list": winston_response.get('similarWords', []),
                "citations": winston_response.get('citations', []),
                "indexes": winston_response.get('indexes', []),
                "credits_used": credits_used,
                "metadata": {
                    "text_length": len(text),
                    "language": language,
                    "country": country,
                    "checked_at": datetime.now().isoformat(),
                    "service_status": status
                }
            }
            
            self.logger.info(f"🎉 Plagiarism detection workflow completed successfully")
            return result_data
            
        except HTTPException:
            # Re-raise HTTP exceptions as-is
            raise
        except Exception as workflow_error:
            self.logger.error(f"❌ Plagiarism detection workflow failed: {workflow_error}")
            self.logger.error(f"❌ Error type: {type(workflow_error)}")
            raise HTTPException(
                status_code=500,
                detail=f"Plagiarism detection workflow error: {str(workflow_error)}"
            )