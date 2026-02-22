import os
import pathlib
import math
import scrapy
from scrapy_playwright.page import PageMethod
from datetime import datetime
from .base_spider import PropertyBaseSpider

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
SAVE_DIR = PROJECT_ROOT / "outputs" / "urls"
SAVE_DIR.mkdir(parents=True, exist_ok=True)


class JijiUrlSpider(PropertyBaseSpider):
    name = "jiji_urls"

    custom_settings = {
        "FEEDS": {
            os.path.join(
                SAVE_DIR, f"jiji_urls_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            ): {
                "format": "csv",
                "fields": ["url", "page", "fetch_date"],
                "overwrite": True,
            }
        },
    }

    def __init__(self, url=None, start_page=None, total_listing=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.url = (
            url
            or "https://jiji.com.gh/greater-accra/houses-apartments-for-rent?page={}"
        )
        self.start_page = int(start_page) if start_page else 1
        self.total_listing = int(total_listing) if total_listing else 20
        self.max_page = self.start_page + math.ceil(self.total_listing / 20) - 1
        self.total_count = self.max_page - self.start_page + 1

    def start_requests(self):
        for page in range(self.start_page, self.max_page + 1):
            yield scrapy.Request(
                url=self.url.format(page),
                meta={
                    "playwright": True,
                    "playwright_page_methods": [
                        PageMethod(
                            "wait_for_selector", "div.b-advert-listing", timeout=30000
                        ),
                    ],
                    "current_page": page,
                },
                callback=self.parse,
                errback=self.errback_close_page,
                dont_filter=True,
            )

    def parse(self, response):
        curr_page = response.meta["current_page"]
        today = datetime.now().strftime("%Y-%m-%d")

        for href in response.css("div.b-advert-listing a::attr(href)").getall():
            self.scraped_count += 1
            if self.scraped_count % 200 == 0:
                self.update_ui(current_page=curr_page, total_pages=self.total_count)

            yield {
                "url": response.urljoin(href),
                "page": curr_page,
                "fetch_date": today,
            }
