from typing import Any, Dict, List, Optional, Union
from celery import chain
from app.celery_config import celery_app as celery
from app.core.config import settings
from app.core.logging_config import logger
from datetime import datetime
import asyncio
import logging
import openai
from openai import OpenAI
import requests

# Initialize OpenAI client
# client = OpenAI(api_key=settings.OPENAI_API_KEY)

def generate_prompt(
    services: List[str],
    business_type: str,
    locations: List[str],
    target_audience: str,
    homepage_content: str,
    industry: Optional[str] = None
) -> str:
    # Format the inputs
    services_str = ", ".join(services) if services else "[Add input here]"
    locations_str = ", ".join(locations) if locations else "[Add input here]"
    
    prompt = f"""Generate a list of SEO-relevant keywords from the following inputs:

Type of business: {business_type or "[Add input here]"}
List of services/products: {services_str}
Locations: {locations_str}
Target Audience: {target_audience or "[Add input here]"}
Scrapped Homepage: {homepage_content or "[Add input here]"}

Instructions:
1. For E-Commerce and SaaS businesses: - Split the intent of keywords into a 4:1 ratio, favoring commercial intent over informational intent. - Ensure 30% of the commercial intent keywords are location-based.
2. For all other types of businesses: - Split the intent of keywords into a 1:4 ratio, favoring informational intent over commercial intent. - Ensure 30% of the commercial intent keywords are location-based.
3. The SEO relevancy of all keywords should be very high.
4. Output the keywords as text separated by commas, WITHOUT any quotes.
5. No grouping should be done. Output only in one line.
6. No comments to be mentioned.
7. Do not change the split of commercial and informational intent keywords at all.
8. Do not include the name of the brand in your response.
9. The name of the brand is the name of the company which is hosting these services.
10. Act as a Googlebot crawler to give the list of high search volume and low difficulty keywords to rank the company with SEO efforts.
11. Output not less than 10 and not more than 20 keywords.
12. You are a highly experienced SEO expert who can access Ahrefs and Semrush. Make sure all keywords have high search volume and low difficulty.
13. DO NOT use any quotes or special characters in the keywords."""

    return prompt

@celery.task(name="keyword_suggestions.generate_keywords", queue="keyword_suggestions")
def generate_keywords(
    services: List[str],
    business_type: str,
    locations: List[str],
    target_audience: str,
    homepage_content: str,
    industry: str,
    country: str
) -> List[str]:
    """Generate keyword suggestions using GPT model"""
    try:
        # Initialize OpenAI client
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        
        # Ensure all inputs are strings or lists of strings
        services_str = ", ".join(map(str, services))
        locations_str = ", ".join(map(str, locations))
        
        # Create the prompt
        prompt = f"""Generate SEO keyword suggestions for a {business_type} that provides {services_str}.
        Target Locations: {locations_str}
        Target Audience: {target_audience}
        Industry: {industry or "General"}
        
        Generate keywords that:
        1. Are relevant to the business services and locations
        2. Target the specific audience
        3. Include both short-tail and long-tail keywords
        4. DO NOT include any quotes or special characters
        5. Are in plain text format
        
        Format each keyword on a new line without any quotes or special formatting.
        """
        
        # Get response from GPT using new API format
        response = client.responses.create(
            model=settings.OPENAI_MODEL,
             input=[
                {"role": "system", "content": "You are a skilled SEO expert helping to generate relevant keywords."},
                {"role": "user", "content": prompt}
            ],
            temperature=settings.OPENAI_TEMPERATURE,
            max_output_tokens=settings.OPENAI_MAX_TOKENS
        )
        
        # Extract and clean keywords (updated for new API response format)
        keywords_text = response.output_text.strip()
        keywords = [
            keyword.strip().strip('"\'').strip('.,;:').strip()
            for keyword in keywords_text.split('\n')
            if keyword.strip()
        ]
        
        # Remove any duplicates while preserving order
        seen = set()
        unique_keywords = [
            k for k in keywords
            if not (k.lower() in seen or seen.add(k.lower()))
        ]
        
        return unique_keywords
        
    except Exception as e:
        logger.error(f"Error generating keywords: {e}")
        raise

@celery.task(name="keyword_suggestions.fetch_metrics_task", queue="keyword_suggestions")
def fetch_metrics_task(keywords: List[str], country: str = "in") -> List[Dict[str, Any]]:
    """Celery task wrapper for fetch_metrics"""
    try:
        # Ensure all inputs are basic Python types
        clean_keywords = list(map(str, keywords))
        metrics = asyncio.run(fetch_metrics(clean_keywords, str(country)))
        
        # Convert all values to basic Python types
        serializable_metrics = []
        for metric in metrics:
            serializable_metrics.append({
                "keyword": str(metric["keyword"]),
                "search_volume": int(metric.get("search_volume", 0)),
                "difficulty": int(metric.get("difficulty", 0)),
                "intent": str(metric.get("intent", "Unknown")),
                "cpc": float(metric.get("cpc", 0.0)),
                "competition": float(metric.get("competition", 0.0))
            })
        
        return serializable_metrics
        
    except Exception as e:
        logger.error(f"Error fetching metrics in task: {e}")
        raise

@celery.task(name="keyword_suggestions.process_results", queue="keyword_suggestions")
def process_results(metrics: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Process and sort the results"""
    try:
        # Clean keywords in metrics
        cleaned_metrics = []
        for metric in metrics:
            # Clean keyword thoroughly
            clean_keyword = metric["keyword"].strip().strip('"\'').strip()
            clean_keyword = clean_keyword.strip('.,;:').strip()
            clean_keyword = clean_keyword.replace('"', '').replace("'", '')
            clean_keyword = clean_keyword.rstrip('.')
            
            cleaned_metrics.append({
                "keyword": clean_keyword,
                "search_volume": int(metric.get("search_volume", 0)),
                "difficulty": int(metric.get("difficulty", 0)),
                "intent": metric.get("intent", "Unknown"),
                "cpc": float(metric.get("cpc", 0.0)),
                "competition": float(metric.get("competition", 0.0))
            })
        
        # Sort by search volume descending
        cleaned_metrics.sort(key=lambda x: (-x["search_volume"], x["keyword"]))
        
        return {
            "keywords": cleaned_metrics,
            "generated_at": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error processing results: {e}")
        raise

def create_keyword_suggestions_chain(
    services: List[str],
    business_type: str,
    locations: List[str],
    target_audience: str,
    homepage_content: str,
    industry: str = "General",  # Set default value for industry
    country: str = "in"
) -> chain:
    """Create a chain of tasks for generating and processing keyword suggestions"""
    
    # Convert all inputs to basic Python types to ensure they're serializable
    services_list = list(map(str, services))
    locations_list = list(map(str, locations))
    
    # Create the task chain
    keyword_chain = chain(
        # First task: Generate keywords
        generate_keywords.s(
            services=services_list,
            business_type=str(business_type),
            locations=locations_list,
            target_audience=str(target_audience),
            homepage_content=str(homepage_content),
            industry=str(industry),
            country=str(country)
        ),
        # Second task: Fetch metrics for the generated keywords
        fetch_metrics_task.s(country=str(country)),
        # Third task: Process and sort results
        process_results.s()
    )
    
    return keyword_chain

def fetch_metrics(keywords: List[str], country: str = "in") -> List[Dict[str, Any]]:
    """Fetch metrics for keywords from SEMrush"""
    try:
        results = []
        
        # Clean all keywords first
        clean_keywords = []
        for keyword in keywords:
            clean_k = keyword.strip().strip('"\'').strip()
            clean_k = clean_k.strip('.,;:').strip()
            clean_k = clean_k.replace('"', '').replace("'", '')
            clean_k = clean_k.rstrip('.')
            clean_k = clean_k.lower()
            clean_keywords.append(clean_k)
            
        # Process keywords in batches of 100
        batch_size = 100
        for i in range(0, len(clean_keywords), batch_size):
            batch = clean_keywords[i:i + batch_size]
            
            # Map country codes to SEMrush database codes
            country_map = {
                "us": "us",
                "uk": "uk",
                "in": "in",
                "ae": "ae",  # UAE
                "au": "au",
                "ca": "ca",
                "de": "de",
                "fr": "fr",
                "es": "es",
                "it": "it"
            }
            
            # Get database code or default to us
            # db_code = country_map.get(country.lower(), "us")
            
            try:
                # Join keywords with semicolons for batch request
                keywords_str = ";".join(batch)
                
                params = {
                    "type": "phrase_these",
                    "key": settings.SEMRUSH_API_KEY,
                    "phrase": keywords_str,
                    "database": country.lower(),
                    "export_columns": "Ph,Nq,Cp,Co,Kd,In",  # Phrase, Volume, CPC, Competition, Difficulty, Intent
                }
                
                logger.info(f"Fetching SEMrush data for {len(batch)} keywords in batch")
                
                response = requests.get(
                    "https://api.semrush.com/",
                    params=params,
                    timeout=30.0
                )
                
                # Check for API errors in response text
                if response.text.startswith("ERROR"):
                    logger.warning(f"SEMrush API error for batch: {response.text}")
                    # Add default metrics for all keywords in failed batch
                    for keyword in batch:
                        results.append({
                            "keyword": keyword,
                            "search_volume": 0,
                            "difficulty": 0,
                            "intent": "Unknown",
                            "cpc": 0.0,
                            "competition": 0.0
                        })
                    continue
                
                # Parse the response
                lines = response.text.strip().split('\n')
                if len(lines) < 2:
                    logger.warning("No data found in batch response")
                    # Add default metrics for all keywords in batch
                    for keyword in batch:
                        results.append({
                            "keyword": keyword,
                            "search_volume": 0,
                            "difficulty": 0,
                            "intent": "Unknown",
                            "cpc": 0.0,
                            "competition": 0.0
                        })
                    continue
                
                # Process each line (skip header)
                keyword_metrics = {}  # Store metrics by keyword
                for line in lines[1:]:  # Skip header row
                    try:
                        data = line.split(';')
                        if len(data) >= 6:  # Ensure we have all columns
                            keyword = data[0].lower().strip()
                            keyword_metrics[keyword] = {
                                "keyword": keyword,
                                "search_volume": int(data[1]) if data[1] and data[1].strip().isdigit() else 0,
                                "cpc": float(data[2].replace(',', '.')) if data[2] and data[2].strip() else 0.0,
                                "competition": float(data[3].replace(',', '.')) if data[3] and data[3].strip() else 0.0,
                                "difficulty": int(data[4]) if data[4] and data[4].strip().isdigit() else 0,
                                "intent": data[5].strip() if len(data) > 5 and data[5].strip() else "Unknown"
                            }
                    except (IndexError, ValueError) as e:
                        logger.error(f"Error parsing line: {line}, error: {e}")
                        continue
                
                # Add results in original keyword order, using default metrics for missing keywords
                for keyword in batch:
                    results.append(keyword_metrics.get(keyword, {
                        "keyword": keyword,
                        "search_volume": 0,
                        "difficulty": 0,
                        "intent": "Unknown",
                        "cpc": 0.0,
                        "competition": 0.0
                    }))
                
            except Exception as e:
                logger.error(f"Error processing batch: {e}")
                # Add default metrics for all keywords in failed batch
                for keyword in batch:
                    results.append({
                        "keyword": keyword,
                        "search_volume": 0,
                        "difficulty": 0,
                        "intent": "Unknown",
                        "cpc": 0.0,
                        "competition": 0.0
                    })
                
        return results
        
    except Exception as e:
        logger.error(f"Error in fetch_metrics: {e}")
        raise

def fetch_semrush_data(keywords: Union[str, List[str]], country: str = "us", match_type: str = "phrase_this"):
    """
    Fetch keyword metrics from SEMrush API for one or multiple keywords
    
    Args:
        keywords: A single keyword or list of keywords to fetch metrics for
        country: Country database to search in (default: 'us')
        match_type: Type of keyword match (default: 'phrase_this')
    
    Returns:
        List of keyword metrics or None if API call fails
    """
    # Intent mapping for SEMrush numeric values
    INTENT_MAPPING = {
        "0": "commercial",
        "1": "informational",
        "2": "navigational",
        "3": "transactional",
        "": "unknown"
    }

    try:
        if not settings.SEMRUSH_API_KEY:
            logger.error("SEMRUSH_API_KEY is not configured")
            return None
        
        # Convert single keyword to list if needed
        if isinstance(keywords, str):
            keywords = [keywords]
        
        # Clean keywords
        clean_keywords = [keyword.strip() for keyword in keywords]
        
        # Join keywords with semicolon for API request
        keywords_str = ';'.join(clean_keywords)
        
        params = {
            "type": match_type,
            "key": settings.SEMRUSH_API_KEY,
            "phrase": keywords_str,
            "database": country.lower(),
            "export_columns": "Ph,Nq,Cp,Co,Kd,In",
            "display_limit": len(keywords)
        }
        
        logger.info(f"Fetching SEMrush data for keywords: {keywords_str}, database: {country}")
        logger.debug(f"SEMrush API params: {params}")
        
        response = requests.get(
            "https://api.semrush.com/",
            params=params,
            timeout=20.0
        )
        
        # Log the full URL and response for debugging
        logger.debug(f"SEMrush API URL: {response.url}")
        logger.debug(f"SEMrush API Response Status: {response.status_code}")
        logger.debug(f"SEMrush API Response Text: {response.text}")
        
        # Check for API errors in response text
        if response.text.startswith("ERROR"):
            logger.warning(f"SEMrush API error for keywords '{keywords_str}': {response.text}")
            return None
            
        # Parse the response
        lines = response.text.strip().split('\n')
        if len(lines) < 2:
            logger.warning(f"No data found for keywords '{keywords_str}'")
            return None
            
        # Skip header row, parse all data rows
        results = []
        for line in lines[1:]:
            data_row = line.split(';')
            if len(data_row) < 6:
                logger.warning(f"Incomplete data for row: {line}")
                continue
            
            # Map the data to our schema
            result = {
                "keyword": data_row[0],
                "search_volume": int(data_row[1]) if data_row[1].isdigit() else 0,
                "cpc": float(data_row[2].replace(',','.')) if data_row[2] else 0.0,
                "competition": float(data_row[3].replace(',','.')) if data_row[3] else 0.0,
                "difficulty": int(data_row[4]) if data_row[4].isdigit() else 0,
                "intent": INTENT_MAPPING.get(data_row[5].strip().rstrip('%'), "unknown")
            }
            results.append(result)
        
        return results if results else None
        
    except Exception as e:
        logger.error(f"Error fetching SEMrush data: {str(e)}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return None
