import httpx
from fastapi import HTTPException
from app.core.logging_config import logger

async def get_domain_authority(domain: str) -> dict:
    """
    Get domain authority metrics using RapidAPI service
    
    Args:
        domain: Domain URL to check (without http/https)
        
    Returns:
        dict: Domain authority metrics including DA, PA, and other Moz metrics
    """
    try:
        # RapidAPI endpoint configuration
        url = "https://domain-da-pa-checker.p.rapidapi.com/v1/getDaPa"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "x-rapidapi-ua": "RapidAPI-Playground",
            "x-rapidapi-key": "2c9d46aa1bmsh5e7c92ef2f79015p1558d4jsn9ca6ec5d4d3d",
            "x-rapidapi-host": "domain-da-pa-checker.p.rapidapi.com"
        }
        payload = {"q": domain}

        # Make API request using httpx (async HTTP client)
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()  # Raise exception for non-200 status codes
            
            data = response.json()
            
            # Extract relevant metrics
            return data

    except httpx.HTTPError as e:
        logger.error(f"HTTP error occurred while fetching domain authority: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch domain authority: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error getting domain authority: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error getting domain authority: {str(e)}"
        )
