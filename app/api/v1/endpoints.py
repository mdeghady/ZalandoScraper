from fastapi import APIRouter, HTTPException
from typing import Dict, Any

from app.models.schemas import ScrapeRequest, ScrapeResponse
from app.services.scraper_service import ZalandoScraperService

router = APIRouter()
scraper_service = ZalandoScraperService()


@router.post("/scrape-product", response_model=ScrapeResponse)
async def scrape_product(request: ScrapeRequest) -> ScrapeResponse:
    """
    Scrape Zalando product data from both API and web page

    - **url**: Valid Zalando product URL (e.g., https://www.zalando.it/acdc-calze-mehrfarbig-a9182f001-t11.html)
    """
    try:
        result = await scraper_service.scrape_product(str(request.url))

        if not result.success:
            raise HTTPException(status_code=400, detail=result.error)

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health check endpoint"""
    return {"status": "healthy", "service": "Zalando Scraper API"}