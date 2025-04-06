# agent/browser_computer.py

import asyncio
import logging
from typing import Optional
from playwright.async_api import (
    async_playwright,
    Page,
    Browser,
    Playwright,
    BrowserContext,
    TimeoutError as PlaywrightTimeoutError, # Import specific error
)

# Get logger (configured in main.py)
logger = logging.getLogger("browser_computer")

class LocalPlaywrightComputer:
    """
    Manages a local Playwright browser instance, context, and page
    for interacting with web applications.
    """

    def __init__(self, url: str, headless: bool = True, navigation_timeout: int = 40000):
        """
        Initializes the LocalPlaywrightComputer.

        Args:
            url (str): The initial URL to navigate to upon starting.
            headless (bool): Whether to run the browser in headless mode. Defaults to True.
            navigation_timeout (int): Default navigation timeout in milliseconds for the browser context.
                                      Defaults to 40000ms (40 seconds).
        """
        self.url = url
        self.headless = headless
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None # Store context
        self.page: Optional[Page] = None

        # Store timeouts (Action timeout can be a fixed default or configurable)
        self._default_action_timeout = 30000 # Default for actions like click, fill (30s)
        self._navigation_timeout = navigation_timeout # Use the passed value

        logger.info(f"Initializing browser computer: Headless={headless}, Nav Timeout={self._navigation_timeout}ms")


    async def start(self):
        """
        Starts the Playwright instance, launches the browser, creates a context
        with specified timeouts, creates a page, and navigates to the initial URL.

        Raises:
            RuntimeError: If starting Playwright, launching the browser, or initial navigation fails.
        """
        if self._playwright and self.page:
            logger.debug("Browser computer already started.")
            return # Already started

        logger.info("Starting Playwright browser instance...")
        try:
            self._playwright = await async_playwright().start()
            logger.debug("Playwright started.")

            # Launch Chromium by default (Consider making browser type configurable later)
            logger.debug(f"Launching Chromium browser (headless={self.headless})...")
            self._browser = await self._playwright.chromium.launch(headless=self.headless)
            logger.debug("Chromium browser launched.")

            # Create a new browser context WITHOUT navigation_timeout arg here
            logger.debug(f"Creating new browser context...")
            self._context = await self._browser.new_context(
                viewport={'width': 1280, 'height': 1024}, # Standard viewport
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36', # Example recent user agent
                # locale='en-US' # Optionally set locale
            )
            logger.debug("Browser context created.")

            # Set default timeouts *after* context creation
            logger.debug(f"Setting context default timeouts: Navigation={self._navigation_timeout}ms, Action={self._default_action_timeout}ms")
            self._context.set_default_navigation_timeout(self._navigation_timeout)
            self._context.set_default_timeout(self._default_action_timeout) # This is for actions like click, fill

            # Create a new page within the context
            logger.debug("Creating new page...")
            self.page = await self._context.new_page()
            logger.debug("New page created.")

            # Navigate to the initial URL. This uses the context's default navigation timeout.
            logger.info(f"Navigating to initial URL: {self.url}")
            # Wrap goto in a try-except for specific timeout handling during startup
            try:
                 await self.page.goto(self.url) # Timeout handled by context setting
                 logger.info("Initial navigation successful.")
            except PlaywrightTimeoutError:
                 logger.error(f"Timeout ({self._navigation_timeout}ms) occurred during initial navigation to {self.url}")
                 raise # Re-raise the timeout error to be caught by the caller
            except Exception as nav_err:
                 logger.error(f"Error during initial navigation to {self.url}: {nav_err}")
                 raise # Re-raise other navigation errors

        except Exception as e:
            logger.critical(f"Fatal error during browser computer startup: {e}", exc_info=True)
            await self.close() # Attempt cleanup even if startup failed
            # Re-raise as a runtime error to signal that the computer could not start
            raise RuntimeError(f"Failed to start Playwright browser computer: {e}")


    async def close(self):
        """
        Safely closes the page, context, browser instance, and stops the
        Playwright instance, logging any errors encountered during closure.
        """
        logger.info("Closing browser computer resources...")
        # Close resources in reverse order of creation
        if self.page and not self.page.is_closed():
            try:
                logger.debug("Closing page...")
                await self.page.close()
                logger.debug("Page closed.")
            except Exception as e: logger.warning(f"Error closing page: {e}")
            self.page = None # Ensure page is None after attempting close

        if self._context:
             try:
                  logger.debug("Closing browser context...")
                  await self._context.close()
                  logger.debug("Browser context closed.")
             except Exception as e: logger.warning(f"Error closing context: {e}")
             self._context = None # Ensure context is None

        if self._browser and self._browser.is_connected():
            try:
                logger.debug("Closing browser...")
                await self._browser.close()
                logger.debug("Browser closed.")
            except Exception as e: logger.warning(f"Error closing browser: {e}")
            self._browser = None # Ensure browser is None

        if self._playwright:
            try:
                logger.debug("Stopping Playwright...")
                await self._playwright.stop()
                logger.debug("Playwright stopped.")
            except Exception as e: logger.warning(f"Error stopping playwright: {e}")
            self._playwright = None # Ensure playwright is None
        logger.info("Browser computer resources closed.")


    async def __aenter__(self):
        """Enables using the class with 'async with'."""
        await self.start()
        if not self.page: # Check if start failed silently (should have raised error)
            raise RuntimeError("Failed to initialize page within browser computer.")
        return self # Return the instance itself

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Ensures resources are closed when exiting 'async with' block."""
        await self.close()


# Example Usage (for testing this file directly)
async def _test_browser_computer():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    test_url = "https://httpbin.org/get" # A simple URL for testing
    computer = None
    try:
        logger.info("--- Testing Browser Computer Start ---")
        # Test with non-default navigation timeout
        computer = LocalPlaywrightComputer(url=test_url, headless=True, navigation_timeout=25000)
        await computer.start()
        logger.info(f"Successfully started and navigated to {computer.page.url}")
        title = await computer.page.title()
        logger.info(f"Page title: {title}")
        content = await computer.page.content()
        logger.info(f"Page content length: {len(content)}")
        logger.info("--- Testing Browser Computer Close ---")

    except Exception as e:
        logger.error(f"Error during browser computer test: {e}", exc_info=True)
    finally:
        if computer:
            await computer.close()
        logger.info("--- Browser Computer Test Finished ---")

if __name__ == "__main__":
    # To test this file: python agent/browser_computer.py
    asyncio.run(_test_browser_computer())