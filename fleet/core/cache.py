"""Fleet cache interface — abstract contract for persistence.

Implemented by infra/ with SQLite (persistent) or memory (ephemeral).
Used by all infra clients to avoid redundant API calls.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional


class Cache(ABC):
    """Key-value cache with optional TTL."""

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """Get a cached value. Returns None if missing or expired."""

    @abstractmethod
    async def set(self, key: str, value: Any, ttl_seconds: int = 300) -> None:
        """Set a cached value with TTL (default 5 minutes)."""

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete a cached value."""

    @abstractmethod
    async def clear(self, prefix: str = "") -> None:
        """Clear cache entries. If prefix given, only matching keys."""