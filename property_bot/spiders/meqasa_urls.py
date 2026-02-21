import scrapy
from datetime import datetime
from scrapy_playwright.page import PageMethod
from .base_spider import PropertyBaseSpider


class MeqasaUrlSpider(PropertyBaseSpider):
    name = "meqasa_urls"

    custom_settings = {
        "FEEDS": {
            f"outputs/urls/meqasa_urls_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv": {
                "format": "csv",
                "fields": ["url", "page", "fetch_date"],
            }
        },
    }

    def __init__(self, start_page=1, total_pages=5, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_page = int(start_page)
        self.total_pages = int(total_pages)

    def start_requests(self):
        for page in range(self.start_page, self.start_page + self.total_pages):
            url = f"https://meqasa.com/properties-for-rent-in-Greater%20Accra-region?w={page}"
            yield scrapy.Request(
                url,
                meta={
                    "playwright": True,
                    "playwright_page_methods": [
                        PageMethod(
                            "wait_for_selector", ".mqs-prop-dt-wrapper", timeout=10000
                        )
                    ],
                    "current_page": page,
                },
                callback=self.parse,
                errback=self.errback_close_page,
            )

    async def parse(self, response):
        curr_page = response.meta["current_page"]
        listings = response.css(".mqs-prop-dt-wrapper")

        for listing in listings:
            href = listing.css("a::attr(href)").get()
            if href:
                self.scraped_count += 1
                if self.scraped_count % 5 == 0:
                    self.update_ui(current_page=curr_page)

                yield {
                    "url": response.urljoin(href),
                    "page": curr_page,
                    "fetch_date": datetime.now().strftime("%Y-%m-%d"),
                }
