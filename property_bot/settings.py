import sys
import asyncio
import warnings
import logging
import pathlib

BOT_NAME = "property_bot"
SPIDER_MODULES = ["property_bot.spiders"]
NEWSPIDER_MODULE = "property_bot.spiders"

ADDONS = {}
ROBOTSTXT_OBEY = True

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

warnings.filterwarnings("ignore", category=RuntimeWarning, module="asyncio")

LOG_ENABLED = False
LOG_LEVEL = "ERROR"
TELNETCONSOLE_ENABLED = False
logging.getLogger("asyncio").setLevel(logging.CRITICAL)
logging.getLogger("scrapy").setLevel(logging.ERROR)
logging.getLogger("playwright").setLevel(logging.ERROR)

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
(PROJECT_ROOT / "outputs" / "urls").mkdir(parents=True, exist_ok=True)
(PROJECT_ROOT / "outputs" / "data").mkdir(parents=True, exist_ok=True)

DOWNLOAD_HANDLERS = {
    "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
}
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"

PLAYWRIGHT_BROWSER_TYPE = "chromium"
PLAYWRIGHT_LAUNCH_OPTIONS = {
    "headless": True,
    "args": [
        "--disable-gpu",
        "--disable-dev-shm-usage",
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-extensions",
        "--blink-settings=imagesEnabled=false",
    ],
}

_CTX = {
    "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "viewport": {"width": 1280, "height": 720},
    "ignore_https_errors": True,
    "bypass_csp": True,
    "java_script_enabled": True,
    "accept_downloads": False,
}

PLAYWRIGHT_CONTEXTS = {
    "jiji_urls": _CTX,
    "jiji_listings": _CTX,
    "meqasa_urls": _CTX,
    "meqasa_listings": _CTX,
}

PLAYWRIGHT_MAX_CONTEXTS = 10
PLAYWRIGHT_MAX_PAGES_PER_CONTEXT = 12


def should_abort_request(req):
    return req.resource_type in {"image", "media", "font", "stylesheet", "other"}


PLAYWRIGHT_ABORT_REQUEST = should_abort_request
PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT = 25000

CONCURRENT_REQUESTS = 32
CONCURRENT_REQUESTS_PER_DOMAIN = 32
DOWNLOAD_DELAY = 0.5
DOWNLOAD_TIMEOUT = 35

AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 0.5
AUTOTHROTTLE_MAX_DELAY = 5
AUTOTHROTTLE_TARGET_CONCURRENCY = 16

RETRY_TIMES = 3
RETRY_HTTP_CODES = [500, 502, 503, 504, 408, 429, 403]
COOKIES_ENABLED = False
