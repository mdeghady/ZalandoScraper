import json
import re
import logging
from typing import List, Dict, Optional
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode

from app.models.schemas import SizeInfo, AvailabilityStatus, ModernSizeInfo  # NEW
from app.utils.crawl4ai_utils import ZalandoCrawl4AIScraper

logger = logging.getLogger(__name__)


class Crawl4AIScraper:
    """Wrapper around the refactored Crawl4AI functionality."""

    def __init__(self):
        self.scraper = ZalandoCrawl4AIScraper()

    def _normalize_size_data(self, raw_sizes: List[Dict]) -> List[SizeInfo]:
        """Clean and normalize size data from crawler."""
        normalized_sizes = []
        seen_sizes = set()

        for size_data in raw_sizes:
            if not size_data.get("Size"):
                continue

            size = size_data["Size"].strip()

            # Filter out invalid sizes and duplicates
            if (not size or
                    size.startswith(('€', '$', '£')) or  # Price mistaken as size
                    size in seen_sizes):
                continue

            seen_sizes.add(size)

            # Determine availability
            availability_text = size_data.get("Availability", "").lower()
            stock_quantity = None

            if "esaurito" in availability_text or "out of stock" in availability_text:
                availability = AvailabilityStatus.OUT_OF_STOCK
            elif "articoli disponibili" in availability_text or "available" in availability_text:
                availability = AvailabilityStatus.IN_STOCK
                # Extract stock quantity
                quantity_match = re.search(r'(\d+)\s*articoli? disponibili?', availability_text)
                if quantity_match:
                    stock_quantity = int(quantity_match.group(1))
                    if stock_quantity <= 3:
                        availability = AvailabilityStatus.LOW_STOCK
            elif "1 articolo disponibile" in availability_text:
                availability = AvailabilityStatus.LOW_STOCK
                stock_quantity = 1
            else:
                # If no availability info, assume in stock
                availability = AvailabilityStatus.IN_STOCK

            normalized_sizes.append(SizeInfo(
                size=size,
                price=size_data.get("Price"),
                availability=availability,
                stock_quantity=stock_quantity
            ))

        return normalized_sizes

    async def scrape_product_page(self, url: str) -> Optional[Dict]:
        """Scrape product page using the refactored Crawl4AI scraper."""
        try:
            # Use the refactored scraper instead of the old implementation
            result = await self.scraper.scrape_product_page(url)

            if result and result["success"]:
                # Transform the result to match the expected format with modern sizes
                transformed_data = self._transform_to_modern_format(result)  # UPDATED
                return transformed_data

            logger.warning("Scraping failed or returned no data")
            return None

        except Exception as e:
            logger.error(f"Crawler error: {e}")
            return None

    def _transform_to_modern_format(self, result: Dict) -> Dict:  # NEW METHOD
        """Transform to modern format with SKU-keyed size dictionary."""
        try:
            raw_data = result.get("raw_extracted_data", {})
            structured_data = result.get("structured_data", {})

            # Get modern sizes directly from the refactored scraper
            modern_sizes = structured_data.get("modern_sizes", {})

            # Get product highlight from raw data
            product_highlight = structured_data.get("ProductHighlight", None)

            return {
                "ModernSizes": modern_sizes,  # NEW: Include modern sizes
                "ProductHighlight": product_highlight
            }

        except Exception as e:
            logger.error(f"Error transforming to modern format: {e}")
            return {"AvailableSizes": [], "ModernSizes": {}, "ProductHighlight": None}

    def _convert_modern_to_legacy_sizes(self, modern_sizes: Dict[str, Dict]) -> List[Dict]:
        """Convert modern size format to legacy format for backward compatibility."""
        legacy_sizes = []
        for sku, size_info in modern_sizes.items():
            legacy_sizes.append({
                "Size": size_info.get("size_label", ""),
                "Availability": size_info.get("notes", ""),
                "Price": None,
                "SKU": sku
            })
        return legacy_sizes
