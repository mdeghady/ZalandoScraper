from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional, Dict, Any
from enum import Enum

class AvailabilityStatus(str, Enum):
    IN_STOCK = "in_stock"
    OUT_OF_STOCK = "out_of_stock"
    LOW_STOCK = "low_stock"
    UNKNOWN = "unknown"

class SizeInfo(BaseModel):
    size: str
    price: Optional[str] = None
    availability: AvailabilityStatus
    stock_quantity: Optional[int] = None
    sku: Optional[str] = None

class ProductData(BaseModel):
    """Model for API product data"""
    id: str
    name: str
    sku: str
    brand: str
    model_number : Optional[str] = None
    gtin: Optional[str] = None
    display_price: Dict[str, Any]
    packshot_image: Optional[str] = None
    silhouette: Optional[str] = None
    navigation_target_group: Optional[str] = None
    simples: List[Dict[str, Any]] = Field(default_factory=list)

class SkuData(BaseModel):
    """Model for SKU data"""
    sku: str
    model_number: Optional[str] = None
    gtin: Optional[str] = None
    simples: List[Dict[str, Any]] = Field(default_factory=list)

class CrawlData(BaseModel):
    """Model for crawl data"""
    available_sizes: List[SizeInfo] = Field(default_factory=list)
    product_highlight: Optional[str] = None
    url: HttpUrl

class APIProductResponse(BaseModel):
    """Combined API response from both scrapers"""
    product_data: Optional[ProductData] = None
    sku_data: Optional[SkuData] = None
    crawl_data: Optional[CrawlData] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class ScrapeRequest(BaseModel):
    url: HttpUrl = Field(..., description="Zalando product URL")

class ScrapeResponse(BaseModel):
    success: bool
    data: Optional[APIProductResponse] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)