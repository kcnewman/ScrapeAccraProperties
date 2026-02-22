import math
import pathlib
import sys
import re
import scrapy
from scrapy_playwright.page import PageMethod
from datetime import datetime
from .base_spider import PropertyBaseSpider

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
BASE_URL = "https://meqasa.com/properties-for-rent-in-Greater%20Accra-region?w={}"
LISTINGS_PER_PAGE = 16


class MeqasaUrlSpider(PropertyBaseSpider):
    name = "meqasa_urls"
    OUTPUT_CSV = PROJECT_ROOT / "outputs" / "urls" / "meqasa_urls.csv"
    URL_FIELD = "url"

    def __init__(self, start_page=1, total_pages=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_page = int(start_page) if start_page else 1
        self.total_pages = int(total_pages) if total_pages else None
        self.total_count = self.total_pages
        self._detected = False

    def start_requests(self):
        if self.total_pages:
            for page in range(self.start_page, self.start_page + self.total_pages):
                yield self._make_request(page)
            return

        yield self._make_request(self.start_page, is_detector=True)

    def _make_request(self, page_num, is_detector=False):
        return scrapy.Request(
            url=BASE_URL.format(page_num),
            meta={
                "playwright": True,
                "playwright_page_goto_kwargs": {"wait_until": "domcontentloaded"},
                "playwright_page_methods": [
                    PageMethod(
                        "wait_for_selector", ".mqs-prop-dt-wrapper", timeout=15000
                    ),
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
            raw_count = response.css("#headfiltercount::text").get()

            if raw_count:
                total_listings = int(re.sub(r"[^\d]", "", raw_count))
                detected_pages = math.ceil(total_listings / LISTINGS_PER_PAGE)

                self.total_pages = detected_pages
                self.total_count = detected_pages

                sys.stdout.write(
                    f"\r\033[2K🔍  Meqasa: {total_listings:,} listings found (~{detected_pages} pages)\n"
                )
                sys.stdout.flush()

                if detected_pages > self.start_page:
                    for p in range(
                        self.start_page + 1, self.start_page + detected_pages
                    ):
                        yield self._make_request(p)

        today = datetime.now().strftime("%Y-%m-%d")
        listings = response.css(".mqs-prop-dt-wrapper")

        for listing in listings:
            href = listing.css("a::attr(href)").get()
            if not href:
                continue

            self.scraped_count += 1
            self._collected_items.append(
                {
                    "url": response.urljoin(href),
                    "page": curr_page,
                    "fetch_date": today,
                }
            )

        if self.scraped_count % 4 == 0:
            self.update_ui(current_page=curr_page, total_pages=self.total_pages)
