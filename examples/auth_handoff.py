"""Example of authentication handoff using lazyests.

This script demonstrates how to seamlessly switch between headless automation
and manual user intervention for login processes using 'The Internet' test site.
"""

import logging
import sys

from rich.logging import RichHandler

# Make sure we can import lazyests from src if running from repo root
sys.path.append("src")

from lazyests import Client

# Configure logging with RichHandler
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="%H:%M:%S",
    handlers=[RichHandler(rich_tracebacks=True, markup=True)],
)
logger = logging.getLogger("auth_example")


def main() -> None:
    """Run the authentication handoff example."""
    base_url = "https://the-internet.herokuapp.com"

    # Initialize client in headless mode
    # We use a persistent profile so the login state is saved for future runs
    # auto_navigate_for_cors=True ensures we are on the right domain before fetching
    client = Client(
        base_url=base_url,
        profile_dir="./browser_data/auth_example_profile",
        headless=True,
        auto_navigate_for_cors=True,
    )

    try:
        logger.info("1. Attempting to access protected resource...")
        # The /secure endpoint redirects to /login if not authenticated
        response = client.get("/secure")

        # Check if we are already logged in (from a previous run)
        if response.status_code == 200 and "Secure Area" in response.text:
            logger.info("✅ Already authenticated! Access granted.")
            logger.info(
                "Response snippet: %s...", response.text[:100].replace("\n", " ")
            )
            return

        logger.info("❌ Access denied. Redirected to: %s", response.url)
        logger.info("Interactive login required.")

        # Trigger the manual handoff
        # The browser will open in GUI mode.
        # User performs login:
        #   Username: tomsmith
        #   Password: SuperSecretPassword!
        logger.info("\n" + "=" * 60)
        logger.info("🚨 HANDOFF INITIATED 🚨")
        logger.info("Please log in manually in the opened browser window.")
        logger.info(f"URL: {base_url}/login")
        logger.info("Credentials (for test site):")
        logger.info("  User: tomsmith")
        logger.info("  Pass: SuperSecretPassword!")
        logger.info("=" * 60 + "\n")

        # We wait until the browser URL matches "secure", which happens after successful login
        # We also tell the browser to explicitly go to the login page (response.url)
        logging.getLogger("lazyests.client").setLevel(logging.DEBUG)
        client.wait_for_login(
            success_pattern="secure", timeout=120, start_url=response.url
        )
        logging.getLogger("lazyests.client").setLevel(logging.INFO)

        logger.info("2. Retrying access to protected resource...")
        response = client.get("/secure")

        if response.status_code == 200 and "Secure Area" in response.text:
            logger.info("✅ Authentication successful! Access granted.")
            logger.info(
                "Response snippet: %s...", response.text[:100].replace("\n", " ")
            )
        else:
            logger.error("❌ Failed to access protected resource even after handoff.")
            logger.error(f"   Final URL: {response.url}")
            logger.error(f"   Snippet: {response.text[:200]}")

    finally:
        client.close()


if __name__ == "__main__":
    main()
