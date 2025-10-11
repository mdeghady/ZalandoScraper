import asyncio
from typing import Optional , Dict
from app.models.schemas import (
    ProductData, SkuData, CrawlData, APIProductResponse,
    ScrapeResponse, AvailabilityStatus
)
from app.utils.url_parser import ZalandoURLParser
from app.services.api_scraper import ZalandoAPIScraper
from app.services.crawl_scraper import Crawl4AIScraper


class ZalandoScraperService:
    """Main service that orchestrates both scrapers"""

    def __init__(self):
        self.api_scraper = ZalandoAPIScraper()
        self.crawl_scraper = Crawl4AIScraper()
        self.url_parser = ZalandoURLParser()

    async def scrape_product(self, url: str) -> ScrapeResponse:
        """Main method to scrape product data from both sources"""
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

            api_result, crawl_result = await asyncio.gather(
                api_task, crawl_task, return_exceptions=True
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

            product_data, sku_data = api_result
            crawl_data = crawl_result

            # Merge and normalize data
            merged_response = self._merge_responses(
                product_data, sku_data, crawl_data, url
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

    def _fetch_api_data(self, product_code: str):
        """Fetch data from API scraper (runs in thread)"""
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
            product_node = product_data['data']['product']['family']['products']['edges'][0]['node']
            parsed_product = ProductData(
                id=product_node['id'],
                name=product_node['name'],
                sku=product_node['sku'],
                model_number=sku_node.get('modelNumber'),
                gtin=gtin,
                brand=product_node['brand']['name'],
                display_price=product_node['displayPrice'],
                packshot_image=product_node.get('packshotImage', {}).get('uri'),
                silhouette=product_node.get('silhouette'),
                navigation_target_group=product_node.get('navigationTargetGroup'),
                simples=sku_node.get('simples', [])
            )

            # Some of the prices are multiplied by 100
            for price_key in parsed_product.display_price:
                price_value = parsed_product.display_price[price_key]
                if isinstance(price_value , dict):
                    if 'amount' in price_value.keys():
                        try:
                            price_value['amount'] =  price_value['amount'] / 100
                        except Exception as _:
                            continue


        return parsed_product, parsed_sku

    def _merge_responses(self, product_data: Optional[ProductData],
                         sku_data: Optional[SkuData],
                         crawl_data: Optional[Dict],
                         url: str) -> APIProductResponse:
        """Merge and normalize data from all sources"""
        # Parse crawl data
        parsed_crawl = None
        if crawl_data:
            normalized_sizes = self.crawl_scraper._normalize_size_data(
                crawl_data.get('AvailableSizes', [])
            )

            parsed_crawl = CrawlData(
                available_sizes=normalized_sizes,
                product_highlight=crawl_data.get('ProductHighlight'),
                url=url
            )

        return APIProductResponse(
            product_data=product_data,
            sku_data=sku_data,
            crawl_data=parsed_crawl,
            metadata={
                "merged_at": "2024-01-01T00:00:00Z",  # Use actual timestamp
                "data_sources": ["api", "crawl"] if product_data and crawl_data else
                ["api"] if product_data else
                ["crawl"] if crawl_data else []
            }
        )