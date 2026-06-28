from typing import Any, Dict

import httpx

from app.core.config import get_settings
from app.providers.base import ProviderResponse


class NewsAPIClient:
    base_url = "https://newsapi.org/v2/everything"

    def __init__(self) -> None:
        self.settings = get_settings()

    async def search_company(self, company_name: str) -> ProviderResponse:
        if not self.settings.news_api_key:
            return ProviderResponse(
                provider="newsapi",
                data={},
                source_url=self.base_url,
                error="NEWS_API_KEY is not configured.",
            )
        params: Dict[str, Any] = {
            "q": f'"{company_name}" AND (IPO OR funding OR valuation OR revenue OR lawsuit OR regulatory)',
            "sortBy": "publishedAt",
            "language": "en",
            "apiKey": self.settings.news_api_key,
            "searchIn": "title,description,content",
            "pageSize": 10,
        }
        try:
            async with httpx.AsyncClient(timeout=self.settings.provider_timeout_seconds) as client:
                response = await client.get(self.base_url, params=params)
                response.raise_for_status()
                return ProviderResponse(provider="newsapi", data=response.json(), source_url=self.base_url)
        except Exception as exc:
            return ProviderResponse(provider="newsapi", data={}, source_url=self.base_url, error=str(exc))


newsapi_client = NewsAPIClient()
