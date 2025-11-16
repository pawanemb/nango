from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from typing import List, Optional, Dict, Union, Any
from datetime import datetime, timedelta
import json
from app.models.gsc import GSCDimension, GSCAccount
from sqlalchemy.orm import Session
from uuid import UUID

from app.core.logging_config import logger
from app.utils.domain_authority import get_domain_authority

SCOPES = [
    'https://www.googleapis.com/auth/webmasters.readonly',
    'https://www.googleapis.com/auth/webmasters',
    'https://www.googleapis.com/auth/userinfo.email',
    'openid',
    'https://www.googleapis.com/auth/userinfo.profile'
]

class GSCService:
    """Service for interacting with Google Search Console API"""

    def __init__(self, db: Session, project_id: UUID):
        """Initialize GSC service"""
        try:
            # Get GSC credentials from database
            gsc_account = db.query(GSCAccount).filter(
                GSCAccount.project_id == project_id
            ).first()

            if not gsc_account:
                raise Exception("No GSC account found for this project")

            # Parse credentials from JSON
            credentials = gsc_account.credentials
            if isinstance(credentials, str):
                credentials = json.loads(credentials)

            # Create credentials from stored token
            creds = Credentials(
                token=credentials.get('token'),
                refresh_token=credentials.get('refresh_token'),
                token_uri=credentials.get('token_uri'),
                client_id=credentials.get('client_id'),
                client_secret=credentials.get('client_secret'),
                scopes=credentials.get('scopes', SCOPES)
            )

            # Build the service
            self.service = build('searchconsole', 'v1', credentials=creds)
            self.db = db
            self.project_id = project_id
            self.credentials = credentials
            self.gsc_account = gsc_account
            logger.info(f"GSC service initialized for project {project_id}")

        except Exception as e:
            logger.error(f"Error initializing GSC service: {str(e)}")
            raise Exception(f"Failed to initialize GSC service: {str(e)}")

    async def _refresh_token_if_needed(self):
        """Refresh the access token if it's expired"""
        try:
            # Get current GSC account
            gsc_account = self.db.query(GSCAccount).filter(
                GSCAccount.project_id == self.project_id
            ).first()

            if not gsc_account:
                raise Exception("No GSC account found")

            # Parse credentials from JSON
            credentials = gsc_account.credentials
            if isinstance(credentials, str):
                credentials = json.loads(credentials)

            # Check if token needs refresh
            if credentials.get('expiry') and datetime.now() >= datetime.fromisoformat(credentials['expiry']):
                logger.info("Refreshing GSC access token")
                
                # Create credentials for refresh
                creds = Credentials(
                    token=credentials.get('token'),
                    refresh_token=credentials.get('refresh_token'),
                    token_uri=credentials.get('token_uri'),
                    client_id=credentials.get('client_id'),
                    client_secret=credentials.get('client_secret'),
                    scopes=credentials.get('scopes', SCOPES)
                )

                # Refresh the token
                request = Request()
                try:
                    creds.refresh(request)
                    
                    # Update stored credentials with new tokens
                    self.credentials.update({
                        'token': creds.token,
                        'refresh_token': creds.refresh_token,
                        'token_uri': creds.token_uri,
                        'client_id': creds.client_id,
                        'client_secret': creds.client_secret,
                        'scopes': creds.scopes
                    })
                except Exception as e:
                    logger.error(f"Error refreshing token: {str(e)}")
                    raise

                # Update database with new token
                gsc_account.credentials = self.credentials
                self.db.commit()

                # Rebuild service with new credentials
                self.service = build('searchconsole', 'v1', credentials=creds)
                logger.info("GSC token refreshed successfully")

        except Exception as e:
            logger.error(f"Error refreshing GSC token: {str(e)}")
            raise Exception(f"Failed to refresh GSC token: {str(e)}")

    async def get_search_analytics(
        self,
        site_url: str,
        start_date: str,
        end_date: str,
        dimensions: List[GSCDimension],
        row_limit: int = 1000
    ):
        """Get search analytics data from Google Search Console"""
        try:
            await self._refresh_token_if_needed()
            body = {
                'startDate': start_date,
                'endDate': end_date,
                'dimensions': [dim.value for dim in dimensions],
                'rowLimit': row_limit
            }

            response = self.service.searchanalytics().query(
                siteUrl=site_url,
                body=body
            ).execute()
            
            return response.get('rows', [])
        except Exception as e:
            raise Exception(f"Failed to fetch search analytics: {str(e)}")

    async def get_sites(self):
        """Get list of sites from Google Search Console"""
        try:
            await self._refresh_token_if_needed()
            sites = self.service.sites().list().execute()
            return sites.get('siteEntry', [])
        except Exception as e:
            raise Exception(f"Failed to fetch sites: {str(e)}")

    async def verify_credentials(self, credentials: Dict, site_url: str) -> bool:
        """Verify GSC credentials by attempting to access the API"""
        try:
            # Create credentials object with token refresh capability
            creds = Credentials(
                token=credentials.get('token'),
                refresh_token=credentials.get('refresh_token'),
                token_uri=credentials.get('token_uri'),
                client_id=credentials.get('client_id'),
                client_secret=credentials.get('client_secret'),
                scopes=['https://www.googleapis.com/auth/webmasters.readonly']
            )

            # Build the service with credentials that can auto-refresh
            service = build('searchconsole', 'v1', credentials=creds)

            # First check if we can access the API at all
            try:
                sites = service.sites().list().execute()
                site_urls = [site['siteUrl'] for site in sites.get('siteEntry', [])]
                
                if site_url not in site_urls:
                    logger.error(f"Site {site_url} not found in user's GSC account. Available sites: {site_urls}")
                    return False
                    
                # Now verify we have permission to access this specific site
                test_query = {
                    'startDate': '2024-01-01',
                    'endDate': '2024-01-01',
                    'dimensions': ['query'],
                    'rowLimit': 1
                }
                service.searchanalytics().query(siteUrl=site_url, body=test_query).execute()
                return True
                
            except Exception as api_error:
                if 'sufficient permission' in str(api_error):
                    logger.error(f"Permission denied for site {site_url}. Error: {str(api_error)}")
                    return False
                raise
                
        except Exception as e:
            logger.error(f"Error verifying GSC credentials: {str(e)}")
            return False

    async def get_search_analytics_summary(
        self,
        site_url: str,
        start_date: str,
        end_date: str,
        dimensions: List[str] = None,
        previous: bool = False,
        compare: bool = True
    ):
        """Get search analytics summary metrics with comparison to previous period"""
        try:
            await self._refresh_token_if_needed()
            # Calculate previous period dates if needed
            previous_start_date = None
            previous_end_date = None
            if compare:
                from datetime import datetime, timedelta
                start = datetime.strptime(start_date, "%Y-%m-%d")
                end = datetime.strptime(end_date, "%Y-%m-%d")
                period_length = (end - start).days + 1
                previous_end_date = (start - timedelta(days=1)).strftime("%Y-%m-%d")
                previous_start_date = (start - timedelta(days=period_length)).strftime("%Y-%m-%d")

            # Get current period metrics
            current_metrics = await self._execute_query(
                site_url=site_url,
                start_date=start_date,
                end_date=end_date,
                dimensions=dimensions if dimensions else [],
                filters=None,
                row_limit=1000,
                start_row=0
            )

            # Initialize metrics
            current_data = {
                'clicks': 0,
                'impressions': 0,
                'ctr': 0,
                'position': 0
            }

            # Extract current period metrics
            if current_metrics:
                for row in current_metrics:
                    current_data['clicks'] += row.get('clicks', 0)
                    current_data['impressions'] += row.get('impressions', 0)
                    current_data['ctr'] += row.get('ctr', 0) * row.get('impressions', 0)
                    current_data['position'] += row.get('position', 0) * row.get('impressions', 0)

                if current_data['impressions'] > 0:
                    current_data['ctr'] = round((current_data['ctr'] / current_data['impressions']) * 100, 2)  # Convert to percentage
                    current_data['position'] = round(current_data['position'] / current_data['impressions'], 2)

            # Get previous period metrics if needed
            previous_data = None
            if compare and previous_start_date and previous_end_date:
                previous_metrics = await self._execute_query(
                    site_url=site_url,
                    start_date=previous_start_date,
                    end_date=previous_end_date,
                    dimensions=dimensions if dimensions else [],
                    filters=None,
                    row_limit=1000,
                    start_row=0
                )

                if previous_metrics:
                    previous_data = {
                        'clicks': 0,
                        'impressions': 0,
                        'ctr': 0,
                        'position': 0
                    }

                    for row in previous_metrics:
                        previous_data['clicks'] += row.get('clicks', 0)
                        previous_data['impressions'] += row.get('impressions', 0)
                        previous_data['ctr'] += row.get('ctr', 0) * row.get('impressions', 0)
                        previous_data['position'] += row.get('position', 0) * row.get('impressions', 0)

                    if previous_data['impressions'] > 0:
                        previous_data['ctr'] = round((previous_data['ctr'] / previous_data['impressions']) * 100, 2)  # Convert to percentage
                        previous_data['position'] = round(previous_data['position'] / previous_data['impressions'], 2)

            # Calculate changes if we have previous data
            changes = None
            if previous_data:
                changes = {
                    'clicks': round(self._calculate_percentage_change(
                        previous_data['clicks'], current_data['clicks']
                    ), 2),
                    'impressions': round(self._calculate_percentage_change(
                        previous_data['impressions'], current_data['impressions']
                    ), 2),
                    'ctr': round(self._calculate_percentage_change(
                        previous_data['ctr'], current_data['ctr']
                    ), 2),
                    'position': round(self._calculate_percentage_change(
                        previous_data['position'], current_data['position'],
                        reverse=True  # Lower position is better
                    ), 2)
                }

            return {
                'current': {
                    'clicks': current_data['clicks'],
                    'impressions': current_data['impressions'],
                    'ctr': current_data['ctr'],  # Now as percentage
                    'position': current_data['position']
                },
                'previous': {
                    'clicks': previous_data['clicks'],
                    'impressions': previous_data['impressions'],
                    'ctr': previous_data['ctr'],  # Now as percentage
                    'position': previous_data['position']
                } if previous_data else None,
                'changes': changes
            }

        except Exception as e:
            logger.error(f"Failed to fetch search analytics summary: {str(e)}")
            raise Exception(f"Failed to fetch search analytics summary: {str(e)}")

    async def get_report_analytics_summary(
        self,
        site_url: str,
        start_date: str,
        end_date: str,
        country: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get search analytics summary for report"""
        try:
            # Get current GSC account
            gsc_account = self.db.query(GSCAccount).filter(
                GSCAccount.project_id == self.project_id
            ).first()

            if not gsc_account:
                raise Exception("No GSC account found")

            # Parse credentials from JSON
            credentials = gsc_account.credentials
            if isinstance(credentials, str):
                credentials = json.loads(credentials)

            # Create credentials object
            creds = Credentials(
                token=credentials.get('token'),
                refresh_token=credentials.get('refresh_token'),
                token_uri=credentials.get('token_uri'),
                client_id=credentials.get('client_id'),
                client_secret=credentials.get('client_secret'),
                scopes=credentials.get('scopes', SCOPES)
            )

            # Check if token needs refresh
            if credentials.get('expiry') and datetime.now() >= datetime.fromisoformat(credentials['expiry']):
                logger.info("Refreshing GSC access token")
                request = Request()
                try:
                    creds.refresh(request)
                    
                    # Update stored credentials with new tokens
                    self.credentials.update({
                        'token': creds.token,
                        'refresh_token': creds.refresh_token,
                        'token_uri': creds.token_uri,
                        'client_id': creds.client_id,
                        'client_secret': creds.client_secret,
                        'scopes': creds.scopes
                    })
                except Exception as e:
                    logger.error(f"Error refreshing token: {str(e)}")
                    raise

                # Update database with new token
                gsc_account.credentials = self.credentials
                self.db.commit()

            # Build service with credentials
            service = build('searchconsole', 'v1', credentials=creds)

            # Get search analytics data
            request = {
                'startDate': start_date,
                'endDate': end_date,
                'dimensions': [],  # No dimensions for summary
                'searchType': 'web'
            }
            
            if country:
                request['dimensionFilterGroups'] = [{
                    'filters': [{
                        'dimension': 'country',
                        'operator': 'equals',
                        'expression': country
                    }]
                }]

            response = service.searchanalytics().query(
                siteUrl=site_url,
                body=request
            ).execute()

            # Process response
            summary = {
                'total_clicks': 0,
                'total_impressions': 0,
                'average_ctr': 0.0,
                'average_position': 0.0
            }

            if 'rows' in response and response['rows']:
                row = response['rows'][0]  # Summary data is in a single row
                summary = {
                    'total_clicks': int(row.get('clicks', 0)),
                    'total_impressions': int(row.get('impressions', 0)),
                    'average_ctr': round(row.get('ctr', 0) * 100, 2),  # Convert to percentage
                    'average_position': round(row.get('position', 0), 2)
                }

            # Calculate previous period dates (same duration as current period)
            current_start = datetime.strptime(start_date, '%Y-%m-%d')
            current_end = datetime.strptime(end_date, '%Y-%m-%d')
            date_diff = (current_end - current_start).days
            
            prev_end = current_start - timedelta(days=1)
            prev_start = prev_end - timedelta(days=date_diff)
            
            prev_start_str = prev_start.strftime('%Y-%m-%d')
            prev_end_str = prev_end.strftime('%Y-%m-%d')
            
            # Get search analytics data for previous period
            prev_request = {
                'startDate': prev_start_str,
                'endDate': prev_end_str,
                'dimensions': [],
                'searchType': 'web'
            }
            
            if country:
                prev_request['dimensionFilterGroups'] = request['dimensionFilterGroups']
                
            prev_response = service.searchanalytics().query(
                siteUrl=site_url,
                body=prev_request
            ).execute()
            
            # Process response for previous period
            prev_summary = {
                'total_clicks': 0,
                'total_impressions': 0,
                'average_ctr': 0.0,
                'average_position': 0.0
            }
            
            if 'rows' in prev_response and prev_response['rows']:
                row = prev_response['rows'][0]
                prev_summary = {
                    'total_clicks': int(row.get('clicks', 0)),
                    'total_impressions': int(row.get('impressions', 0)),
                    'average_ctr': round(row.get('ctr', 0) * 100, 2),
                    'average_position': round(row.get('position', 0), 2)
                }
            
            # Calculate percentage changes
            summary['impressions_change'] = self._calculate_percentage_change(
                prev_summary['total_impressions'], 
                summary['total_impressions']
            )
            
            summary['ctr_change'] = self._calculate_percentage_change(
                prev_summary['average_ctr'],
                summary['average_ctr']
            )
            
            # For position, a lower number is better, so we reverse the calculation
            summary['position_change'] = self._calculate_percentage_change(
                prev_summary['average_position'],
                summary['average_position'],
                reverse=True
            )
            
            return summary

        except Exception as e:
            logger.error(f"Error getting search analytics summary: {str(e)}")
            return {
                'total_clicks': 0,
                'total_impressions': 0,
                'average_ctr': 0.0,
                'average_position': 0.0,
                'impressions_change': 0.0,
                'ctr_change': 0.0,
                'position_change': 0.0
            }

    async def get_search_analytics_timeseries(
        self,
        site_url: str,
        start_date: str,
        end_date: str,
        dimensions: List[str] = None,
        filters: Dict = None
    ):
        """Get search analytics timeseries data"""
        try:
            logger.info(f"Fetching GSC timeseries for {site_url} from {start_date} to {end_date}")
            
            # Default dimensions
            if not dimensions:
                dimensions = ['date']  # At minimum include date for timeseries
            
            # Build request body
            request = {
                'startDate': start_date,
                'endDate': end_date,
                'dimensions': dimensions,
                'rowLimit': 25000  # Maximum allowed by API
            }
            
            # Add filters if provided
            if filters:
                # Convert filters to API format
                dimension_filter_groups = []
                for dimension, value in filters.items():
                    if value:
                        dimension_filter_groups.append({
                            'filters': [{
                                'dimension': dimension,
                                'operator': 'equals',
                                'expression': value
                            }]
                        })
                if dimension_filter_groups:
                    request['dimensionFilterGroups'] = dimension_filter_groups

            # Execute request
            response = self.service.searchanalytics().query(
                siteUrl=site_url,
                body=request
            ).execute()

            # Process response
            timeseries_data = []
            if 'rows' in response:
                for row in response['rows']:
                    data_point = {
                        'dimensions': {},
                        'metrics': {
                            'clicks': row['clicks'],
                            'impressions': row['impressions'],
                            'ctr': row['ctr'],
                            'position': row['position']
                        }
                    }
                    
                    # Map dimension values to names
                    for i, dim_value in enumerate(row['keys']):
                        data_point['dimensions'][dimensions[i]] = dim_value
                    
                    timeseries_data.append(data_point)

            return {
                'data': timeseries_data,
                'total_rows': len(timeseries_data)
            }

        except Exception as e:
            logger.error(f"Error fetching GSC timeseries: {str(e)}")
            raise Exception(f"Error fetching GSC timeseries: {str(e)}")

    async def get_page_indexing_stats(self, site_url: str) -> Dict[str, int]:
        """Get page indexing statistics from GSC"""
        try:
            # Get current GSC account
            gsc_account = self.db.query(GSCAccount).filter(
                GSCAccount.project_id == self.project_id
            ).first()

            if not gsc_account:
                raise Exception("No GSC account found")

            # Parse credentials from JSON
            credentials = gsc_account.credentials
            if isinstance(credentials, str):
                credentials = json.loads(credentials)

            # Create credentials object
            creds = Credentials(
                token=credentials.get('token'),
                refresh_token=credentials.get('refresh_token'),
                token_uri=credentials.get('token_uri'),
                client_id=credentials.get('client_id'),
                client_secret=credentials.get('client_secret'),
                scopes=credentials.get('scopes', SCOPES)
            )

            # Check if token needs refresh
            if credentials.get('expiry') and datetime.now() >= datetime.fromisoformat(credentials['expiry']):
                logger.info("Refreshing GSC access token")
                request = Request()
                try:
                    creds.refresh(request)
                    
                    # Update stored credentials with new tokens
                    self.credentials.update({
                        'token': creds.token,
                        'refresh_token': creds.refresh_token,
                        'token_uri': creds.token_uri,
                        'client_id': creds.client_id,
                        'client_secret': creds.client_secret,
                        'scopes': creds.scopes
                    })
                except Exception as e:
                    logger.error(f"Error refreshing token: {str(e)}")
                    raise

                # Update database with new token
                gsc_account.credentials = self.credentials
                self.db.commit()

            # Build service with credentials
            service = build('searchconsole', 'v1', credentials=creds)

            # Use Search Analytics API to get indexed pages
            current_date = datetime.now()
            start_date = (current_date - timedelta(days=7)).strftime('%Y-%m-%d')
            end_date = current_date.strftime('%Y-%m-%d')

            # Get all pages that received impressions (these are indexed)
            request = {
                'startDate': start_date,
                'endDate': end_date,
                'dimensions': ['page'],
                'rowLimit': 25000  # Maximum allowed by API
            }
            
            response = service.searchanalytics().query(
                siteUrl=site_url,
                body=request
            ).execute()

            # Count unique pages that are indexed
            indexed_pages = set()
            if 'rows' in response:
                for row in response['rows']:
                    page_url = row['keys'][0]
                    if page_url.startswith(site_url):
                        indexed_pages.add(page_url)

            # Get total pages from sitemap or estimate
            total_pages = 120  # This should be dynamically fetched from sitemap

            # Calculate not indexed pages
            not_indexed = max(0, total_pages - len(indexed_pages))

            return {
                "total": total_pages,
                "indexed": len(indexed_pages),
                "not_indexed": not_indexed
            }

        except Exception as e:
            logger.error(f"Error fetching page indexing stats: {str(e)}")
            return {
                "total": 0,
                "indexed": 0,
                "not_indexed": 0
            }

    async def get_ranking_overview(
        self,
        site_url: str,
        start_date: str,
        end_date: str
    ) -> Dict[str, Dict[str, Union[int, float]]]:
        """Get ranking distribution overview"""
        try:
            # Get current GSC account
            gsc_account = self.db.query(GSCAccount).filter(
                GSCAccount.project_id == self.project_id
            ).first()

            if not gsc_account:
                raise Exception("No GSC account found")

            # Parse credentials from JSON
            credentials = gsc_account.credentials
            if isinstance(credentials, str):
                credentials = json.loads(credentials)

            # Create credentials object
            creds = Credentials(
                token=credentials.get('token'),
                refresh_token=credentials.get('refresh_token'),
                token_uri=credentials.get('token_uri'),
                client_id=credentials.get('client_id'),
                client_secret=credentials.get('client_secret'),
                scopes=credentials.get('scopes', SCOPES)
            )

            # Check if token needs refresh
            if credentials.get('expiry') and datetime.now() >= datetime.fromisoformat(credentials['expiry']):
                logger.info("Refreshing GSC access token")
                request = Request()
                try:
                    creds.refresh(request)
                    
                    # Update stored credentials with new tokens
                    self.credentials.update({
                        'token': creds.token,
                        'refresh_token': creds.refresh_token,
                        'token_uri': creds.token_uri,
                        'client_id': creds.client_id,
                        'client_secret': creds.client_secret,
                        'scopes': creds.scopes
                    })
                except Exception as e:
                    logger.error(f"Error refreshing token: {str(e)}")
                    raise

                # Update database with new token
                gsc_account.credentials = self.credentials
                self.db.commit()

            # Build service with credentials
            service = build('searchconsole', 'v1', credentials=creds)

            # Get all pages with their positions
            request = {
                'startDate': start_date,
                'endDate': end_date,
                'dimensions': ['page'],
                'rowLimit': 25000,  # Maximum allowed by API
                'searchType': 'web'
            }
            
            response = service.searchanalytics().query(
                siteUrl=site_url,
                body=request
            ).execute()

            # Initialize position ranges
            position_ranges = {
                '1-3': 0,
                '4-10': 0,
                '11-20': 0,
                '21-50': 0,
                '51-100': 0
            }

            # Process response
            total_pages = 0
            if 'rows' in response:
                for row in response['rows']:
                    position = float(row.get('position', 0))
                    
                    # Increment appropriate range
                    if 1 <= position <= 3:
                        position_ranges['1-3'] += 1
                    elif 4 <= position <= 10:
                        position_ranges['4-10'] += 1
                    elif 11 <= position <= 20:
                        position_ranges['11-20'] += 1
                    elif 21 <= position <= 50:
                        position_ranges['21-50'] += 1
                    elif 51 <= position <= 100:
                        position_ranges['51-100'] += 1
                    
                    total_pages += 1

            return {
                'position_ranges': position_ranges
            }

        except Exception as e:
            logger.error(f"Error fetching ranking overview: {str(e)}")
            return {
                'position_ranges': {
                    '1-3': 0,
                    '4-10': 0,
                    '11-20': 0,
                    '21-50': 0,
                    '51-100': 0
                }
            }

    async def get_top_performing_pages(
        self,
        site_url: str,
        start_date: str,
        end_date: str,
        country: Optional[str] = None,
        page_size: int = 10,
        page: int = 1,
        sort_by: str = "impressions",
        sort_desc: bool = True,
        filters: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Get top performing pages with pagination"""
        try:
            # Build request body
            body = {
                'startDate': start_date,
                'endDate': end_date,
                'dimensions': ['page'],
                'rowLimit': page_size * 2,  # Get extra item to check if there's more
                'startRow': (page - 1) * page_size,
                'searchType': 'web'
            }

            # Add sorting
            if sort_by:
                body['orderBy'] = [{
                    'field': sort_by,
                    'sortOrder': 'DESCENDING' if sort_desc else 'ASCENDING'
                }]

            # Add filters if provided
            if filters:
                # Convert filters to API format
                dimension_filter_groups = []
                for dimension, value in filters.items():
                    if value:
                        dimension_filter_groups.append({
                            'filters': [{
                                'dimension': dimension,
                                'operator': 'equals',
                                'expression': value
                            }]
                        })
                if dimension_filter_groups:
                    body['dimensionFilterGroups'] = dimension_filter_groups

            # Execute the query
            response = self.service.searchanalytics().query(
                siteUrl=site_url,
                body=body
            ).execute()

            # Process response
            pages = []
            if 'rows' in response:
                for row in response['rows'][:page_size]:  # Only take requested page size
                    pages.append({
                        'page': row['keys'][0],
                        'clicks': int(row.get('clicks', 0)),
                        'impressions': int(row.get('impressions', 0)),
                        'ctr': round(row.get('ctr', 0) * 100, 2),
                        'position': round(row.get('position', 0), 2)
                    })

            # Check if there are more pages
            has_more = len(response.get('rows', [])) > page_size

            # Calculate total pages
            total_items = (page - 1) * page_size + len(pages)
            if has_more:
                total_items += page_size  # Estimate at least one more page

            return {
                'items': pages,
                'total': total_items,
                'current_page': page,
                'total_pages': (total_items + page_size - 1) // page_size,
                'page_size': page_size,
                'has_more': has_more
            }

        except Exception as e:
            logger.error(f"Error getting top performing pages: {str(e)}")
            return {
                'items': [],
                'total': 0,
                'current_page': page,
                'total_pages': 0,
                'page_size': page_size,
                'has_more': False
            }

    async def get_metrics_breakdown(
        self,
        site_url: str,
        start_date: str,
        end_date: str,
        breakdown_type: str  # 'country' or 'device'
    ):
        """Get metrics breakdown by country or device"""
        try:
            await self._refresh_token_if_needed()
            # Query for breakdown
            body = {
                'startDate': start_date,
                'endDate': end_date,
                'dimensions': [breakdown_type],
                'rowLimit': 250  # Get all possible values
            }

            response = self.service.searchanalytics().query(
                siteUrl=site_url,
                body=body
            ).execute()

            breakdown_data = []
            total_impressions = 0
            total_clicks = 0

            if response.get('rows'):
                # Calculate totals first
                for row in response['rows']:
                    total_impressions += row.get('impressions', 0)
                    total_clicks += row.get('clicks', 0)

                # Process each row
                for row in response['rows']:
                    value = row['keys'][0]  # country or device value
                    impressions = row.get('impressions', 0)
                    clicks = row.get('clicks', 0)
                    
                    # Calculate percentages
                    impression_percentage = round((impressions / total_impressions * 100), 1) if total_impressions > 0 else 0
                    click_percentage = round((clicks / total_clicks * 100), 1) if total_clicks > 0 else 0
                    
                    breakdown_data.append({
                        'key': value,
                        'impressions': int(impressions),
                        'clicks': int(clicks),
                        'ctr': round(row.get('ctr', 0) * 100, 2),
                        'impression_percentage': impression_percentage,
                        'click_percentage': click_percentage
                    })

                # Sort by impressions descending
                breakdown_data.sort(key=lambda x: x['impressions'], reverse=True)

            return {
                'breakdown': breakdown_data,
                'total_impressions': int(total_impressions),
                'total_clicks': int(total_clicks)
            }

        except Exception as e:
            logger.error(f"Failed to fetch metrics breakdown: {str(e)}")
            raise Exception(f"Failed to fetch metrics breakdown: {str(e)}")

    async def generate_report(
        self,
        site_url: str,
        start_date: str,
        end_date: str,
        country: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate a comprehensive GSC report"""
        try:
            # Calculate previous period dates
            start = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y-%m-%d")
            period_length = (end - start).days + 1
            previous_end_date = (start - timedelta(days=1)).strftime("%Y-%m-%d")
            previous_start_date = (start - timedelta(days=period_length)).strftime("%Y-%m-%d")

            # Get current period analytics
            search_analytics = await self.get_report_analytics_summary(
                site_url=site_url,
                start_date=start_date,
                end_date=end_date,
                country=country
            )

            # Get previous period analytics
            previous_analytics = await self.get_report_analytics_summary(
                site_url=site_url,
                start_date=previous_start_date,
                end_date=previous_end_date,
                country=country
            )

            # Get timeseries data for impressions and CTR
            timeseries_data = await self.get_email_report_timeseries(
                site_url=site_url,
                start_date=start_date,
                end_date=end_date,
                dimensions=['date']
            )

            # Get indexing stats
            indexing_stats = await self.get_page_indexing_stats(site_url)

            # Compile report data
            report_data = {
                "site_url": site_url,
                "time_range": {
                    "start_date": start_date,
                    "end_date": end_date
                },
                "search_analytics": search_analytics,
                "previous_period": previous_analytics,
                "timeseries": timeseries_data,
                "indexing_stats": indexing_stats
            }

            return report_data

        except Exception as e:
            logger.error(f"Error generating GSC report: {str(e)}")
            raise e

    async def get_top_queries(
        self,
        site_url: str,
        start_date: str,
        end_date: str,
        country: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get top performing queries"""
        try:
            # Get current GSC account
            gsc_account = self.db.query(GSCAccount).filter(
                GSCAccount.project_id == self.project_id
            ).first()

            if not gsc_account:
                raise Exception("No GSC account found")

            # Parse credentials from JSON
            credentials = gsc_account.credentials
            if isinstance(credentials, str):
                credentials = json.loads(credentials)

            # Create credentials object
            creds = Credentials(
                token=credentials.get('token'),
                refresh_token=credentials.get('refresh_token'),
                token_uri=credentials.get('token_uri'),
                client_id=credentials.get('client_id'),
                client_secret=credentials.get('client_secret'),
                scopes=credentials.get('scopes', SCOPES)
            )

            # Check if token needs refresh
            if credentials.get('expiry') and datetime.now() >= datetime.fromisoformat(credentials['expiry']):
                logger.info("Refreshing GSC access token")
                request = Request()
                try:
                    creds.refresh(request)
                    
                    # Update stored credentials with new tokens
                    self.credentials.update({
                        'token': creds.token,
                        'refresh_token': creds.refresh_token,
                        'token_uri': creds.token_uri,
                        'client_id': creds.client_id,
                        'client_secret': creds.client_secret,
                        'scopes': creds.scopes
                    })
                except Exception as e:
                    logger.error(f"Error refreshing token: {str(e)}")
                    raise

                # Update database with new token
                gsc_account.credentials = self.credentials
                self.db.commit()

            # Build service with credentials
            service = build('searchconsole', 'v1', credentials=creds)

            # Get top queries
            request = {
                'startDate': start_date,
                'endDate': end_date,
                'dimensions': ['query'],
                'rowLimit': limit,
                'searchType': 'web'
            }
            
            if country:
                request['dimensionFilterGroups'] = [{
                    'filters': [{
                        'dimension': 'country',
                        'expression': country
                    }]
                }]

            response = service.searchanalytics().query(
                siteUrl=site_url,
                body=request
            ).execute()

            # Process response
            queries = []
            if 'rows' in response:
                for row in response['rows']:
                    query = {
                        'query': row['keys'][0],
                        'clicks': row.get('clicks', 0),
                        'impressions': row.get('impressions', 0),
                        'ctr': round(row.get('ctr', 0) * 100, 2),
                        'position': round(row.get('position', 0), 2)
                    }
                    queries.append(query)

            return queries

        except Exception as e:
            logger.error(f"Error getting top queries: {str(e)}")
            return []

    async def generate_gsc_report(
        self,
        site_url: str,
        start_date: str,
        end_date: str,
        country: Optional[str] = None
    ) -> Dict:
        """Generate a comprehensive GSC report"""
        try:
            await self._refresh_token_if_needed()
            # Get search analytics data
            analytics_data = await self._execute_query(
                site_url=site_url,
                start_date=start_date,
                end_date=end_date,
                dimensions=["query", "page", "country", "device"],
                filters={"country": country} if country else None
            )

            # Process analytics data
            processed_analytics = {
                "queries": [],
                "pages": [],
                "countries": [],
                "devices": []
            }

            for row in analytics_data:
                item = {
                    "clicks": row.get("clicks", 0),
                    "impressions": row.get("impressions", 0),
                    "ctr": row.get("ctr", 0),
                    "position": row.get("position", 0)
                }

                if len(row.get("keys", [])) == 4:
                    query, page, country, device = row["keys"]
                    processed_analytics["queries"].append({"query": query, **item})
                    processed_analytics["pages"].append({"page": page, **item})
                    processed_analytics["countries"].append({"country": country, **item})
                    processed_analytics["devices"].append({"device": device, **item})

            # Get page indexing stats
            indexing_stats = await self.get_page_indexing_stats(site_url=site_url)
            
            # Get ranking overview
            ranking_overview = await self.get_ranking_overview(
                site_url=site_url,
                start_date=start_date,
                end_date=end_date
            )

            # Compile report data
            report_data = {
                "site_url": site_url,
                "time_range": {
                    "start_date": start_date,
                    "end_date": end_date
                },
                "search_analytics": processed_analytics,
                "indexing_stats": indexing_stats,
                "ranking_overview": ranking_overview
            }

            return report_data

        except Exception as e:
            logger.error(f"Error generating GSC report: {str(e)}")
            raise Exception(f"Failed to generate GSC report: {str(e)}")

    async def _execute_query(
        self,
        site_url: str,
        start_date: str,
        end_date: str,
        dimensions: List[str],
        filters: Optional[Dict] = None,
        row_limit: int = 1000,
        start_row: int = 0
    ) -> List[Dict]:
        """Execute a GSC search analytics query"""
        try:
            await self._refresh_token_if_needed()
            # Build request body
            request = {
                'startDate': start_date,
                'endDate': end_date,
                'dimensions': dimensions,
                'rowLimit': row_limit,
                'startRow': start_row,
                'searchType': 'web',
                'dataState': 'all'  # Include fresh data
            }

            # Add dimension filters if provided
            if filters:
                dimension_filter_groups = []
                for key, value in filters.items():
                    if not value:
                        continue

                    if key == 'position':
                        try:
                            range_parts = value.replace(' ', '').split('AND')
                            min_pos = float(range_parts[0].replace('>=', ''))
                            max_pos = float(range_parts[1].replace('<=', ''))
                            
                            # For position filtering, we need to use the aggregation
                            request['aggregationType'] = 'byPage'
                            request['dimensionFilterGroups'] = [{
                                'filters': [{
                                    'dimension': 'page',
                                    'expression': site_url,
                                    'operator': 'contains'
                                }]
                            }]
                            
                            # Add position filtering in post-processing
                            request['_position_filter'] = {
                                'min': min_pos,
                                'max': max_pos
                            }
                        except Exception as e:
                            logger.error(f"Error parsing position filter: {str(e)}")
                            continue
                    else:
                        # Handle regular dimension filters
                        dimension_filter_groups.append({
                            'filters': [{
                                'dimension': key,
                                'operator': 'equals',
                                'expression': value
                            }]
                        })

                if dimension_filter_groups and '_position_filter' not in request:
                    request['dimensionFilterGroups'] = dimension_filter_groups

            # Log the request for debugging
            logger.info(f"GSC API Request - Site: {site_url}")
            logger.info(f"Request body: {request}")

            # Execute the query
            response = self.service.searchanalytics().query(
                siteUrl=site_url,
                body=request
            ).execute()

            # Log the response for debugging
            logger.info(f"GSC API Response: {response}")

            # Get the rows
            rows = response.get('rows', [])

            # Apply position filtering if needed
            if '_position_filter' in request:
                position_filter = request['_position_filter']
                rows = [
                    row for row in rows 
                    if position_filter['min'] <= row.get('position', 0) <= position_filter['max']
                ]

            return rows

        except Exception as e:
            logger.error(f"Error executing GSC query: {str(e)}")
            return []

    async def get_timeseries_data(
        self,
        site_url: str,
        start_date: str,
        end_date: str,
        dimensions: List[str] = None,
        filters: Dict = None
    ) -> Dict:
        """Get time series data for search analytics metrics"""
        try:
            # Ensure we have the date dimension
            if not dimensions:
                dimensions = ['date']
            elif 'date' not in dimensions:
                dimensions.insert(0, 'date')

            # Build request body
            request = {
                'startDate': start_date,
                'endDate': end_date,
                'dimensions': dimensions,
                'rowLimit': 1000  # Get more data for better visualization
            }
            
            # Add filters if provided
            if filters:
                dimension_filter_groups = []
                for dimension, value in filters.items():
                    if value:
                        dimension_filter_groups.append({
                            'filters': [{
                                'dimension': dimension,
                                'operator': 'equals',
                                'expression': value
                            }]
                        })
                if dimension_filter_groups:
                    request['dimensionFilterGroups'] = dimension_filter_groups

            # Execute request
            response = self.service.searchanalytics().query(
                siteUrl=site_url,
                body=request
            ).execute()

            # Process the response
            result = {
                'data': [],
                'total_clicks': 0,
                'total_impressions': 0
            }

            if response and 'rows' in response:
                for row in response['rows']:
                    # Extract date and metrics
                    date_val = row['keys'][0] if row.get('keys') else None
                    clicks = int(row.get('clicks', 0))
                    impressions = int(row.get('impressions', 0))

                    if date_val:
                        # Add to total metrics
                        result['total_clicks'] += clicks
                        result['total_impressions'] += impressions

                        # Add to data array
                        result['data'].append({
                            'dimensions': {'date': date_val},
                            'metrics': {
                                'clicks': clicks,
                                'impressions': impressions,
                                'ctr': row.get('ctr', 0),
                                'position': row.get('position', 0)
                            }
                        })

            return result

        except Exception as e:
            logger.error(f"Error getting search analytics time series: {str(e)}")
            return {
                'data': [],
                'total_clicks': 0,
                'total_impressions': 0
            }

    async def generate_pdf_report(
        self,
        site_url: str,
        start_date: str,
        end_date: str,
        country: Optional[str] = None
    ) -> bytes:
        """Generate a PDF report with GSC data using the modern GSCPDFGenerator"""
        try:
            # Ensure token is fresh before making any requests
            await self._refresh_token_if_needed()


            async def get_data_with_retry(func, *args, **kwargs):
                """Helper to retry API calls with token refresh"""
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if 'sufficient permission' in str(e):
                        # If it's a permission error, try refreshing token and retry once
                        await self._refresh_token_if_needed()
                        return await func(*args, **kwargs)
                    raise
                
            # Get all necessary report data with retry logic
            analytics_summary = await get_data_with_retry(
                self.get_report_analytics_summary,
                site_url=site_url,
                start_date=start_date,
                end_date=end_date,
                country=country
            )
            
            # Get time series data for the charts
            time_series = await get_data_with_retry(
                self.get_timeseries_data,
                site_url=site_url,
                start_date=start_date,
                end_date=end_date,
                dimensions=['date']
            )
            
            # Get pages indexing data
            pages_data = await get_data_with_retry(
                self.get_page_indexing_stats,
                site_url=site_url
            )
            
            # Get ranking overview data
            ranking_data = await get_data_with_retry(
                self.get_ranking_overview,
                site_url=site_url,
                start_date=start_date,
                end_date=end_date
            )
            da_site_url = site_url
            gda_domain = site_url.startswith("sc-domain:") #check if the domain starts with sc:domain
            if gda_domain:
                da_site_url = site_url.replace("sc-domain:", "")
            # Format data for the PDF generator
            report_data = {
                'site_url': site_url,
                'date_range': {
                    'start': start_date,
                    'end': end_date
                },
                'metrics': {
                    'domain_authority': (await get_domain_authority(domain=da_site_url))['domain_authority'],
                    'domain_authority_change': '+5%',
                    'impressions': analytics_summary.get('total_impressions', 0),
                    'impressions_change': f"{analytics_summary.get('impressions_change', 0):.1f}%",
                    'ctr': analytics_summary.get('average_ctr', 0),
                    'ctr_change': f"{analytics_summary.get('ctr_change', 0):.1f}%",
                    'avg_position': analytics_summary.get('average_position', 0),
                    'position_change': f"{analytics_summary.get('position_change', 0):.1f}%"
                },

                'time_series': {
                    'dates': [],
                    'impressions': [],
                    'clicks': []
                },
                'pages': {
                    'total': pages_data.get('total', 120),
                    'indexed': pages_data.get('indexed', 100),
                    'not_indexed': pages_data.get('not_indexed', 20)
                },
                'ranking_overview': {
                    'position_ranges': ranking_data.get('position_ranges', {})
                }
            }
            
            # Process time series data
            if time_series and isinstance(time_series, dict) and 'data' in time_series:
                for row in time_series['data']:
                    if isinstance(row, dict):
                        # Get date from dimensions
                        date = row.get('dimensions', {}).get('date')
                        
                        # Get metrics
                        metrics = row.get('metrics', {})
                        impressions = metrics.get('impressions', 0)
                        clicks = metrics.get('clicks', 0)
                        
                        if date:
                            report_data['time_series']['dates'].append(date)
                            report_data['time_series']['impressions'].append(impressions)
                            report_data['time_series']['clicks'].append(clicks)
            
            # Log the data before generating PDF
            logger.info("Report data prepared successfully")
            logger.debug(f"Report data: {report_data}")
            
            # Use the modern PDF generator
            from app.utils.gsc_pdf_generator import GSCPDFGenerator
            pdf_generator = GSCPDFGenerator()
            
            # Generate the PDF and return the bytes
            logger.info("Generating PDF")
            logger.debug(f"Report data for PDF: {report_data}")
            return pdf_generator.generate_report(report_data)
            
        except Exception as e:
            logger.error(f"Error generating PDF report: {str(e)}")
            raise Exception(f"Failed to generate PDF report: {str(e)}")

    async def get_email_report_timeseries(
        self,
        site_url: str,
        start_date: str,
        end_date: str,
        dimensions: List[str] = None,
        filters: Dict = None
    ) -> Dict[str, Any]:
        """Get time series data specifically formatted for email reports"""
        try:
            # Get current GSC account
            gsc_account = self.db.query(GSCAccount).filter(
                GSCAccount.project_id == self.project_id
            ).first()

            if not gsc_account:
                raise Exception("No GSC account found")

            # Parse credentials from JSON
            credentials = gsc_account.credentials
            if isinstance(credentials, str):
                credentials = json.loads(credentials)

            # Create credentials object
            creds = Credentials(
                token=credentials.get('token'),
                refresh_token=credentials.get('refresh_token'),
                token_uri=credentials.get('token_uri'),
                client_id=credentials.get('client_id'),
                client_secret=credentials.get('client_secret'),
                scopes=credentials.get('scopes', SCOPES)
            )

            # Check if token needs refresh
            if credentials.get('expiry') and datetime.now() >= datetime.fromisoformat(credentials['expiry']):
                logger.info("Refreshing GSC access token")
                request = Request()
                try:
                    creds.refresh(request)
                    
                    # Update stored credentials with new tokens
                    self.credentials.update({
                        'token': creds.token,
                        'refresh_token': creds.refresh_token,
                        'token_uri': creds.token_uri,
                        'client_id': creds.client_id,
                        'client_secret': creds.client_secret,
                        'scopes': creds.scopes
                    })
                except Exception as e:
                    logger.error(f"Error refreshing token: {str(e)}")
                    raise

                # Update database with new token
                gsc_account.credentials = self.credentials
                self.db.commit()

            # Build service with credentials
            service = build('searchconsole', 'v1', credentials=creds)

            # Set default dimensions if not provided
            if not dimensions:
                dimensions = ['date']

            # Prepare request body
            request = {
                'startDate': start_date,
                'endDate': end_date,
                'dimensions': dimensions,
                'rowLimit': 25000,  # Maximum allowed by API
                'searchType': 'web'  # Only include web search data
            }
            
            # Add filters if provided
            if filters:
                request['dimensionFilterGroups'] = [{
                    'filters': [{
                        'dimension': dim,
                        'operator': op,
                        'expression': expr
                    } for dim, (op, expr) in filters.items()]
                }]

            # Execute request
            response = service.searchanalytics().query(
                siteUrl=site_url,
                body=request
            ).execute()

            # Process response data
            timeseries_data = []
            if 'rows' in response:
                # Group data by 3 days to reduce density
                grouped_data = {}
                for row in response['rows']:
                    date_str = row['keys'][0]
                    date = datetime.strptime(date_str, '%Y-%m-%d')
                    # Use the first date of each 3-day period as the key
                    group_key = date - timedelta(days=date.day % 3)
                    
                    if group_key not in grouped_data:
                        grouped_data[group_key] = {
                            'impressions': 0,
                            'clicks': 0,
                            'count': 0
                        }
                    
                    grouped_data[group_key]['impressions'] += int(row['impressions'])
                    grouped_data[group_key]['clicks'] += int(row['clicks'])
                    grouped_data[group_key]['count'] += 1

                # Calculate averages and format data
                for date, data in grouped_data.items():
                    avg_ctr = (data['clicks'] / data['impressions'] * 100) if data['impressions'] > 0 else 0
                    timeseries_data.append({
                        'date': date.strftime('%b %d'),
                        'impressions': data['impressions'] // data['count'],  # Average impressions
                        'ctr': round(avg_ctr, 2)  # Average CTR as percentage
                    })

            # Sort by date
            sorted_data = sorted(timeseries_data, key=lambda x: datetime.strptime(x['date'], '%b %d'))

            # Extract dates and metrics
            dates = [data['date'] for data in sorted_data]
            impressions = [data['impressions'] for data in sorted_data]
            ctr = [data['ctr'] for data in sorted_data]

            return {
                'dates': dates,
                'impressions': impressions,
                'ctr': ctr
            }

        except Exception as e:
            logger.error(f"Error getting email report timeseries: {str(e)}")
            return {
                'dates': [],
                'impressions': [],
                'ctr': []
            }

    def _calculate_percentage_change(self, old_value: float, new_value: float, reverse: bool = False) -> float:
        """Calculate percentage change between two values"""
        if old_value == 0:
            return 100 if new_value > 0 else 0
        
        change = ((new_value - old_value) / old_value) * 100
        return -change if reverse else change