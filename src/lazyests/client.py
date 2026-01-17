"""Main client module for lazyests."""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import timedelta
from pathlib import Path
from typing import Any, Callable, cast
from urllib.parse import urlencode, urljoin, urlparse

from DrissionPage import ChromiumOptions, ChromiumPage

from .cache import RequestCache
from .exceptions import BrowserInitError
from .response import Response
from .schemas import FetchOptions, FetchResponseData, Headers, JSONDict, QueryParams

logger = logging.getLogger(__name__)

# Type alias for page factory
PageFactory = Callable[[ChromiumOptions], ChromiumPage]


class Client:
    """An HTTP client powered by a Chromium browser backend.

    This class provides an API similar to the `requests` library but operates
    a real browser instance behind the scenes to leverage existing authentication
    states (Browser Piggybacking).

    Attributes:
        base_url: The base URL for all requests.
        profile_dir: Path to the browser profile directory.
        headless: Whether the browser runs in headless mode.
    """

    def __init__(
        self,
        base_url: str | None = None,
        profile_dir: str | Path = "./browser_data",
        headless: bool = True,
        auto_navigate_for_cors: bool = False,
        cache: RequestCache | None = None,
        page_factory: PageFactory | None = None,
    ) -> None:
        """Initialize the Client.

        Args:
            base_url: The base URL to prefix to relative URLs.
            profile_dir: Directory path for the user data profile.
            headless: Run browser in headless mode.
            auto_navigate_for_cors: Auto navigate to target origin to fix CORS.
            cache: Optional RequestCache instance (for testing/DI).
            page_factory: Optional callable to create browser pages (for testing/DI).

        Raises:
            BrowserInitError: If browser fails to start.
        """
        self.base_url = base_url.rstrip("/") if base_url else None
        self.profile_dir = Path(profile_dir)
        self.headless = headless
        self.auto_navigate_for_cors = auto_navigate_for_cors
        self._page_factory = page_factory

        # Initialize cache store in the profile directory for persistence
        if cache:
            self.cache = cache
        else:
            if not self.profile_dir.exists():
                self.profile_dir.mkdir(parents=True, exist_ok=True)
            self.cache = RequestCache(self.profile_dir / "request_cache.db")

        self._page: ChromiumPage | None = None
        self._user_agent: str | None = None
        self._init_browser()

    def _init_browser(self) -> None:
        """Initialize the DrissionPage browser instance.

        Raises:
            BrowserInitError: If initialization fails.
        """
        try:
            options = ChromiumOptions()
            options.set_user_data_path(str(self.profile_dir))
            options.headless(self.headless)
            if self._user_agent:
                options.set_user_agent(self._user_agent)

            if self._page_factory:
                self._page = self._page_factory(options)
            else:
                self._page = ChromiumPage(options)
        except Exception as e:
            # Catching generic Exception because DrissionPage can raise various errors
            raise BrowserInitError(f"Failed to initialize browser: {e}") from e

    @property
    def page(self) -> ChromiumPage:
        """Return the active DrissionPage instance.

        Returns:
            The active ChromiumPage.

        Raises:
            BrowserInitError: If page is not initialized.
        """
        if self._page is None:
            raise BrowserInitError("Browser has not been initialized.")
        return self._page

    @property
    def current_url(self) -> str:
        """Return the current URL of the browser."""
        return self.page.url if self._page else ""

    def _resolve_url(self, endpoint: str) -> str:
        """Resolve a partial endpoint to a full URL.

        Args:
            endpoint: The path or full URL.

        Returns:
            Absolute URL string.
        """
        if endpoint.startswith(("http://", "https://")):
            return endpoint

        if self.base_url:
            return urljoin(self.base_url + "/", endpoint.lstrip("/"))

        return endpoint

    def _ensure_cors_context(self, url: str) -> None:
        """Navigate browser if needed to satisfy CORS policies.

        Args:
            url: The target request URL.
        """
        if not self.auto_navigate_for_cors:
            return

        try:
            target_netloc = urlparse(url).netloc
            current_netloc = urlparse(self.current_url).netloc

            if not target_netloc or target_netloc == current_netloc:
                return

            target_scheme = urlparse(url).scheme or "https"
            target_origin = f"{target_scheme}://{target_netloc}"

            # Navigate to the target origin if we are not already there.
            # This ensures that cookies and CORS context are correctly established.
            self.page.get(target_origin)
        except Exception:
            # Swallow exceptions to maintain "lazy" behavior; fail silently.
            pass

    @staticmethod
    def _validate_fetch_response(data: Any) -> FetchResponseData | None:
        """Validate that the fetch response data matches the expected structure."""
        if not isinstance(data, dict):
            return None

        required_keys = {
            "status",
            "statusText",
            "url",
            "headers",
            "text",
            "redirected",
            "type",
        }

        if not required_keys.issubset(data.keys()):
            return None

        return cast(FetchResponseData, data)

    def request(
        self,
        method: str,
        endpoint: str,
        params: QueryParams | None = None,
        data: JSONDict | None = None,
        json_data: JSONDict | None = None,
        headers: Headers | None = None,
        timeout: float = 30.0,
        cache_ttl: int | float | timedelta | None = None,
    ) -> Response:
        """Execute an HTTP request using the browser's fetch API.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: Target URL or path.
            params: Query parameters to append to URL.
            data: Form data to send in body (application/x-www-form-urlencoded).
            json_data: JSON data to send in body (application/json).
            headers: HTTP headers.
            timeout: Request timeout in seconds.
            cache_ttl: Time-to-live for caching the response.
                       Can be int/float (seconds) or datetime.timedelta.
                       If None (default), caching is disabled.

        Returns:
            Response object containing the fetch result.
        """
        full_url = self._resolve_url(endpoint)

        if params:
            query_string = urlencode(params)
            joiner = "&" if "?" in full_url else "?"
            full_url = f"{full_url}{joiner}{query_string}"

        self._ensure_cors_context(full_url)

        # Check Cache
        cache_key = ""
        if cache_ttl is not None:
            cache_key = self.cache.generate_key(method, full_url, None, data, json_data)
            cached_data = self.cache.get(cache_key)
            if cached_data:
                return Response(cached_data)

        # Build fetch options
        options: FetchOptions = {
            "method": method.upper(),
            "headers": headers or {},
        }

        if json_data is not None:
            options["body"] = json.dumps(json_data)
            if "Content-Type" not in options["headers"]:
                options["headers"]["Content-Type"] = "application/json"
        elif data is not None:
            # Support form-urlencoded
            options["body"] = urlencode(data, doseq=True)
            if "Content-Type" not in options["headers"]:
                options["headers"]["Content-Type"] = "application/x-www-form-urlencoded"

        response = self._exec_fetch(full_url, options, timeout)

        # Store in Cache
        if cache_ttl is not None and response.ok:
            # Normalize TTL to seconds
            ttl_seconds: float
            if isinstance(cache_ttl, timedelta):
                ttl_seconds = cache_ttl.total_seconds()
            else:
                ttl_seconds = float(cache_ttl)

            self.cache.set(cache_key, response.raw_data, ttl_seconds)

        return response

    def _exec_fetch(self, url: str, options: FetchOptions, timeout: float) -> Response:
        """Execute the fetch JavaScript in the browser.

        Args:
            url: Full URL to fetch.
            options: Fetch options dictionary.
            timeout: Timeout in seconds.

        Returns:
            Response object.
        """
        # Serialize arguments to pass safely to JS
        safe_url = json.dumps(url)
        safe_options = json.dumps(options)
        timeout_ms = int(timeout * 1000)

        # We wrap the code in an async function call and use AbortController for timeout
        js_script = f"""
            (async () => {{
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), {timeout_ms});
                try {{
                    const opts = {safe_options};
                    opts.signal = controller.signal;

                    const res = await fetch({safe_url}, opts);
                    clearTimeout(timeoutId);

                    const text = await res.text();
                    const headers = {{}};
                    res.headers.forEach((v, k) => headers[k] = v);

                    return {{
                        status: res.status,
                        statusText: res.statusText,
                        url: res.url,
                        headers: headers,
                        text: text,
                        redirected: res.redirected,
                        type: res.type
                    }};
                }} catch (e) {{
                    return {{ error: e.toString() }};
                }}
            }})()
        """

        # Log execution details. Full script logging is disabled for security.
        logger.debug("Executing fetch with timeout %s ms", timeout_ms)

        # Use run_cdp to specifically leverage 'awaitPromise=True'.
        cdp_res = self.page.run_cdp(
            "Runtime.evaluate",
            expression=js_script,
            awaitPromise=True,
            returnByValue=True,
            includeCommandLineAPI=False,
        )

        if "exceptionDetails" in cdp_res:
            details = cdp_res["exceptionDetails"]
            raise RuntimeError(f"JS Execution Error: {details}")

        result_value = cdp_res.get("result", {}).get("value")

        if not isinstance(result_value, dict):
            raise RuntimeError(f"Unexpected JS result type: {type(result_value)}")

        if "error" in result_value:
            err_msg = result_value["error"]
            if "AbortError" in err_msg:
                raise TimeoutError(f"Request timed out after {timeout} seconds")
            raise RuntimeError(f"Fetch failed: {err_msg}")

        # Validate data
        response_data = self._validate_fetch_response(result_value)
        if not response_data:
            # We already checked for "error" key above, so this is a structural mismatch
            raise RuntimeError(
                f"Invalid fetch response structure. Keys found: {list(result_value.keys())}"
            )

        return Response(response_data)

    def get(
        self, endpoint: str, params: QueryParams | None = None, **kwargs: Any
    ) -> Response:
        """Send a GET request.

        Args:
            endpoint: URL or path.
            params: Query parameters.
            **kwargs: Extra arguments passed to request().

        Returns:
            Response object.
        """
        return self.request("GET", endpoint, params=params, **kwargs)

    def post(
        self,
        endpoint: str,
        data: JSONDict | None = None,
        json: JSONDict | None = None,
        **kwargs: Any,
    ) -> Response:
        """Send a POST request.

        Args:
            endpoint: URL or path.
            data: Form data.
            json: JSON data (passed as json_data to request).
            **kwargs: Extra arguments passed to request().

        Returns:
            Response object.
        """
        return self.request("POST", endpoint, data=data, json_data=json, **kwargs)

    def wait_for_login(
        self, success_pattern: str, timeout: int = 300, start_url: str | None = None
    ) -> None:
        """Wait for successful login via GUI intervention.

        This method:
        1. Closes the headless browser.
        2. Opens a GUI browser.
        3. Navigates to start_url (or stays on current page if None).
        4. Waits for the URL to match the `success_pattern`.
        5. Closes the GUI browser.
        6. Re-opens the headless browser.

        Args:
            success_pattern: Regex pattern to match the URL indicating success.
            timeout: Max wait time in seconds. Defaults to 300.
            start_url: Optional URL to navigate to after opening GUI.
                       If None, attempts to stay on the previous URL.
        """
        original_url = self.current_url

        logger.info("Initiating manual login handoff...")
        # 1. Switch to GUI
        self._restart_browser(headless=False)

        captured_cookies = None

        try:
            # 2. Navigate to context
            target_url = start_url if start_url else original_url
            if target_url and target_url != "about:blank":
                self.page.get(target_url)

            logger.info(f"Waiting for URL matching: '{success_pattern}'")

            start_time = time.time()
            while True:
                if time.time() - start_time > timeout:
                    logger.warning("Login timeout exceeded.")
                    break

                try:
                    current = self.page.url
                    if re.search(success_pattern, current):
                        logger.info("Login success detected!")

                        # Capture User Agent from GUI context
                        try:
                            self._user_agent = self.page.user_agent
                        except Exception:
                            logger.warning("Failed to capture User-Agent.")

                        # Give a moment for cookies to flush/settle
                        time.sleep(3.0)
                        captured_cookies = self.page.cookies(all_info=True)
                        break
                except Exception as e:
                    # Only log if it's not a harmless "browser closed" check during simple polling
                    if "Login success detected" in str(locals().get("e", "")):
                        pass
                    logger.debug(f"Polling error or cookie capture failed: {e}")
                    pass

                time.sleep(1.0)

        finally:
            logger.info("Resuming headless operation...")
            # 5. Switch back to Headless
            self._restart_browser(headless=True)

            if captured_cookies:
                try:
                    # Navigate to the domain root or original URL domain to ensure cookies stick
                    # Chrome/DrissionPage often requires being on the same domain to set secure cookies
                    target_scheme_netloc = None
                    if start_url:
                        u = urlparse(start_url)
                        if u.scheme and u.netloc:
                            target_scheme_netloc = f"{u.scheme}://{u.netloc}"

                    if (
                        not target_scheme_netloc
                        and original_url
                        and "://" in original_url
                    ):
                        u = urlparse(original_url)
                        if u.scheme and u.netloc:
                            target_scheme_netloc = f"{u.scheme}://{u.netloc}"

                    if not target_scheme_netloc and self.base_url:
                        target_scheme_netloc = self.base_url

                    if target_scheme_netloc:
                        logger.debug(
                            f"Navigating to {target_scheme_netloc} to restore cookies."
                        )
                        self.page.get(target_scheme_netloc)

                    # Sanitize cookies to ensure compatibility
                    sanitized_cookies = []
                    allowed_keys = {
                        "name",
                        "value",
                        "domain",
                        "path",
                        "expires",
                        "size",
                        "httpOnly",
                        "secure",
                        "sameSite",
                        "priority",
                    }
                    for c in captured_cookies:
                        clean_cookie = {
                            k: v for k, v in dict(c).items() if k in allowed_keys
                        }
                        if clean_cookie.get("expires", 0) <= 0:
                            clean_cookie.pop("expires", None)
                        sanitized_cookies.append(clean_cookie)

                    self.page.set.cookies(sanitized_cookies)

                    # Refresh to "activate" cookies, but careful with crashes
                    try:
                        self.page.refresh()
                        # Wait for load carefully
                        self.page.wait.load_start()
                        self.page.wait.doc_loaded()
                    except Exception as e:
                        logger.debug(f"Refresh wait warning: {e}")

                    logger.info("Restored cookies to headless session.")
                except Exception as e:
                    logger.warning(f"Failed to restore cookies: {e}")

    def _restart_browser(self, headless: bool) -> None:
        """Restart the browser process with the specified headless mode.

        Safely shuts down the current instance to release profile locks before
        starting a new instance.

        Args:
            headless: True for headless mode, False for GUI mode.
        """
        if self._page:
            try:
                self._page.quit()
            except Exception:
                # Ignore errors during shutdown (e.g. process already dead)
                pass
            self._page = None

        # DrissionPage/Chromium sometimes needs a moment to release file locks
        time.sleep(2.0)

        # Update configuration and re-initialize
        self.headless = headless
        self._init_browser()

    def close(self) -> None:
        """Close the browser instance and other resources."""
        if self._page:
            self._page.quit()

        if self.cache and hasattr(self.cache, "close"):
            self.cache.close()
