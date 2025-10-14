import json
import re
import os
import logging
from datetime import datetime
from typing import Dict, List, Any
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy

logger = logging.getLogger(__name__)


class FallbackJsonCssExtractionStrategy(JsonCssExtractionStrategy):
    """Custom extraction strategy with fallback selectors and default values."""

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


class ZalandoCrawl4AIScraper:
    """Main scraper class for Zalando product pages using Crawl4AI."""

    # Extraction schema for Zalando product pages
    SCHEMA = {
        "name": "Zalando Product",
        "baseSelector": "body",
        "fields": [
            {
                "name": "page_title",
                "selector": "title",
                "type": "text"
            },
            {
                "name": "product_name",
                "selector": [
                    "[data-testid='product-name']",
                    "h1[data-id='productTitle']",
                    "h1._1PY2_7",
                    "h1._0xLoFW",
                    "h1"
                ],
                "type": "text"
            },
            {
                "name": "product_brand",
                "selector": [
                    "[data-testid='brand-link']",
                    "a[data-testid='brand-link']",
                    "a[title*='Brand']",
                    "a._0xLoFW"
                ],
                "type": "text"
            },
            {
                "name": "product_price",
                "selector": [
                    "[data-testid='price-amount']",
                    "span._0xLoFW._7CKbLS",
                    ".price",
                    "span[data-id='price']"
                ],
                "type": "text"
            },
            {
                "name": "sizes_container",
                "selector": [
                    "[data-testid='sizes-container']",
                    ".size-selector",
                    "div[data-id='sizes']",
                    "div.MU8FaS"
                ],
                "type": "html"
            },
            {
                "name": "all_size_buttons",
                "selector": [
                    "button[data-testid='size-picker-trigger']",
                    ".size-picker-trigger",
                    "#picker-trigger",
                    "button[data-id='size-select']"
                ],
                "type": "text",
                "multiple": True
            },
            {
                "name": "size_options",
                "selector": [
                    "div[data-testid='size-options']",
                    ".size-options",
                    "div[role='listbox']",
                    "div[data-id='size-list']"
                ],
                "type": "html"
            },
            {
                "name": "available_sizes",
                "selector": [
                    "button[data-testid='size-option']:not([disabled])",
                    ".size-option:not(.disabled)",
                    "div[data-id='size-available']",
                    "button:not([disabled])"
                ],
                "type": "text",
                "multiple": True
            },
            {
                "name": "product_description",
                "selector": [
                    "[data-testid='product-description']",
                    ".product-description",
                    "div._0xLoFW._78xIQ-"
                ],
                "type": "text"
            },
            {
                "name": "all_scripts",
                "selector": "script",
                "type": "html",
                "multiple": True
            },
            {
                "name": "json_ld_data",
                "selector": "script[type='application/ld+json']",
                "type": "html"
            },
            {
                "name": "ProductHighlight",
                "selector": "div._ZDS_REF_SCOPE_.tyCFc1._4VHUP_._0xLoFW.P3OKTW.EJ4MLB._7ckuOK.Ij3QKg.abTEo1.hD5J5m > div > div > span",
                "type": "text"
            }
        ]
    }

    # JavaScript commands to interact with the size selector
    JS_COMMANDS = [
        "try { document.querySelector('#picker-trigger')?.click(); } catch(e) {}",
        "try { document.querySelector('[data-testid=\"size-picker-trigger\"]')?.click(); } catch(e) {}",
        "try { document.querySelector('button[data-id=\"size-select\"]')?.click(); } catch(e) {}",
        "await new Promise(resolve => setTimeout(resolve, 800));",
        "window.scrollTo(0, 300);",
        "await new Promise(resolve => setTimeout(resolve, 400));",
    ]

    def __init__(self):
        self.extraction_strategy = FallbackJsonCssExtractionStrategy(self.SCHEMA)

    @staticmethod
    def extract_product_code(url: str) -> str:
        """Extract product code from Zalando URL."""
        patterns = [
            r'([A-Z0-9]+-[A-Z0-9]+)\.html',
            r'/([A-Z0-9]+-[A-Z0-9]+)-',
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        return url.split('/')[-1].replace('.html', '')

    @staticmethod
    def extract_json_ld_structured_data(json_ld_html: str) -> Dict[str, Any]:
        """Extract and structure data from JSON-LD script."""
        if not json_ld_html:
            return {}

        try:
            clean_script = re.sub(r'<\/?script[^>]*>', '', json_ld_html)
            json_data = json.loads(clean_script)

            structured_data = {
                "product_info": {},
                "pricing": {},
                "availability": {},
                "skus": []
            }

            # Basic product information
            if 'name' in json_data:
                structured_data["product_info"]["name"] = json_data['name']
            if 'brand' in json_data:
                if isinstance(json_data['brand'], dict):
                    structured_data["product_info"]["brand"] = json_data['brand'].get('name')
                else:
                    structured_data["product_info"]["brand"] = json_data['brand']
            if 'description' in json_data:
                structured_data["product_info"]["description"] = json_data['description'].strip()
            if 'color' in json_data:
                structured_data["product_info"]["color"] = json_data['color']
            if 'sku' in json_data:
                structured_data["product_info"]["main_sku"] = json_data['sku']

            # Offers and prices
            if 'offers' in json_data and isinstance(json_data['offers'], list):
                offers = json_data['offers']

                if len(offers) > 0:
                    first_offer = offers[0]
                    structured_data["pricing"]["price"] = first_offer.get('price')
                    structured_data["pricing"]["currency"] = first_offer.get('priceCurrency')

                # Extract all SKUs
                for offer in offers:
                    sku_data = {
                        "sku": offer.get('sku'),
                        "price": offer.get('price'),
                        "currency": offer.get('priceCurrency'),
                        "availability": offer.get('availability', '').replace('http://schema.org/', ''),
                        "url": offer.get('url')
                    }
                    structured_data["skus"].append(sku_data)

                # Calculate availability statistics
                available_skus = [sku for sku in structured_data["skus"] if sku["availability"] == "InStock"]
                out_of_stock_skus = [sku for sku in structured_data["skus"] if sku["availability"] == "OutOfStock"]

                structured_data["availability"]["total_skus"] = len(structured_data["skus"])
                structured_data["availability"]["available_skus"] = len(available_skus)
                structured_data["availability"]["out_of_stock_skus"] = len(out_of_stock_skus)
                structured_data["availability"][
                    "availability_rate"] = f"{(len(available_skus) / len(structured_data['skus']) * 100):.1f}%" if \
                    structured_data["skus"] else "0%"

            return structured_data

        except Exception as e:
            logger.error(f"JSON-LD parsing error: {str(e)}")
            return {"error": f"JSON-LD parsing error: {str(e)}"}

    @staticmethod
    def extract_detailed_skus(html_content: str) -> Dict[str, Dict[str, Any]]:
        """Extract SKU details from HTML container in modern format."""
        if not html_content:
            return {}

        result = {}
        blocks = re.findall(
            r'<input[^>]+id="size-picker-([^"]+)"[^>]*>\s*<div[^>]*>\s*<label[^>]*>([\s\S]*?)</label>',
            html_content, re.DOTALL
        )

        for sku, label_html in blocks:
            # Extract size label
            size_match = re.search(
                r'<span class="[^\"]*voFjEy[^\"]*SbJZ75[^\"]*Sb5G3D[^\"]*HlZ_Tf[^\"]*">([^<]+)</span>',
                label_html
            )
            if not size_match:
                size_match = re.search(
                    r'<span class="[^\"]*voFjEy[^\"]*SbJZ75[^\"]*Sb5G3D[^\"]*Yb63TQ[^\"]*">([^<]+)</span>',
                    label_html
                )
            if not size_match:
                generic_matches = re.findall(
                    r'<span class="[^\"]*voFjEy[^\"]*SbJZ75[^\"]*Sb5G3D[^\"]*[^\"]*">([^<]+)</span>',
                    label_html
                )
                for gm in generic_matches:
                    if "€" not in gm:
                        size_match = re.match(r'.*', gm)
                        break

            size_label = size_match.group(1).strip() if size_match else ""

            # Extract notes
            note = ""
            note_candidates = re.findall(r'<div class="nXkCf3">\s*<span[^>]*>([^<]+)</span>', label_html)
            if note_candidates:
                for n in note_candidates:
                    n_clean = n.strip()
                    if n_clean and "€" not in n_clean:
                        if n_clean == size_label or re.match(r'^\d+(?:\s\d/\d)?$', n_clean):
                            continue
                        note = n_clean
                        break

            if not note:
                alt = re.findall(r'class="[^\"]*HlZ_Tf[^\"]*"[^>]*>([^<]+)<', label_html)
                for n in alt:
                    n_clean = n.strip()
                    if n_clean and "€" not in n_clean:
                        if n_clean == size_label or re.match(r'^\d+(?:\s\d/\d)?$', n_clean):
                            continue
                        note = n_clean
                        break

            availability = "OutOfStock" if "Esaurito" in note else "InStock"

            # Extract quantity for available_Qnty field
            qty = None
            patterns = [
                r'(\d+)\s*articolo', r'Articoli\s+disponibili\s*:\s*(\d+)',
                r'(\d+)\s*articoli', r'(\d+)\s*pezzi',
                r'(?:solo\s*)?(\d+)\s*(?:pz|pezzo|pezzi)'
            ]
            for p in patterns:
                m = re.search(p, note)
                if m:
                    qty = int(m.group(1))
                    break

            is_long_distance = "true" if "lunga distanza" in note.lower() else "false"

            # Clean up note if it's only long distance message
            if is_long_distance == "true" and not re.search(r"articolo|articoli|Esaurito", note, re.IGNORECASE):
                note = ""

            # Determine available_Qnty value
            if availability == "OutOfStock":
                available_qnty_str = "0"
            else:
                available_qnty_str = "+2"  # Default for available items without specific quantity
                if qty is not None:
                    available_qnty_str = str(qty)
                elif "1 articolo disponibile" in note:
                    available_qnty_str = "1"
                elif "articoli disponibili" in note and qty is None:
                    # If we have the phrase but couldn't extract number, use default
                    available_qnty_str = "+2"

            # NEW: Use modern format without available_qnty field
            result[sku] = {
                "size_label": size_label,
                "notes": note,
                "available_Qnty": available_qnty_str,  # Keep this as it's in the desired format
                "availability": availability,
                "long_distance": is_long_distance
            }

        return result

    def _enrich_modern_sizes_with_prices(self, modern_sizes: Dict[str, Dict], json_ld_skus: List[Dict]) -> Dict[
        str, Dict]:
        """Enrich modern sizes with price information from JSON-LD data."""
        enriched_sizes = modern_sizes.copy()

        # Create a lookup dictionary for SKU prices
        sku_price_lookup = {}
        for sku_data in json_ld_skus:
            sku_id = sku_data.get('sku')
            price = sku_data.get('price')
            if sku_id and price:
                sku_price_lookup[sku_id] = str(price)  # Convert to string for consistency

        # Add prices to modern sizes
        for sku_id, size_info in enriched_sizes.items():
            if size_info['availability'] == "OutOfStock":
                size_info["price"] = 0
                continue
            if sku_id in sku_price_lookup:
                size_info["price"] = sku_price_lookup[sku_id]
            else:
                # If no specific price found for this SKU, try to find any price from JSON-LD
                if json_ld_skus and len(json_ld_skus) > 0:
                    size_info["price"] = str(json_ld_skus[0].get('price', ''))
                else:
                    size_info["price"] = ""

        return enriched_sizes

    async def scrape_product_page(self, url: str) -> Dict[str, Any]:
        """
        Main method to scrape and process Zalando product page.

        Args:
            url: Zalando product page URL

        Returns:
            Dictionary containing extracted data and metadata
        """
        logger.info(f"Scraping product page: {url}")

        async with AsyncWebCrawler() as crawler:
            result = await crawler.arun(
                url=url,
                config=CrawlerRunConfig(
                    cache_mode=CacheMode.BYPASS,
                    extraction_strategy=self.extraction_strategy,
                    js_code=self.JS_COMMANDS,
                    scan_full_page=True,
                    magic=True,
                    wait_for="css:body",
                    wait_for_timeout=10000,
                    page_timeout=30000,
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
            )

        # Process extracted data
        extracted_data = {}
        json_ld_structured = {}
        detailed_skus_from_html = {}

        if result.success:
            try:
                data = json.loads(result.extracted_content)
                if data and data[0]:
                    extracted_data = data[0]

                    # Extract structured data from JSON-LD
                    if extracted_data.get('json_ld_data'):
                        json_ld_structured = self.extract_json_ld_structured_data(
                            extracted_data['json_ld_data']
                        )

                    # Extract SKU details from HTML in modern format
                    if extracted_data.get('sizes_container'):
                        detailed_skus_from_html = self.extract_detailed_skus(
                            extracted_data['sizes_container']
                        )

                    # NEW: Enrich modern sizes with price information
                    if detailed_skus_from_html and json_ld_structured.get('skus'):
                        detailed_skus_from_html = self._enrich_modern_sizes_with_prices(
                            detailed_skus_from_html,
                            json_ld_structured['skus']
                        )

                    # Save debug data
                    # self._save_debug_data(extracted_data, result)

            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {e}")
                extracted_data = {"error": f"JSON decode error: {str(e)}"}

        return {
            "success": result.success,
            "html_length": len(result.html) if result.html else 0,
            "raw_extracted_data": extracted_data,
            "structured_data": {
                "json_ld": json_ld_structured,
                "modern_sizes": detailed_skus_from_html,  # NEW: renamed to modern_sizes
                "ProductHighlight": extracted_data.get("ProductHighlight", None)
            }
        }

    def _save_debug_data(self, extracted_data: Dict[str, Any], result) -> None:
        """Save debug data to file for troubleshooting."""
        try:
            if not os.path.exists('complete_data'):
                os.makedirs('complete_data')

            with open('zalando_full_debug.json', 'w', encoding='utf-8') as f:
                debug_data = {
                    'extracted_content': extracted_data,
                    'html_length': len(result.html) if result.html else 0,
                    'success': result.success
                }
                json.dump(debug_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"Could not save debug data: {e}")

    def save_complete_data(self, result_data: Dict[str, Any], product_code: str) -> str:
        """Save complete extracted data in JSON format with modern size format."""
        if not os.path.exists('complete_data'):
            os.makedirs('complete_data')

        date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"complete_data/{product_code}_{date_str}.json"

        json_ld = result_data["structured_data"]["json_ld"]
        modern_sizes = result_data["structured_data"].get("modern_sizes", {})

        # NEW: Create final data with modern format
        final_data = {
            "extracted_content": result_data.get("raw_extracted_data", {}),
            "html_length": result_data.get("html_length", 0),
            "success": result_data.get("success", False),
            "modern_sizes": modern_sizes,  # NEW: Include modern sizes directly
            "skus": self._create_legacy_skus_for_compatibility(json_ld, modern_sizes)  # Keep for backward compatibility
        }

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(final_data, f, indent=2, ensure_ascii=False)

        logger.info(f"Complete data saved in: {filename}")
        return filename

    def _create_legacy_skus_for_compatibility(self, json_ld: Dict, modern_sizes: Dict) -> List[Dict]:
        """Create legacy SKU format for backward compatibility."""
        skus_out = []
        for offer in json_ld.get("skus", []):
            sku_id = offer.get("sku")
            modern_size = modern_sizes.get(sku_id, {})

            item = {
                "sku": sku_id,
                "size_lable": modern_size.get("size_label", ""),  # Note: typo preserved
                "price": modern_size.get("price", str(offer.get("price", ""))),
                # Use price from modern_sizes if available
                "currency": offer.get("currency"),
                "availability": modern_size.get("availability", ""),
                "available_qnty": modern_size.get("available_Qnty", "+2"),
                "notes": modern_size.get("notes", ""),
                "long_distance": modern_size.get("long_distance", "false")
            }
            skus_out.append(item)
        return skus_out


