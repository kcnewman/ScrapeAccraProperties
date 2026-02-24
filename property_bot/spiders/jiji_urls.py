import math
import pathlib
import re
import scrapy

from scrapy_playwright.page import PageMethod
from datetime import datetime
from .base_spider import PropertyBaseSpider

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
PAGE_URL = "https://jiji.com.gh/greater-accra/houses-apartments-for-rent?page={}"
LISTINGS_PER_PAGE = 20


class JijiUrlSpider(PropertyBaseSpider):
    name = "jiji_urls"
    OUTPUT_CSV = PROJECT_ROOT / "outputs" / "urls" / "jiji_urls.csv"
    URL_FIELD = "url"

    def __init__(self, start_page=1, max_pages=None, total_listing=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_page = int(start_page)
        self.max_pages = int(max_pages) if max_pages else None
        if total_listing:
            self.max_pages = math.ceil(int(total_listing) / LISTINGS_PER_PAGE)
        self.total_count = self.max_pages
        self._detected = False

    def start_requests(self):
        if self.max_pages:
            for page in range(self.start_page, self.start_page + self.max_pages):
                yield self._make_request(page)
        else:
            yield self._make_request(self.start_page, is_detector=True)

    def _make_request(self, page_num, is_detector=False):
        return scrapy.Request(
            url=PAGE_URL.format(page_num),
            meta={
                "playwright": True,
                "playwright_context": "jiji_urls",
                "playwright_page_goto_kwargs": {"wait_until": "domcontentloaded"},
                "playwright_page_methods": [
                    PageMethod("wait_for_selector", "div.b-advert-listing", timeout=15000),
                ],
                "current_page": page_num,
                "is_detector": is_detector,
            },
            callback=self.parse,
            errback=self.errback_close_page,
            dont_filter=True,
        )

    def parse(self, response):
        curr_page = response.meta["current_page"]

        if response.meta.get("is_detector") and not self._detected:
            self._detected = True
            count_text = response.css(
                'div.b-breadcrumb-link--current-url span[property="name"]::text'
            ).get()
            if count_text:
                match = re.search(r"([\d,]+)\s+results", count_text)
                if match:
                    total = int(match.group(1).replace(",", ""))
                    self.max_pages = math.ceil(total / LISTINGS_PER_PAGE)
                    self.total_count = self.max_pages
                    _progress_print = f"🔍 Jiji: {total:,} results (~{self.max_pages} pages)"
                    self.logger.info(_progress_print)
                    for p in range(self.start_page + 1, self.start_page + self.max_pages):
                        yield self._make_request(p)

        today = datetime.now().strftime("%Y-%m-%d")
        for href in response.css("div.b-advert-listing a::attr(href)").getall():
            item = {
                "url": response.urljoin(href),
                "page": curr_page,
                "fetch_date": today,
            }
            self.save_item(item)
            self.scraped_count += 1

        self.update_ui(current_page=curr_page, total_pages=self.max_pages)
