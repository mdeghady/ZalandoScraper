import requests
import json
import time
from typing import Dict, Optional
from app.utils.url_parser import ZalandoURLParser



class ZalandoAPIScraper:
    """Handles authenticated API calls to Zalando's GraphQL endpoints (multi-domain support)."""

    def __init__(self, base_domain: str = "zalando.it"):
        """
        Initialize the client with a default domain.
        """
        self.base_domain = base_domain
        self.session = requests.Session()
        self._configure_session()
        self._last_cookie_refresh = 0

    # ------------------- SESSION MANAGEMENT -------------------
    def _configure_session(self):
        """Set up headers and base session parameters."""
        self.session.headers.update({
            'accept': '*/*',
            'accept-language': 'en-US,en;q=0.9,ar;q=0.8',
            'user-agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/137.0.0.0 Safari/537.36'
            ),
            'x-frontend-type': 'browser',
            'x-zalando-feature': 'pdp',
            'x-zalando-intent-context': 'navigationTargetGroup=MEN'
        })

    def _get_base_url(self) -> str:
        """Return GraphQL endpoint for current domain."""
        return f"https://www.{self.base_domain}/api/graphql/"

    def _get_homepage_url(self) -> str:
        """Return homepage for current domain."""
        return f"https://www.{self.base_domain}/"

    def _ensure_cookies(self):
        """Ensure we have recent cookies (refresh every 5 minutes)."""
        if time.time() - self._last_cookie_refresh < 300:
            return
        homepage_url = self._get_homepage_url()
        self.session.get(homepage_url, timeout=10)
        self._last_cookie_refresh = time.time()

    def _get_xsrf_token(self) -> Optional[str]:
        """Extract XSRF token from cookies."""
        token = self.session.cookies.get("frsx")
        if token:
            return token
        for c in self.session.cookies:
            if "frsx" in c.name.lower():
                return c.value
        return None

    # ------------------- API REQUEST -------------------
    def _post_graphql(self, payload: dict, retries: int = 2) -> Dict:
        """Send POST request to Zalando GraphQL with retry logic."""
        for attempt in range(retries + 1):
            try:
                self._ensure_cookies()
                headers = {'content-type': 'application/json', 'viewport-width': '1016'}

                xsrf_token = self._get_xsrf_token()
                if xsrf_token:
                    headers['x-xsrf-token'] = xsrf_token

                response = self.session.post(
                    self._get_base_url(), headers=headers,
                    data=json.dumps([payload]), timeout=15
                )

                if response.status_code == 200:
                    return response.json()
                elif response.status_code in [401, 403]:
                    print(f"Auth error {response.status_code}, refreshing session...")
                    self._last_cookie_refresh = 0
                    continue
                else:
                    print(f"Attempt {attempt+1} failed ({response.status_code})")
                    time.sleep(2 ** attempt)

            except requests.exceptions.RequestException as e:
                if attempt < retries:
                    print(f"Retry {attempt+1}: {e}")
                    time.sleep(2 ** attempt)
                    continue
                raise

        raise Exception("All retries failed when calling Zalando API.")

    # ------------------- PUBLIC METHODS -------------------
    def fetch_product_by_url(self, url: str) -> Dict:
        """Fetch product data directly from a Zalando product URL."""
        if not ZalandoURLParser.is_valid_zalando_url(url):
            raise ValueError(f"Invalid Zalando product URL: {url}")

        # Extract product code and domain dynamically
        product_code = ZalandoURLParser.extract_product_code(url)
        domain, _ = ZalandoURLParser.extract_domain_info(url)
        self.base_domain = domain  # 🔁 dynamically update client domain

        return self.fetch_product_by_id(product_code)

    def fetch_product_by_id(self, product_id: str) -> Dict:
        payload = {
            "id": "4d1d108a1b774122d02d46a47ffc05819b083570192b52c0c609813cb59f26fe",
            "variables": {
                "id": f"ern:product::{product_id}",
                "version": 1,
                "moduleInput": {"module": "PRODUCT_CARD_WITH_HOVER"},
                "displayContext": {"module": "PRODUCT_CARD_WITH_HOVER"},
            },
        }
        return self._post_graphql(payload)

    def fetch_product_sku(self, product_id: str) -> Dict:
        payload = {
            "id": "86882a8b31d8657c7219bbba76635fdfcf6d8b04f959241985e7a5911b242a26",
            "variables": {"id": f"ern:product::{product_id}"},
        }
        return self._post_graphql(payload)

