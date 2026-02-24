import math
import re
from datetime import datetime
from pathlib import Path

import scrapy
from scrapy_playwright.page import PageMethod

from .base_spider import PropertyBaseSpider

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PAGE_URL = "https://jiji.com.gh/greater-accra/houses-apartments-for-rent?page={}"
LISTINGS_PER_PAGE = 20


class JijiUrlSpider(PropertyBaseSpider):
    name = "jiji_urls"
    OUTPUT_CSV = PROJECT_ROOT / "outputs" / "urls" / "jiji_urls.csv"
    URL_FIELD = "url"

    def __init__(
        self, start_page=1, max_pages=None, total_listing=None, *args, **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.start_page = int(start_page)
        self.max_pages = (
            math.ceil(int(total_listing) / LISTINGS_PER_PAGE)
            if total_listing
            else (int(max_pages) if max_pages else None)
        )
        self.total_count = self.max_pages
        self._detected = False

    def start_requests(self):
        if self.max_pages:
            yield from (
                self._make_request(p)
                for p in range(self.start_page, self.start_page + self.max_pages)
            )
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
                    PageMethod(
                        "wait_for_selector", "div.b-advert-listing", timeout=15000
                    )
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
            if count_text := response.css(
                'div.b-breadcrumb-link--current-url span[property="name"]::text'
            ).get():
                if match := re.search(r"([\d,]+)\s+results", count_text):
                    total = int(match.group(1).replace(",", ""))
                    self.max_pages = math.ceil(total / LISTINGS_PER_PAGE)
                    self.total_count = self.max_pages
                    self.logger.info(
                        f"🔍 Jiji: {total:,} results (~{self.max_pages} pages)"
                    )
                    yield from (
                        self._make_request(p)
                        for p in range(
                            self.start_page + 1, self.start_page + self.max_pages
                        )
                    )

        today = datetime.now().strftime("%Y-%m-%d")
        for href in response.css("div.b-advert-listing a::attr(href)").getall():
            href = href.strip()
            self.save_item(
                {"url": response.urljoin(href), "page": curr_page, "fetch_date": today}
            )
            self.scraped_count += 1

        self.update_ui(current_page=curr_page, total_pages=self.max_pages)
