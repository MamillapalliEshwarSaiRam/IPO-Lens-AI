from typing import Any, Dict

import httpx

from app.core.config import get_settings
from app.providers.base import ProviderResponse


class FinnhubClient:
    base_url = "https://finnhub.io/api/v1"

    def __init__(self) -> None:
        self.settings = get_settings()

    async def company_profile(self, symbol: str) -> ProviderResponse:
        if not self.settings.finnhub_api_key:
            return ProviderResponse(
                provider="finnhub",
                data={},
                source_url=self.base_url,
                error="FINNHUB_API_KEY is not configured.",
            )
        params: Dict[str, Any] = {"symbol": symbol, "token": self.settings.finnhub_api_key}
        url = f"{self.base_url}/stock/profile2"
        try:
            async with httpx.AsyncClient(timeout=self.settings.provider_timeout_seconds) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                return ProviderResponse(provider="finnhub", data=response.json(), source_url=url)
        except Exception as exc:
            return ProviderResponse(provider="finnhub", data={}, source_url=url, error=str(exc))

    async def ipo_calendar(self) -> ProviderResponse:
        if not self.settings.finnhub_api_key:
            return ProviderResponse(
                provider="finnhub",
                data={},
                source_url=self.base_url,
                error="FINNHUB_API_KEY is not configured.",
            )
        url = f"{self.base_url}/calendar/ipo"
        try:
            async with httpx.AsyncClient(timeout=self.settings.provider_timeout_seconds) as client:
                response = await client.get(url, params={"token": self.settings.finnhub_api_key})
                response.raise_for_status()
                return ProviderResponse(provider="finnhub", data=response.json(), source_url=url)
        except Exception as exc:
            return ProviderResponse(provider="finnhub", data={}, source_url=url, error=str(exc))


finnhub_client = FinnhubClient()
