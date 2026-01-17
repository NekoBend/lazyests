"""Type definitions for lazyests."""

from typing import TypedDict

# JSON Type Definition
JSONValue = str | int | float | bool | None | dict[str, "JSONValue"] | list["JSONValue"]
JSONDict = dict[str, JSONValue]
JSONList = list[JSONValue]

# Other common types
QueryParams = dict[str, str | int | float | bool]
Headers = dict[str, str]


class FetchOptions(TypedDict, total=False):
    """Options to pass to the browser's fetch API.

    This maps to the RequestInit object in the Fetch API.
    """

    method: str
    headers: Headers
    body: str | None
    credentials: str
    signal: object  # Represents the AbortSignal on the JS side


class FetchResponseData(TypedDict):
    """Structure of the response data coming from the browser's fetch API."""

    status: int
    statusText: str
    url: str
    headers: dict[str, str]
    text: str
    redirected: bool
    type: str
