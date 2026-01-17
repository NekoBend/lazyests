"""Quick start example for lazyests.

This script demonstrates the basic usage of the Client class,
including making GET/POST requests and handling the handoff flow.
"""

import json
import logging
import sys
import time
from pathlib import Path

# Ensure src is in python path for local testing
sys.path.append(str(Path(__file__).parent.parent / "src"))

from lazyests import Client, LazyestsError, setup_logging

logger = logging.getLogger("lazyests.quick_start")


def main() -> None:
    """Run the demonstration."""
    # Enable the rich logger
    setup_logging(level=logging.INFO)

    logger.info("🚀 Initializing lazyests Client (Headless Mode)...")

    # Initialize client targeting httpbin.org
    # We use a local profile directory for this example
    client = Client(
        base_url="https://httpbin.org",
        profile_dir="./browser_data/quick_start_profile",
        headless=True,
        auto_navigate_for_cors=True,
    )

    try:
        # 1. Simple GET Request
        logger.info("📡 1. Testing GET /get...")
        response = client.get("/get")

        if response.ok:
            data = response.json()
            logger.info(f"✅ Status: {response.status_code}")
            if isinstance(data, dict):
                logger.info(f"   Origin: {data.get('origin')}")
                headers = data.get("headers", {})
                if isinstance(headers, dict):
                    logger.info(f"   User-Agent: {headers.get('User-Agent')}")
        else:
            logger.error(f"❌ Failed: {response.status_code}")

        # 2. POST Request with JSON
        logger.info("📨 2. Testing POST /post...")
        payload = {"mission": "lazy", "philosophy": "virtue"}
        response = client.post("/post", json=payload)

        if response.ok:
            full_resp = response.json()
            logger.info(f"✅ Status: {response.status_code}")
            logger.debug(f"   Full Response: {json.dumps(full_resp, indent=2)}")
        else:
            logger.error(f"❌ Failed: {response.status_code}")

        # 3. Simulate Authentication Handoff
        # In a real scenario, this happens when you get a 401/403
        logger.info("👀 3. Simulating Authentication Handoff...")
        logger.info("   (The browser will open. Please wait or interact.)")
        logger.info("   Target: We will wait until URL contains 'headers'")

        # Trigger handoff to manual browser.
        # This will pause execution until the user (or existing cookies) causes
        # the URL to match the success pattern. For this demo, we use httpbin.org
        logger.info("   >> ACTION REQUIRED: When the browser opens, verify it loads.")
        logger.info("   >> Logic: waiting for URL pattern 'httpbin.org'.")

        client.wait_for_login(success_pattern=r"httpbin\.org", timeout=10)

        logger.info("✨ Handoff complete! Back to headless.")

        # 4. Verify context is maintained
        logger.info("🔍 4. Verifying session...")
        response = client.get("/status/200")
        logger.info(f"✅ Status Check: {response.status_code}")

        # 5. Testing Cache
        logger.info("💾 5. Testing Cache TTL...")
        start = time.time()
        # First request: Cache Miss
        client.get("/delay/2", cache_ttl=60)
        elapsed1 = time.time() - start
        logger.info(f"   Request 1 (Miss): {elapsed1:.2f}s (should be > 2s)")

        start = time.time()
        # Second request: Cache Hit
        client.get("/delay/2", cache_ttl=60)
        elapsed2 = time.time() - start
        logger.info(f"   Request 2 (Hit):  {elapsed2:.2f}s (should be instantaneous)")

    except LazyestsError as e:
        logger.exception(f"🔥 Error: {e}")
    except KeyboardInterrupt:
        logger.warning("\n🛑 Interrupted by user")
    finally:
        logger.info("👋 Closing client...")
        client.close()


if __name__ == "__main__":
    main()
