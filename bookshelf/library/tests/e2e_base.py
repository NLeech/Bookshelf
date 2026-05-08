import os
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page


class PlaywrightBaseTestCase(StaticLiveServerTestCase):
    """Base class for E2E tests using Playwright."""

    browser: Browser
    context: BrowserContext
    page: Page

    @classmethod
    def setUpClass(cls) -> None:
        os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
        super().setUpClass()
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.browser.close()
        cls.playwright.stop()
        super().tearDownClass()
        if "DJANGO_ALLOW_ASYNC_UNSAFE" in os.environ:
            del os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"]

    def setUp(self) -> None:
        super().setUp()
        self.context = self.browser.new_context()
        self.page = self.context.new_page()

    def tearDown(self) -> None:
        self.page.close()
        self.context.close()
        super().tearDown()

    def wait_for_htmx(self) -> None:
        """Wait for HTMX requests to complete."""
        # Wait a bit for htmx to start the request
        self.page.wait_for_timeout(200)
        self.page.wait_for_selector('.htmx-requesting', state='detached')
