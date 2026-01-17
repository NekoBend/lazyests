"""Caching mechanism for lazyests using SQLite."""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import threading
import time
from pathlib import Path
from types import TracebackType
from typing import Any, cast

from .schemas import FetchResponseData, JSONDict, QueryParams

logger = logging.getLogger(__name__)


class RequestCache:
    """SQLite-based cache for HTTP response data with TTL support.

    Attributes:
        db_path: Path to the SQLite database file.
        conn: The persistent SQLite connection object.
        lock: Threading lock for synchronizing database access.
    """

    REQUIRED_KEYS = frozenset((
        "status",
        "statusText",
        "url",
        "headers",
        "text",
        "redirected",
        "type",
    ))

    def __init__(self, db_path: Path) -> None:
        """Initialize the cache.

        Args:
            db_path: Path to the SQLite database file.
        """
        self.db_path = db_path
        self.lock = threading.Lock()
        # Initialize persistent connection
        # check_same_thread=False allows using the connection across multiple threads,
        # provided we handle locking (which we do with self.lock).
        self.conn = sqlite3.connect(self.db_path, timeout=10, check_same_thread=False)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the database schema."""
        try:
            with self.lock:
                # Use WAL mode to allow concurrent reads during writes and
                # improve write performance for this cache workload. The
                # NORMAL synchronous level relaxes some durability guarantees
                # in exchange for faster writes, which is acceptable for a
                # rebuildable cache.
                cursor = self.conn.execute("PRAGMA journal_mode = WAL")
                cursor.fetchone()
                cursor = self.conn.execute("PRAGMA synchronous = NORMAL")
                cursor.fetchone()

                with self.conn:
                    self.conn.execute(
                        """
                        CREATE TABLE IF NOT EXISTS cache (
                            key TEXT PRIMARY KEY,
                            value TEXT NOT NULL,
                            expires_at REAL NOT NULL
                        )
                        """
                    )
                    # Index for expiration cleanup
                    self.conn.execute(
                        "CREATE INDEX IF NOT EXISTS idx_expires_at ON cache (expires_at)"
                    )
        except sqlite3.Error as e:
            logger.error(f"Failed to initialize cache database: {e}")

    def close(self) -> None:
        """Close the database connection."""
        try:
            self.conn.close()
        except sqlite3.Error as e:
            logger.warning(f"Error closing database connection: {e}")

    def __enter__(self) -> RequestCache:
        """Enter the runtime context related to this object."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Exit the runtime context and close the database connection."""
        self.close()

    def generate_key(
        self,
        method: str,
        url: str,
        params: QueryParams | None,
        data: JSONDict | None,
        json_data: JSONDict | None,
    ) -> str:
        """Generate a unique cache key based on request parameters.

        Args:
            method: HTTP method.
            url: Full URL.
            params: Query parameters.
            data: Form data.
            json_data: JSON payload.

        Returns:
            SHA256 hash string serving as the key.
        """
        # Normalize inputs for consistent hashing
        params_str = json.dumps(params, sort_keys=True) if params else ""
        data_str = json.dumps(data, sort_keys=True) if data else ""
        json_str = json.dumps(json_data, sort_keys=True) if json_data else ""

        # Construct raw string
        raw = f"{method.upper()}|{url}|{params_str}|{data_str}|{json_str}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(self, key: str) -> FetchResponseData | None:
        """Retrieve a cached response if valid.

        Args:
            key: Cache lookup key.

        Returns:
            Cached FetchResponseData if found and not expired, else None.
        """
        now = time.time()
        try:
            with self.lock:
                cursor = self.conn.execute(
                    "SELECT value, expires_at FROM cache WHERE key = ?", (key,)
                )
                row = cursor.fetchone()

                if row:
                    value_json, expires_at = row
                    if now < expires_at:
                        # Valid cache
                        logger.debug(f"Cache HIT for key {key[:8]}...")
                        try:
                            data = json.loads(value_json)
                            return self._validate_data(data)
                        except json.JSONDecodeError:
                            logger.warning(f"Corrupt cache data for key {key[:8]}")
                            return None
                    else:
                        # Cache entry has expired.
                        logger.debug(f"Cache EXPIRED for key {key[:8]}...")
                        # Delete the expired entry to keep the database clean.
                        with self.conn:
                            self.conn.execute("DELETE FROM cache WHERE key = ?", (key,))
                else:
                    logger.debug(f"Cache MISS for key {key[:8]}...")

        except sqlite3.Error as e:
            logger.warning(f"Cache read error: {e}")

        return None

    def _validate_data(self, data: Any) -> FetchResponseData | None:
        """Validate that the loaded data matches FetchResponseData structure."""
        if not isinstance(data, dict):
            return None

        if not self.REQUIRED_KEYS.issubset(data.keys()):
            return None

        return cast(FetchResponseData, data)

    def set(self, key: str, value: FetchResponseData, ttl: float) -> None:
        """Store a response in the cache.

        Args:
            key: Cache key.
            value: Data to store.
            ttl: Time to live in seconds.
        """
        expires_at = time.time() + ttl
        value_json = json.dumps(value)

        try:
            with self.lock:
                with self.conn:
                    self.conn.execute(
                        """
                        INSERT OR REPLACE INTO cache (key, value, expires_at)
                        VALUES (?, ?, ?)
                        """,
                        (key, value_json, expires_at),
                    )
        except sqlite3.Error as e:
            logger.warning(f"Cache write error: {e}")

    def clear_expired(self) -> None:
        """Remove all expired entries from the cache."""
        now = time.time()
        try:
            with self.lock:
                with self.conn:
                    self.conn.execute("DELETE FROM cache WHERE expires_at < ?", (now,))
        except sqlite3.Error as e:
            logger.warning(f"Cache cleanup error: {e}")

    def clear_all(self) -> None:
        """Clear the entire cache."""
        try:
            with self.lock:
                with self.conn:
                    self.conn.execute("DELETE FROM cache")
        except sqlite3.Error as e:
            logger.warning(f"Failed to clear cache: {e}")
