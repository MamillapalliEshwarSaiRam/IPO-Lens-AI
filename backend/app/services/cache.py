import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CacheEntry


def make_cache_key(provider: str, payload: Dict[str, Any]) -> str:
    normalized = json.dumps(payload, sort_keys=True, default=str)
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return f"{provider}:{digest}"


class CacheService:
    async def get(self, db: AsyncSession, key: str) -> Optional[Dict[str, Any]]:
        result = await db.execute(select(CacheEntry).where(CacheEntry.key == key))
        entry = result.scalar_one_or_none()
        if not entry:
            return None
        if entry.expires_at:
            expires_at = entry.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at < datetime.now(timezone.utc):
                return None
        entry.hit_count += 1
        await db.commit()
        return entry.response_json

    async def set(
        self,
        db: AsyncSession,
        key: str,
        provider: str,
        response_json: Dict[str, Any],
        ttl_seconds: int,
    ) -> CacheEntry:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
        result = await db.execute(select(CacheEntry).where(CacheEntry.key == key))
        entry = result.scalar_one_or_none()
        if entry:
            entry.response_json = response_json
            entry.expires_at = expires_at
            entry.created_at = datetime.now(timezone.utc)
        else:
            entry = CacheEntry(
                key=key,
                provider=provider,
                response_json=response_json,
                expires_at=expires_at,
            )
            db.add(entry)
        await db.commit()
        await db.refresh(entry)
        return entry


cache_service = CacheService()
