from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class ProviderResponse:
    provider: str
    data: Dict[str, Any]
    source_url: Optional[str]
    cache_hit: bool = False
    error: Optional[str] = None


class ProviderError(RuntimeError):
    pass

