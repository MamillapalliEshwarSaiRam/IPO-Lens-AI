from typing import Any, Dict

import httpx

from app.core.config import get_settings
from app.providers.base import ProviderResponse


class AlphaVantageClient:
    base_url = "https://www.alphavantage.co/query"

    def __init__(self) -> None:
        self.settings = get_settings()

    async def company_overview(self, symbol: str) -> ProviderResponse:
        if not self.settings.alpha_vantage_api_key:
            return ProviderResponse(
                provider="alpha_vantage",
                data={},
                source_url=self.base_url,
                error="ALPHA_VANTAGE_API_KEY is not configured.",
            )
        params: Dict[str, Any] = {
            "function": "OVERVIEW",
            "symbol": symbol,
            "apikey": self.settings.alpha_vantage_api_key,
        }
        try:
            async with httpx.AsyncClient(timeout=self.settings.provider_timeout_seconds) as client:
                response = await client.get(self.base_url, params=params)
                response.raise_for_status()
                return ProviderResponse(
                    provider="alpha_vantage",
                    data=response.json(),
                    source_url=self.base_url,
                )
        except Exception as exc:
            return ProviderResponse(provider="alpha_vantage", data={}, source_url=self.base_url, error=str(exc))


alpha_vantage_client = AlphaVantageClient()
