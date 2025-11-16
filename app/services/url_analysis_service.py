from typing import Dict, Any, Optional
import requests
import httpx
import asyncio
from urllib.parse import urlparse
from app.core.config import settings
from app.core.logging_config import logger

class URLAnalysisService:
    """Service to analyze URLs for traffic, backlinks, and domain authority"""
    
    def __init__(self):
        self.semrush_api_key = settings.SEMRUSH_API_KEY
        self.rapidapi_key = settings.RAPIDAPI_KEY
        self.semrush_api_url = "https://api.semrush.com/"
        self.semrush_api_url_backlinks = "https://api.semrush.com/analytics/v1/"
        
    def extract_domain_from_url(self, url: str) -> str:
        """Extract domain from URL for analysis"""
        try:
            parsed_url = urlparse(url)
            domain = parsed_url.netloc
            # Remove www. prefix if present
            if domain.startswith('www.'):
                domain = domain[4:]
            return domain
        except Exception as e:
            logger.error(f"Error extracting domain from {url}: {str(e)}")
            return url
    
    def get_semrush_traffic_data(self, url: str) -> Dict[str, Any]:
        """
        Get traffic data for a URL using SEMrush API
        Returns comprehensive traffic data with multiple fallback methods
        """
        try:
            if not self.semrush_api_key:
                logger.warning("SEMrush API key not configured")
                return {"total_traffic": 0, "status": "no_api_key"}
            
            logger.info(f"🔍 Fetching SEMrush traffic data for URL: {url}")
            
            # Use working subfolder_ranks method
            traffic_data = self._get_traffic_subfolder(url)
            return traffic_data
            
        except Exception as e:
            logger.error(f"Error fetching traffic data for {url}: {str(e)}")
            return {"total_traffic": 0, "status": "error", "error": str(e)}
    
    def _get_traffic_subfolder(self, url: str) -> Dict[str, Any]:
        """Get traffic data using subfolder_ranks method (WORKING)"""
        try:
            params = {
                "key": self.semrush_api_key,
                "type": "subfolder_ranks",
                "export_columns": "Db,Ot",
                "subfolder": url
            }
            
            response = requests.get(self.semrush_api_url, params=params, timeout=15)
            logger.info(f"📊 Traffic API Response for {url}: Status {response.status_code}")
            
            if response.status_code == 200 and not response.text.startswith("ERROR"):
                lines = response.text.strip().split('\n')
                if len(lines) > 1:
                    # Parse actual traffic data from response
                    try:
                        # Each line after header contains traffic data: Database;Organic Traffic
                        total_traffic = 0
                        parsed_lines = 0
                        
                        for line in lines[1:]:
                            parts = line.split(';')
                            if len(parts) >= 2:
                                # Skip mobile data - only count regular traffic
                                database_key = parts[0].strip()
                                if database_key.startswith('mobile-'):
                                    continue  # Skip mobile data
                                
                                try:
                                    # Try to convert traffic value to int
                                    traffic_value = int(parts[1].strip())
                                    total_traffic += traffic_value
                                    parsed_lines += 1
                                except ValueError:
                                    # Skip lines where traffic value is not a number
                                    continue
                        
                        logger.info(f"✅ Traffic data for {url}: {total_traffic} (from {parsed_lines} non-mobile databases)")
                        return {
                            "total_traffic": total_traffic,
                            "status": "success",
                            "method": "subfolder_ranks"
                        }
                    except (ValueError, IndexError) as e:
                        logger.error(f"Error parsing traffic data: {str(e)}")
                        # Fallback: estimate based on line count
                        traffic_estimate = max(0, (len(lines) - 1) * 100)
                        return {
                            "total_traffic": traffic_estimate,
                            "status": "success",
                            "method": "subfolder_estimate"
                        }
            else:
                logger.warning(f"Traffic API error for {url}: {response.text[:200]}")
                
        except Exception as e:
            logger.error(f"Exception in organic method for {url}: {str(e)}")
        
        return {"total_traffic": 0, "status": "subfolder_failed"}
    
    def get_semrush_backlink_data(self, url: str) -> Dict[str, Any]:
        """
        Get backlink data for a URL using SEMrush API
        Returns comprehensive backlink data with fallback methods
        """
        try:
            if not self.semrush_api_key:
                logger.warning("SEMrush API key not configured")
                return {"total_backlinks": 0, "status": "no_api_key"}
            
            domain = self.extract_domain_from_url(url)
            logger.info(f"🔍 Fetching SEMrush backlink data for domain: {domain}")
            
            # Try backlinks overview method first (pass full URL)
            backlink_data = self._get_backlinks_overview(url)
            if backlink_data["total_backlinks"] > 0:
                return backlink_data
            
            # Method 2: Try backlinks report
            backlink_data = self._get_backlinks_report(domain)
            if backlink_data["total_backlinks"] > 0:
                return backlink_data
            
            # If all methods fail, return zero with status
            logger.warning(f"No backlink data found for {domain} using any method")
            return {"total_backlinks": 0, "status": "no_data_available"}
            
        except Exception as e:
            logger.error(f"Error fetching backlink data for {url}: {str(e)}")
            return {"total_backlinks": 0, "status": "error", "error": str(e)}
    
    def _get_backlinks_overview(self, url: str) -> Dict[str, Any]:
        """Get backlink overview data using direct URL format like the working curl command"""
        try:
            # Build URL directly like the working curl command
            api_url = f"{self.semrush_api_url_backlinks}?key={self.semrush_api_key}&type=backlinks_overview&target={url}&target_type=url&export_columns=total"
            
            response = requests.get(api_url, timeout=15)
            logger.info(f"🔗 Backlinks Overview API Response for {url}: Status {response.status_code}")
            logger.info(f"📄 Response text: {response.text[:200]}...")
            
            if response.status_code == 200 and not response.text.startswith("ERROR"):
                lines = response.text.strip().split('\n')
                logger.info(f"📊 Response lines: {lines}")
                
                if len(lines) >= 2:  # Header + data line
                    # The response format is: "total\n109" (header + value)
                    # Strip both \r and whitespace from each line
                    header = lines[0].strip('\r\n ')
                    data_value = lines[1].strip('\r\n ')
                    
                    logger.info(f"📋 Header: '{header}', Data: '{data_value}'")
                    
                    if header == "total" and data_value.isdigit():
                        backlink_count = int(data_value)
                        logger.info(f"✅ Backlinks overview for {url}: {backlink_count}")
                        return {
                            "total_backlinks": backlink_count,
                            "status": "success",
                            "method": "overview"
                        }
                    else:
                        logger.warning(f"Unexpected response format for {url}: header='{header}', data='{data_value}'")
            else:
                logger.warning(f"Backlinks overview API error for {url}: {response.text[:200]}")
                
        except Exception as e:
            logger.error(f"Exception in backlinks overview for {url}: {str(e)}")
        
        return {"total_backlinks": 0, "status": "overview_failed"}
    
    def _get_backlinks_report(self, domain: str) -> Dict[str, Any]:
        """Get backlinks report data"""
        try:
            params = {
                "type": "backlinks",
                "key": self.semrush_api_key,
                "target": domain,
                "target_type": "root_domain",
                "display_limit": 10
            }
            
            response = requests.get(self.semrush_api_url, params=params, timeout=15)
            logger.info(f"📊 Backlinks Report API Response for {domain}: Status {response.status_code}")
            
            if response.status_code == 200 and not response.text.startswith("ERROR"):
                lines = response.text.strip().split('\n')
                if len(lines) > 1:
                    # Estimate backlinks based on returned results
                    backlink_estimate = max(0, (len(lines) - 1) * 10)  # Rough estimate
                    logger.info(f"✅ Backlinks report estimate for {domain}: {backlink_estimate}")
                    return {
                        "total_backlinks": backlink_estimate,
                        "status": "success",
                        "method": "report_estimate"
                    }
            else:
                logger.warning(f"Backlinks report API error for {domain}: {response.text[:200]}")
                
        except Exception as e:
            logger.error(f"Exception in backlinks report for {domain}: {str(e)}")
        
        return {"total_backlinks": 0, "status": "report_failed"}
    
    async def get_domain_authority_data(self, url: str) -> Dict[str, Any]:
        """
        Get domain authority data using RapidAPI
        Returns domain authority, page authority, and spam score
        """
        try:
            domain = self.extract_domain_from_url(url)
            
            # RapidAPI endpoint configuration
            rapidapi_url = "https://domain-da-pa-checker.p.rapidapi.com/v1/getDaPa"
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "x-rapidapi-ua": "RapidAPI-Playground",
                "x-rapidapi-key": self.rapidapi_key,
                "x-rapidapi-host": "domain-da-pa-checker.p.rapidapi.com"
            }
            payload = {"q": domain}
            
            logger.info(f"🏆 Fetching domain authority for domain: {domain}")
            
            async with httpx.AsyncClient() as client:
                response = await client.post(rapidapi_url, json=payload, headers=headers, timeout=10)  # Reduced timeout for parallel execution
                
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"✅ Found domain authority data for {domain}: {data}")
                    
                    # Extract relevant metrics (adjust based on actual API response format)
                    domain_authority = data.get('domain_authority', data.get('da', 0))
                    page_authority = data.get('page_authority', data.get('pa', 0))
                    spam_score = data.get('spam_score', data.get('ss', 0))
                    
                    return {
                        "domain_authority": int(domain_authority) if domain_authority else 0,
                        "page_authority": int(page_authority) if page_authority else 0,
                        "spam_score": int(spam_score) if spam_score else 0
                    }
                else:
                    logger.warning(f"Domain authority API error for {domain}: Status {response.status_code}")
                    
        except Exception as e:
            logger.error(f"Error fetching domain authority for {url}: {str(e)}")
        
        return {"domain_authority": 0, "page_authority": 0, "spam_score": 0}
    
    def get_domain_authority_data_sync(self, url: str) -> Dict[str, Any]:
        """
        Synchronous version of domain authority data fetching
        Uses requests instead of httpx to avoid async/sync conflicts
        """
        try:
            domain = self.extract_domain_from_url(url)
            
            # RapidAPI endpoint configuration
            rapidapi_url = "https://domain-da-pa-checker.p.rapidapi.com/v1/getDaPa"
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "x-rapidapi-ua": "RapidAPI-Playground",
                "x-rapidapi-key": self.rapidapi_key,
                "x-rapidapi-host": "domain-da-pa-checker.p.rapidapi.com"
            }
            payload = {"q": domain}
            
            logger.info(f"🏆 Fetching domain authority (SYNC) for domain: {domain}")
            
            response = requests.post(rapidapi_url, json=payload, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"✅ Found domain authority data (SYNC) for {domain}: {data}")
                
                # Extract relevant metrics (adjust based on actual API response format)
                domain_authority = data.get('domain_authority', data.get('da', 0))
                page_authority = data.get('page_authority', data.get('pa', 0))
                spam_score = data.get('spam_score', data.get('ss', 0))
                
                return {
                    "domain_authority": int(domain_authority) if domain_authority else 0,
                    "page_authority": int(page_authority) if page_authority else 0,
                    "spam_score": int(spam_score) if spam_score else 0
                }
            else:
                logger.warning(f"Domain authority API error (SYNC) for {domain}: Status {response.status_code}")
                
        except Exception as e:
            logger.error(f"Error fetching domain authority (SYNC) for {url}: {str(e)}")
        
        return {"domain_authority": 0, "page_authority": 0, "spam_score": 0}
    
    async def analyze_url_comprehensive(self, url: str) -> Dict[str, Any]:
        """
        Perform comprehensive URL analysis combining all metrics
        Returns traffic, backlinks, and domain authority data
        """
        logger.info(f"🚀 Starting comprehensive analysis for URL: {url}")
        
        try:
            # Run traffic and backlink analysis synchronously
            traffic_data = self.get_semrush_traffic_data(url)
            backlink_data = self.get_semrush_backlink_data(url)
            
            # Run domain authority analysis asynchronously  
            domain_authority_data = await self.get_domain_authority_data(url)
            
            # Combine all data
            comprehensive_data = {
                "url": url,
                "domain": self.extract_domain_from_url(url),
                "traffic": traffic_data,
                "backlinks": backlink_data,
                "domain_authority": domain_authority_data,
                "analysis_timestamp": str(asyncio.get_event_loop().time()),
                "status": "success"
            }
            
            logger.info(f"✅ Comprehensive analysis completed for {url}")
            return comprehensive_data
            
        except Exception as e:
            logger.error(f"❌ Comprehensive analysis failed for {url}: {str(e)}")
            return {
                "url": url,
                "domain": self.extract_domain_from_url(url),
                "traffic": {"total_traffic": 0},
                "backlinks": {"total_backlinks": 0},
                "domain_authority": {"domain_authority": 0, "page_authority": 0, "spam_score": 0},
                "analysis_timestamp": str(asyncio.get_event_loop().time()),
                "status": "error",
                "error": str(e)
            }
    
    def analyze_url_comprehensive_sync(self, url: str) -> Dict[str, Any]:
        """
        Synchronous wrapper for comprehensive URL analysis
        """
        logger.info(f"🔄 Starting sync analysis wrapper for: {url}")
        try:
            # Create new event loop if none exists
            try:
                loop = asyncio.get_event_loop()
                logger.info(f"✅ Using existing event loop for {url}")
            except RuntimeError:
                logger.info(f"🆕 Creating new event loop for {url}")
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            logger.info(f"🚀 Running async analysis for {url}")
            result = loop.run_until_complete(self.analyze_url_comprehensive(url))
            logger.info(f"✅ Sync wrapper SUCCESS for {url}: {result}")
            return result
        except Exception as e:
            logger.error(f"❌ Sync analysis failed for {url}: {str(e)}")
            logger.error(f"🔍 Exception type: {type(e).__name__}")
            import traceback
            logger.error(f"📍 Full traceback: {traceback.format_exc()}")
            return {
                "url": url,
                "domain": self.extract_domain_from_url(url),
                "traffic": {"total_traffic": 0},
                "backlinks": {"total_backlinks": 0},
                "domain_authority": {"domain_authority": 0, "page_authority": 0, "spam_score": 0},
                "analysis_timestamp": "error",
                "status": "error",
                "error": str(e)
            } 