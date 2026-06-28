from typing import Any, Dict, List, Optional

import httpx

from app.core.config import get_settings
from app.providers.base import ProviderResponse


class LLMClient:
    """Provider-neutral chat client using an OpenAI-compatible transport.

    The MVP agents are deterministic by default, but this adapter keeps the production interface
    explicit. Gemini, OpenAI, and other compatible providers can be swapped with env vars.
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self.base_url = self.settings.llm_base_url.rstrip("/")

    def model_for_task(self, task: str) -> str:
        if task in {"scoring", "conflict_resolution", "report_writer"}:
            return self.settings.llm_strong_model or self.settings.llm_model
        return self.settings.llm_cheap_model or self.settings.llm_model

    async def chat(
        self,
        messages: List[Dict[str, str]],
        task: str,
        temperature: float = 0.0,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> ProviderResponse:
        if not self.settings.llm_api_key:
            return ProviderResponse(
                provider="llm_compatible",
                data={},
                source_url=f"{self.base_url}/chat/completions",
                error="LLM_API_KEY is not configured.",
            )
        payload: Dict[str, Any] = {
            "model": self.model_for_task(task),
            "messages": messages,
            "temperature": temperature,
        }
        if response_format:
            payload["response_format"] = response_format
        try:
            async with httpx.AsyncClient(timeout=self.settings.provider_timeout_seconds) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.settings.llm_api_key}"},
                    json=payload,
                )
                response.raise_for_status()
                return ProviderResponse(
                    provider="llm_compatible",
                    data=response.json(),
                    source_url=f"{self.base_url}/chat/completions",
                )
        except Exception as exc:
            return ProviderResponse(
                provider="llm_compatible",
                data={},
                source_url=f"{self.base_url}/chat/completions",
                error=str(exc),
            )


llm_client = LLMClient()
