import time
from collections import defaultdict, deque
from typing import Deque, Dict


class RateLimiter:
    def __init__(self, max_calls: int = 5, window_seconds: int = 60) -> None:
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self._calls: Dict[str, Deque[float]] = defaultdict(deque)

    def allow(self, provider: str) -> bool:
        now = time.monotonic()
        calls = self._calls[provider]
        while calls and now - calls[0] > self.window_seconds:
            calls.popleft()
        if len(calls) >= self.max_calls:
            return False
        calls.append(now)
        return True

    def remaining(self, provider: str) -> int:
        now = time.monotonic()
        calls = self._calls[provider]
        while calls and now - calls[0] > self.window_seconds:
            calls.popleft()
        return max(0, self.max_calls - len(calls))


provider_rate_limiter = RateLimiter(max_calls=30, window_seconds=60)

