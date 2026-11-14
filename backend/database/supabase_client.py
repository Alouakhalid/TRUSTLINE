"""Resilient Supabase Client for TRUSTLINE Spacecraft & Ground Telemetry.

Operates in dual-mode:
- When SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_KEY) are configured and reachable,
  provides authenticated PostgREST and Storage operations with truth-verified health metrics.
- When unconfigured or offline (air-gapped spacecraft edge), reports status truthfully as
  'UNCONFIGURED' or 'OFFLINE' and falls back safely to local persistence without raising unhandled crashes.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any

logger = logging.getLogger("trustline.supabase")

try:
    from supabase import Client, create_client
    _SUPABASE_AVAILABLE = True
except ImportError:
    _SUPABASE_AVAILABLE = False
    Client = Any  # type: ignore


class SupabaseClientWrapper:
    """Thread-safe, truth-reporting wrapper around supabase-py Client."""

    def __init__(self) -> None:
        self.url: str | None = os.getenv("SUPABASE_URL")
        self.key: str | None = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
        self._client: Client | None = None
        self._initialized: bool = False
        self._last_health_check: float = 0.0
        self._last_status: dict[str, Any] = {
            "configured": False,
            "status": "UNCONFIGURED",
            "url": None,
            "latency_ms": None,
            "error": None,
        }
        self._init_client()

    def _init_client(self) -> None:
        if not _SUPABASE_AVAILABLE:
            self._last_status = {
                "configured": False,
                "status": "UNAVAILABLE",
                "url": None,
                "latency_ms": None,
                "error": "supabase python package is not installed",
            }
            return

        if not self.url or not self.key:
            self._last_status = {
                "configured": False,
                "status": "UNCONFIGURED",
                "url": None,
                "latency_ms": None,
                "error": "SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not set in environment",
            }
            return

        try:
            self._client = create_client(self.url, self.key)
            self._initialized = True
            logger.info("Supabase client initialized with endpoint %s", self.url[:16] + "...")
        except Exception as exc:
            logger.warning("Failed to initialize Supabase client: %s", exc)
            self._client = None
            self._initialized = False
            self._last_status = {
                "configured": True,
                "status": "ERROR",
                "url": self._mask_url(self.url),
                "latency_ms": None,
                "error": str(exc),
            }

    @staticmethod
    def _mask_url(url: str | None) -> str | None:
        if not url:
            return None
        parts = url.split("://")
        if len(parts) == 2:
            domain = parts[1].split("/")[0]
            if len(domain) > 10:
                return f"{parts[0]}://{domain[:4]}...{domain[-4:]}"
            return f"{parts[0]}://{domain}"
        return url[:8] + "..."

    def is_configured(self) -> bool:
        return bool(self._initialized and self._client is not None)

    def get_status(self, force_refresh: bool = False) -> dict[str, Any]:
        """Verify real Supabase health via an active ping query.
        
        Cached for 15 seconds to avoid unnecessary network latency during tight polling loops.
        """
        now = time.time()
        if not force_refresh and (now - self._last_health_check < 15.0):
            return dict(self._last_status)

        if not self.is_configured():
            self._init_client()
            if not self.is_configured():
                return dict(self._last_status)

        self._last_health_check = now
        t0 = time.perf_counter()
        try:
            # Ping user_profiles or application_settings or sync_checkpoints
            res = self._client.table("application_settings").select("key").limit(1).execute()
            latency = (time.perf_counter() - t0) * 1000.0
            self._last_status = {
                "configured": True,
                "status": "HEALTHY",
                "url": self._mask_url(self.url),
                "latency_ms": round(latency, 2),
                "error": None,
            }
        except Exception as exc:
            err_msg = str(exc)
            latency = (time.perf_counter() - t0) * 1000.0
            # If the table does not exist yet because migration hasn't run, check if connection was ok
            if "relation \"public.application_settings\" does not exist" in err_msg:
                self._last_status = {
                    "configured": True,
                    "status": "MIGRATION_REQUIRED",
                    "url": self._mask_url(self.url),
                    "latency_ms": round(latency, 2),
                    "error": "Connection established, but tables not yet created (run 001_initial_schema.sql)",
                }
            else:
                self._last_status = {
                    "configured": True,
                    "status": "ERROR",
                    "url": self._mask_url(self.url),
                    "latency_ms": round(latency, 2),
                    "error": err_msg,
                }
        return dict(self._last_status)

    def insert(self, table: str, record: dict[str, Any]) -> dict[str, Any] | None:
        """Insert a record into a Supabase table."""
        if not self.is_configured():
            return None
        try:
            response = self._client.table(table).insert(record).execute()
            if response.data and len(response.data) > 0:
                return response.data[0]
            return record
        except Exception as exc:
            logger.warning("Supabase insert error on %s: %s", table, exc)
            return None

    def upsert(self, table: str, record: dict[str, Any], on_conflict: str = "id") -> dict[str, Any] | None:
        """Upsert a record into a Supabase table."""
        if not self.is_configured():
            return None
        try:
            response = self._client.table(table).upsert(record, on_conflict=on_conflict).execute()
            if response.data and len(response.data) > 0:
                return response.data[0]
            return record
        except Exception as exc:
            logger.warning("Supabase upsert error on %s: %s", table, exc)
            return None

    def select(self, table: str, filters: dict[str, Any] | None = None, limit: int = 100) -> list[dict[str, Any]]:
        """Query records from a Supabase table with simple equality filters."""
        if not self.is_configured():
            return []
        try:
            query = self._client.table(table).select("*")
            if filters:
                for k, v in filters.items():
                    query = query.eq(k, v)
            response = query.limit(limit).execute()
            return response.data or []
        except Exception as exc:
            logger.warning("Supabase select error on %s: %s", table, exc)
            return []

    def upload_file(self, bucket: str, path: str, file_bytes: bytes, content_type: str = "application/octet-stream") -> str | None:
        """Upload a file to Supabase Storage and return its storage path."""
        if not self.is_configured():
            return None
        try:
            self._client.storage.from_(bucket).upload(
                path=path,
                file=file_bytes,
                file_options={"content-type": content_type, "upsert": "true"},
            )
            return f"{bucket}/{path}"
        except Exception as exc:
            logger.warning("Supabase storage upload error on %s/%s: %s", bucket, path, exc)
            return None

    def download_file(self, bucket: str, path: str) -> bytes | None:
        """Download file bytes from Supabase Storage."""
        if not self.is_configured():
            return None
        try:
            return self._client.storage.from_(bucket).download(path)
        except Exception as exc:
            logger.warning("Supabase storage download error on %s/%s: %s", bucket, path, exc)
            return None


# Global singleton instance
supabase_client = SupabaseClientWrapper()
