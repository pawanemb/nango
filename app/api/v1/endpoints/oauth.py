from fastapi import APIRouter, Depends, HTTPException, Path, Request
from app.db.session import get_db
from app.core.auth import get_current_user
from app.models.gsc import GSCAccount
from app.models.project import Project
from typing import Dict
from sqlalchemy.orm import Session
import google.oauth2.credentials
import google_auth_oauthlib.flow 
import json
import os
import logging
import requests as http_requests
from dotenv import load_dotenv
from googleapiclient.discovery import build
from app.core.logging_config import logger
from datetime import datetime, timezone
import pytz
from pydantic import BaseModel
from uuid import UUID

class OAuthCallbackRequest(BaseModel):
    code: str
    state: str

# Load environment variables at module level
load_dotenv(override=True)

# This is needed because we're doing local OAuth flow
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

class OAuthCallbackRequest(BaseModel):
    code: str
    state: str

router = APIRouter(tags=["OAuth"])

SCOPES = [
    'https://www.googleapis.com/auth/webmasters.readonly',
    'https://www.googleapis.com/auth/webmasters',
    'https://www.googleapis.com/auth/userinfo.email',
    'openid',
    'https://www.googleapis.com/auth/userinfo.profile'
]

def get_client_config():
    """Get OAuth client configuration from environment variables"""
    client_id = os.environ.get('GOOGLE_CLIENT_ID')
    client_secret = os.environ.get('GOOGLE_CLIENT_SECRET')
    redirect_uri = os.environ.get('GOOGLE_OAUTH_REDIRECT_URI')
    
    logger.info(f"Using client_id: {client_id}")
    
    return {
        "web": {
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uris": [redirect_uri],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }

@router.post("/get-auth-url")
async def get_auth_url(
    project_id: str = Path(..., description="Project ID to connect GSC to"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get the Google OAuth2 authorization URL
    """
    try:
        logger.info(f"Starting OAuth flow for project_id: {project_id}")
        
        client_config = get_client_config()
        logger.info(client_config)
        # Create flow instance from client config
        flow = google_auth_oauthlib.flow.Flow.from_client_config(
            client_config,
            scopes=SCOPES
        )
        flow.redirect_uri = os.environ.get('GOOGLE_OAUTH_REDIRECT_URI')
        logger.info(f"Flow created with redirect_uri: {flow.redirect_uri}")

        # Generate a unique state by combining project_id with timestamp
        unique_state = f"{project_id}_{int(datetime.utcnow().timestamp())}"
        
        auth_url, _ = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            state=unique_state,
            prompt='consent'
        )
        logger.info(f"Generated auth_url: {auth_url}")

        return {"auth_url": auth_url}
    except Exception as e:
        logger.error(f"Error generating auth URL: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

def normalize_url(url: str) -> str:
    """Normalize URL by removing protocol, www, and trailing slashes"""
    try:
        if not url:
            return ""
        url = url.lower().strip('/')
        for prefix in ['https://', 'http://', 'www.','https://www.','http://www.']:
            if url.startswith(prefix):
                url = url[len(prefix):]
        return url.strip('/')
    except Exception as e:
        logger.error(f"Error normalizing URL {url}: {str(e)}")
        return url if url else ""

@router.post("/callback")
async def oauth_callback(
    callback_data: OAuthCallbackRequest,
    request: Request,
    project_id: str = Path(..., description="Project ID to connect GSC to"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Handle the OAuth2 callback from Google
    """
    code = callback_data.code
    state = callback_data.state
    if not code:
        raise HTTPException(status_code=400, detail="Authorization code missing")

    try:
        logger.info(f"Handling callback for state: {state}")
        logger.info(f"Extracted project_id: {project_id}")
        logger.info(f"Code length: {len(code)}")

        client_config = get_client_config()
        flow = google_auth_oauthlib.flow.Flow.from_client_config(
            client_config,
            scopes=SCOPES
        )
        flow.redirect_uri = os.environ.get('GOOGLE_OAUTH_REDIRECT_URI')

        logger.info(f"Flow created with redirect_uri: {flow.redirect_uri}")
        token_response = flow.fetch_token(
            code=code,
            allow_scope_change=True
        )
        logger.info(f"My response: {token_response}")

        credentials = flow.credentials
        logger.info(f"Credentials: {credentials}")
        # Get the GSC site URL using the credentials
        webmasters_service = build('searchconsole', 'v1', credentials=credentials)
        sites = webmasters_service.sites().list().execute()
        logger.info(f"Sites: {sites}")
        if not sites.get('siteEntry'):
            # raise HTTPException(status_code=200, detail="No GSC sites found for this account")
            return {
                "success": False,
                "message": "No GSC sites found for this account"
            }
        # Get project URL
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            logger.error(f"Project not found with ID: {project_id}")
            return {
                "success": False,
                "message": "Project not found"
            }

        if not project.url:
            logger.error(f"Project {project_id} has no URL")
            return {
                "success": False,
                "message": "Project URL is not set"
            }

        logger.info(f"Found project with URL: {project.url}")
        logger.info(f"Available GSC sites: {sites.get('siteEntry')}")

        # Get the project's site from GSC sites
        site_url = None
        project_url = normalize_url(project.url)

        logger.info(f"Normalized project URL: {project_url}")
        logger.info(f"Normalized project URL: {project_url}")
        
        for site in sites.get('siteEntry', []):
            try:
                site_url_raw = site.get('siteUrl', '')
                # Skip domain property sites (sc-domain:)
                # if site_url_raw.startswith('sc-domain:'):
                #     logger.info(f"Skipping domain property: {site_url_raw}")
                #     continue
                    
                gsc_url = normalize_url(site_url_raw)
                logger.info(f"Comparing URLs - Project: {project_url} vs GSC: {gsc_url}")
                logger.info(project_url, gsc_url)
                logger.info(project_url == gsc_url)
                logger.info(f"sc-domain:{project_url}", gsc_url)
                logger.info(f"sc-domain:{project_url}" == gsc_url)
                if (project_url == gsc_url) or (f"sc-domain:{project_url}" == gsc_url):
                    logger.info(f"Found matching URL: {site_url_raw}")
                    if site.get('permissionLevel') in ['siteOwner', 'siteFullUser']:
                        site_url = site_url_raw
                        logger.info(f"Found matching site with correct permissions: {site_url}")
                        break
                    else:
                        logger.warning(f"Found matching site but insufficient permissions: {site_url_raw}")
            except Exception as e:
                logger.error(f"Error processing GSC site {site}: {str(e)}")
                continue

        if not site_url:
            # If no matching site found, return error message with 200 status
            error_msg = f"No verified GSC site found matching project URL: {project.url}. Available sites: {[s.get('siteUrl') for s in sites.get('siteEntry', []) if not s.get('siteUrl', '').startswith('sc-domain:')]}"
            logger.info(error_msg)
            return {
                "success": False,
                "message": error_msg
            }

        logger.info(f"Successfully found GSC site: {site_url}")

        # Create a new GSC account record
        credentials_dict = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes
        }
        gsc_account = GSCAccount(
            project_id=project_id,
            credentials=json.dumps(credentials_dict),
            site_url=site_url
        )

        db.add(gsc_account)
        db.commit()

        # Get token expiration time
        if credentials.expiry:
            # Convert UTC to IST
            ist = pytz.timezone('Asia/Kolkata')
            expiry_ist = credentials.expiry.replace(tzinfo=timezone.utc).astimezone(ist)
            expiry = expiry_ist.isoformat()
        else:
            expiry = None
        
        return {
            "success": True,
            "message": "Successfully connected GSC account",
            "project_id": str(project_id),
            "site_url": site_url,
            "access_token": credentials_dict['token'],
            "token_expiry": expiry
        }

    except Exception as e:
        logger.error(f"Error in OAuth callback: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()
