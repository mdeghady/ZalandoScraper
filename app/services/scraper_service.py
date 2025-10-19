import asyncio
from typing import Optional, Dict
from app.models.schemas import (
    ProductData, SkuData, CrawlData, APIProductResponse,
    ScrapeResponse, ModernSizeInfo
)
from app.utils.url_parser import ZalandoURLParser
from app.utils.html_parser import extract_merchant_data , extract_stock_data
from app.services.api_scraper import ZalandoAPIScraper
from app.services.crawl_scraper import Crawl4AIScraper
from app.services.crawl_scraper import ZalandoCrawl4AIScraper

import time


class ZalandoScraperService:
    """Main service that orchestrates both scrapers."""

    def __init__(self):
        self.api_scraper = ZalandoAPIScraper()
        self.crawl_scraper = Crawl4AIScraper()
        self.url_parser = ZalandoURLParser()
        self.refactored_scraper = ZalandoCrawl4AIScraper()

    async def scrape_product(self, url: str) -> ScrapeResponse:
        """Main method to scrape product data from both sources."""
        try:
            # Validate URL
            if not self.url_parser.is_valid_zalando_url(url):
                return ScrapeResponse(
                    success=False,
                    error="Invalid Zalando product URL"
                )

            # Extract product info
            product_code = self.url_parser.extract_product_code(url)
            domain, language = self.url_parser.extract_domain_info(url)

            if not product_code:
                return ScrapeResponse(
                    success=False,
                    error="Could not extract product code from URL"
                )

            # Run both scrapers concurrently
            api_task = asyncio.to_thread(
                self._fetch_api_data, product_code
            )
            crawl_task = self.crawl_scraper.scrape_product_page(url)
            fetch_html_task = asyncio.to_thread(
                self.fetch_html_page_data, url
            )

            api_result, crawl_result , html_result= await asyncio.gather(
                api_task, crawl_task, fetch_html_task, return_exceptions=True
            )

            # Handle exceptions
            if isinstance(api_result, Exception):
                return ScrapeResponse(
                    success=False,
                    error=f"API scraper error: {str(api_result)}"
                )

            if isinstance(crawl_result, Exception):
                return ScrapeResponse(
                    success=False,
                    error=f"Crawler error: {str(crawl_result)}"
                )

            if isinstance(html_result, Exception):
                return ScrapeResponse(
                    success=False,
                    error=f"Crawler error: {str(html_result)}"
                )

            product_data, sku_data = api_result
            crawl_data = crawl_result
            html_data = html_result

            # Merge and normalize data
            merged_response = self._merge_responses(
                product_data, sku_data, crawl_data, html_data, url
            )

            return ScrapeResponse(
                success=True,
                data=merged_response,
                metadata={
                    "product_code": product_code,
                    "domain": domain,
                    "language": language,
                    "sources_used": {
                        "api": product_data is not None,
                        "crawl": crawl_data is not None
                    }
                }
            )

        except Exception as e:
            return ScrapeResponse(
                success=False,
                error=f"Unexpected error: {str(e)}"
            )

    async def scrape_product_advanced(self, url: str) -> Dict:
        """Advanced scraping using the refactored crawler directly."""
        try:
            result = await self.refactored_scraper.scrape_product_page(url)

            if result["success"]:
                # Save complete data
                product_code = self.refactored_scraper.extract_product_code(url)
                # filename = self.refactored_scraper.save_complete_data(result, product_code)
                result["saved_filename"] = None

            return result

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _fetch_api_data(self, product_code: str):
        """Fetch data from API scraper (runs in thread)."""
        # ... existing implementation unchanged ...
        product_data = self.api_scraper.fetch_product_by_id(product_code)[0]
        sku_data = self.api_scraper.fetch_product_sku(product_code)[0]

        # Parse API responses
        parsed_product = None
        parsed_sku = None

        # Assign sku data to the sku model
        if sku_data and 'data' in sku_data:
            sku_node = sku_data['data']['product']
            gtin = None
            if sku_node.get('simples') and len(sku_node['simples']) > 0:
                gtin = sku_node['simples'][0].get('gtins', [None])[0]

            parsed_sku = SkuData(
                sku=sku_node['sku'],
                model_number=sku_node.get('modelNumber'),
                gtin=gtin,
                simples=sku_node.get('simples', [])
            )

        # Assign the product data to the product model
        if product_data and 'data' in product_data:
            # product_node = product_data['data']['product']['family']['products']['edges'][0]['node']
            # Choose the right variant according to the sku
            product_node = product_data.get('data',{}).get('product',{})  #['family']['products']['edges']
            if product_node :
                parsed_product = ProductData(
                    id=product_node['id'],
                    name=product_node['name'],
                    sku=product_node['sku'],
                    model_number=sku_node.get('modelNumber'),
                    gtin=gtin,
                    brand=product_node['brand']['name'],
                    display_price=product_node['displayPrice'],
                    productFlags = product_node.get('productFlags', []),
                    packshot_image=product_node.get('packshotImage', {}).get('uri'),
                    silhouette=product_node.get('silhouette'),
                    navigation_target_group=product_node.get('navigationTargetGroup'),
                    simples=sku_node.get('simples', [])
                )
                # Calculating & Adding Tracking Discount Percentage with 2 decimals
                current_price = parsed_product.display_price.get('trackingCurrentAmount')
                discount_amount = parsed_product.display_price.get('trackingDiscountAmount')

                if current_price is not None and discount_amount is not None:
                    parsed_product.display_price['trackingDiscountPercentage'] = \
                        round(discount_amount / (current_price + discount_amount) , 2) if current_price > 0 else 0
                else:
                    parsed_product.display_price['trackingDiscountPercentage'] = 0.0


            # Some of the prices are multiplied by 100
            for price_key in parsed_product.display_price:
                price_value = parsed_product.display_price[price_key]
                if isinstance(price_value, dict):
                    if 'amount' in price_value.keys():
                        try:
                            price_value['amount'] = price_value['amount'] / 100
                        except Exception as _:
                            continue

        return parsed_product, parsed_sku

    def fetch_html_page_data(self, url: str) -> Optional[Dict]:
        """Fetch raw HTML and extract merchant & shipping data."""
        try:
            html_content = self.api_scraper.fetch_product_page_html(url)
            product_code = self.url_parser.extract_product_code(url)
            merchant_data = extract_merchant_data(html_content, product_code)
            stock_data = extract_stock_data(html_content , product_code)
            return merchant_data , stock_data
        except Exception:
            return Exception("Failed to fetch or parse HTML page.")


    # def _merge_responses(self, product_data: Optional[ProductData],
    #                      sku_data: Optional[SkuData],
    #                      crawl_data: Optional[Dict],
    #                      url: str) -> APIProductResponse:
    #     """Merge and normalize data from all sources."""
    #     # Parse crawl data with modern format
    #     parsed_crawl = None
    #     if crawl_data:
    #         # Convert modern sizes to Pydantic models
    #         modern_sizes_dict = {}
    #         modern_sizes_raw = crawl_data.get('ModernSizes', {})
    #
    #         for sku, size_info in modern_sizes_raw.items():
    #             modern_sizes_dict[sku] = ModernSizeInfo(
    #                 size_label=size_info.get('size_label', ''),
    #                 notes=size_info.get('notes', ''),
    #                 availability=size_info.get('availability', 'InStock'),
    #                 long_distance=size_info.get('long_distance', 'false')
    #             )
    #
    #         # Keep legacy sizes for backward compatibility
    #         normalized_legacy_sizes = self.crawl_scraper._normalize_size_data(
    #             crawl_data.get('AvailableSizes', [])
    #         )
    #
    #         parsed_crawl = CrawlData(
    #             available_sizes=normalized_legacy_sizes,
    #             modern_sizes=modern_sizes_dict,  # NEW: Include modern sizes
    #             product_highlight=crawl_data.get('ProductHighlight'),
    #             url=url
    #         )
    #
    #     return APIProductResponse(
    #         product_data=product_data,
    #         sku_data=sku_data,
    #         crawl_data=parsed_crawl,
    #         metadata={
    #             "merged_at": "2024-01-01T00:00:00Z",  # Use actual timestamp
    #             "data_sources": ["api", "crawl"] if product_data and crawl_data else
    #             ["api"] if product_data else
    #             ["crawl"] if crawl_data else []
    #         }
    #     )
    def _merge_responses(self, product_data: Optional[ProductData],
                        sku_data: Optional[SkuData],
                        crawl_data: Optional[Dict],
                        html_data: tuple[Optional[Dict] , Optional[Dict]],
                        url: str) -> APIProductResponse:
        """
        Merge and normalize data from all sources.
        and merge the sizes info from the crawled
        data into the product data sizes (simples) list.
        """
        # Create a mapping of SKU to SizeInfo from crawl data
        sku_to_sizeinfo = {crawled_sku : crawled_info for crawled_sku, crawled_info in
                           crawl_data.get('ModernSizes', {}).items()} if crawl_data else {}

        # Dive into product_data to find the simples list
        if product_data and product_data.simples:
            for simple in product_data.simples:
                sku = simple.get('sku')
                if sku and sku in sku_to_sizeinfo:
                    size_info = sku_to_sizeinfo[sku]
                    # Merge the gtin and merchant id from simple if available
                    size_info.update({
                        'gtin': simple.get('gtins', [None])[0],
                        'merchant_id': simple.get('offer' , {}).get('merchant', {}).get('id'),
                        'sku' : sku
                    })

        # Replace the simples list with the enriched size info
        if len (sku_to_sizeinfo) > 0:
            product_data.simples = list(sku_to_sizeinfo.values())
        else:
            available_qnty = html_data[1]
            # One size products
            product_data.simples = [{
                'size_label': "One Size",
                'notes': "",
                "available_Qnty" : available_qnty.get('stock' , ""),
                'availability': "InStock",
                'long_distance': "false",
                'price' : product_data.display_price.get('trackingCurrentAmount', ""),
                'gtin': product_data.gtin,
                'merchant_id': None,
                'sku': available_qnty.get('sku', ""),
            }]

        # A dd product highlight if available to product data
        if product_data and crawl_data and 'ProductHighlight' in crawl_data:
            product_data.product_highlight = crawl_data['ProductHighlight']

        parsed_crawl = None
        if crawl_data:
            # Convert modern sizes to Pydantic models
            modern_sizes_dict = {}
            modern_sizes_raw = crawl_data.get('ModernSizes', {})

            for sku, size_info in modern_sizes_raw.items():
                modern_sizes_dict[sku] = ModernSizeInfo(
                    sku=sku,
                    size_label=size_info.get('size_label', ''),
                    notes=size_info.get('notes', ''),
                    availability=size_info.get('availability', 'InStock'),
                    long_distance=size_info.get('long_distance', 'false')
                )

            # Keep legacy sizes for backward compatibility
            normalized_legacy_sizes = self.crawl_scraper._normalize_size_data(
                crawl_data.get('AvailableSizes', [])
            )

            parsed_crawl = CrawlData(
                available_sizes=normalized_legacy_sizes,
                modern_sizes=modern_sizes_dict,  # NEW: Include modern sizes
                product_highlight=crawl_data.get('ProductHighlight'),
                url=url
            )

            html_merchant_data = html_data[0]
        # Add merchant data from HTML parsing to the simples data
            for simple in product_data.simples:
                sku = simple.get('sku')
                if sku and html_merchant_data:
                    merchant_data = html_merchant_data[sku]
                    simple['merchant'] = merchant_data.get('merchant')
                    simple['shipper'] = merchant_data.get('shipper')
        data_sources = []
        if product_data:
            data_sources.append("api")
        if crawl_data:
            data_sources.append("crawl")
        if html_data:
            data_sources.append("html")

        return APIProductResponse(
            product_data=product_data,
            sku_data=sku_data,
            crawl_data=parsed_crawl,
            metadata={
                "merged_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.localtime()),
                "data_sources": data_sources
            }
        )
