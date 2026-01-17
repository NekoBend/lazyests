# lazyests

[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)

**"The laziest way to handle authenticated requests."**

`lazyests` is a lightweight wrapper around [DrissionPage](https://github.com/g1879/DrissionPage) designed to act as a drop-in persistent HTTP client that leverages a real Chromium browser backend.

By "piggybacking" on a real browser session, you can bypass complex anti-bot protections, CAPTCHAs, and authentication flows without maintaining fragile header configurations or cookie jars.

## Prerequisites

- **Python 3.13** or higher.
- **Google Chrome** or a Chromium-based browser installed on your system.

## Installation

```bash
uv pip install git+https://github.com/NekoBend/lazyests.git
```

## Usage Examples

### Basic Requests

```python
from lazyests import Client

# Initialize with a persistent profile directory
client = Client(
    base_url="https://httpbin.org",
    profile_dir="./my_browser_profile",
    headless=True
)

# GET request (Executes fetch() in the browser)
resp = client.get("/get")
print(resp.json())

# POST request
resp = client.post("/post", json={"hello": "world"})
print(resp.status_code)
```

### Authentication Handoff

When you hit a login wall or CAPTCHA, don't try to solve it with code. Just let the human do it.

```python
# If usage requires login, switch to GUI mode manually or automatically
client.wait_for_login(
    success_pattern=r"dashboard",  # Regex to match successful login URL
    timeout=300
)

# ... Browser opens, you log in, browser closes ...

# Now you are authenticated!
client.get("/protected-resource")
```

### Caching

Avoid hitting endpoints repeatedly by using the built-in TTL cache.

```python
from datetime import timedelta

# Cache the response for 1 hour
client.get("/big-data", cache_ttl=timedelta(hours=1))

# Second call returns instantly from SQLite
client.get("/big-data", cache_ttl=timedelta(hours=1))
```

## Components Overview

- **`Client`**: Main entry point. Manages the Chromium process, profile persistence, and request execution.
  - `request(method, url, ...)`: Executes fetch inside the browser context.
  - `wait_for_login(pattern)`: Switches to GUI mode for manual intervention.
- **`Response`**: Wraps the JS `fetch` result. Provides `.json()`, `.text`, `.status_code`.
- **`RequestCache`**: SQLite-backed TTL cache logic.

## License

MIT
