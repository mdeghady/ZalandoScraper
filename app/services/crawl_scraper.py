import json
import re
from typing import List, Dict, Optional
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy
from app.models.schemas import SizeInfo, AvailabilityStatus


class FallbackJsonCssExtractionStrategy(JsonCssExtractionStrategy):
    """Custom extraction strategy with fallback values"""

    def _extract_single_field(self, element, field):
        if "selector" in field:
            if isinstance(field["selector"], list) and len(field["selector"]) > 0:
                for field_selector in field["selector"]:
                    selected = self._get_elements(element, field_selector)
                    if selected:
                        break
            else:
                selected = self._get_elements(element, field["selector"])
            if not selected:
                return field.get("default")
            selected = selected[0]
        else:
            selected = element

        value = None
        if field["type"] == "text":
            value = self._get_element_text(selected)
        elif field["type"] == "attribute":
            value = self._get_element_attribute(selected, field["attribute"])
        elif field["type"] == "html":
            value = self._get_element_html(selected)
        elif field["type"] == "regex":
            text = self._get_element_text(selected)
            match = re.search(field["pattern"], text)
            value = match.group(1) if match else None

        if "transform" in field:
            value = self._apply_transform(value, field["transform"])

        return value if value is not None else field.get("default")


class Crawl4AIScraper:
    """Wrapper around the existing scraper.py functionality"""

    def __init__(self):
        self.schema = {
            "name": "ProductPage",
            "baseSelector": "body",
            "fields": [
                {
                    "name": "AvailableSizes",
                    "selector": "div.MU8FaS._0xLoFW._8sTSoF.parent._78xIQ- div",
                    "type": "nested_list",
                    "fields": [
                        {"name": "Size", "selector": "label span div span", "type": "text"},
                        {"name": "Price", "selector": "div label span div div p span", "type": "text"},
                        {"name": "Availability", "selector": "div label div.nXkCf3 span", "type": "text"}
                    ]
                },
                {
                    "name": "ProductHighlight",
                    "selector": "div._ZDS_REF_SCOPE_.tyCFc1._4VHUP_._0xLoFW.P3OKTW.EJ4MLB._7ckuOK.Ij3QKg.abTEo1.hD5J5m > div > div > span",
                    "type": "text"
                }
            ]
        }

    def _normalize_size_data(self, raw_sizes: List[Dict]) -> List[SizeInfo]:
        """Clean and normalize size data from crawler"""
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
        """Scrape product page using Crawl4AI"""
        try:
            js_commands = [
                "document.querySelector('#picker-trigger')?.click()"
            ]

            async with AsyncWebCrawler() as crawler:
                result = await crawler.arun(
                    url=url,
                    config=CrawlerRunConfig(
                        cache_mode=CacheMode.BYPASS,
                        extraction_strategy=FallbackJsonCssExtractionStrategy(self.schema),
                        js_code=js_commands,
                        scan_full_page=True,
                        magic=True,
                        wait_for="css:body"
                    )
                )

            if result.extracted_content:
                data = json.loads(result.extracted_content)
                if data and len(data) > 0:
                    return data[0]
            print("extracted_content data")
            print(result.extracted_content)

            return None

        except Exception as e:
            print(f"Crawler error: {e}")
            return None

