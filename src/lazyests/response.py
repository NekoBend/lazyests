"""Response class for lazyests."""

from __future__ import annotations

import json
from typing import Any

from .schemas import FetchResponseData, JSONValue


class Response:
    """Wraps the result of a JavaScript Fetch API call.

    This class provides an interface similar to `requests.Response`.

    Attributes:
        status_code: Integer Code of responded HTTP Status, e.g. 404 or 200.
        url: Final URL location of Response.
        headers: Case-insensitive Dictionary of Response Headers.
    """

    def __init__(self, raw_data: FetchResponseData) -> None:
        """Initialize the Response object.

        Args:
            raw_data: The raw dictionary returned from the browser's fetch operation.
        """
        self._raw_data = raw_data

        self.status_code: int = raw_data.get("status", 0)
        self.url: str = raw_data.get("url", "")
        # Browser fetch API usually normalizes header keys to lowercase.
        # We ensure this consistency here for the Python dict.
        self.headers: dict[str, str] = {
            k.lower(): v for k, v in raw_data.get("headers", {}).items()
        }
        self._text: str = raw_data.get("text", "")
        self._content: bytes | None = None

    @property
    def raw_data(self) -> FetchResponseData:
        """Return the raw dictionary returned from the browser's fetch operation."""
        return self._raw_data

    @property
    def text(self) -> str:
        """Content of the response, in unicode."""
        return self._text

    @property
    def content(self) -> bytes:
        """Content of the response, in bytes."""
        if self._content is None:
            self._content = self._text.encode("utf-8")
        return self._content

    def json(self, **kwargs: Any) -> JSONValue:
        """Returns the json-encoded content of a response, if any.

        Args:
            **kwargs: Optional arguments that ``json.loads`` takes.

        Returns:
            The JSON-decoded data.

        Raises:
            json.JSONDecodeError: If the response body does not contain valid JSON.
        """
        return json.loads(self.text, **kwargs)

    @property
    def ok(self) -> bool:
        """Returns True if :attr:`status_code` is in the 200-299 range, False if not."""
        try:
            return 200 <= self.status_code < 300
        except (ValueError, TypeError):
            return False
