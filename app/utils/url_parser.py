import re
from typing import Tuple, Optional
from urllib.parse import urlparse


class ZalandoURLParser:
    """Parser for Zalando product URLs"""

    @staticmethod
    def extract_product_code(url: str) -> Optional[str]:
        """
        Extract product code from Zalando URL
        Pattern: /productname-productcode.html
        Example: /acdc-calze-mehrfarbig-a9182f001-t11.html → A9182F001-T11
        """
        # Match the product code pattern (letters, numbers, hyphens before .html)
        pattern = r'-([a-zA-Z0-9]+-[a-zA-Z0-9]+)\.html$'
        match = re.search(pattern, url)

        if match:
            return match.group(1).upper()
        return None

    @staticmethod
    def extract_domain_info(url: str) -> Tuple[str, str]:
        """
        Extract domain and language from URL
        Returns: (domain, language_code)
        """
        parsed = urlparse(url)
        domain = parsed.netloc.replace('www.', '')

        # I found that the language doesn't matter
        language = "en-US"  # Default

        return domain, language

    @staticmethod
    def is_valid_zalando_url(url: str) -> bool:
        """Validate if URL is a proper Zalando product URL"""
        if not url.startswith(('http://', 'https://')):
            return False

        # Check if it's a zalando domain
        parsed = urlparse(url)
        domain = parsed.netloc.replace('www.', '')

        if not any(zalando_domain in domain for zalando_domain in [
            'zalando.de', 'zalando.it', 'zalando.fr', 'zalando.es',
            'zalando.nl', 'zalando.pl', 'zalando.co.uk', 'zalando.com'
        ]):
            return False

        product_code = ZalandoURLParser.extract_product_code(url)
        return product_code is not None
