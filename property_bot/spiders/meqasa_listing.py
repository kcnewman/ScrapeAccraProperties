import scrapy
import csv
import os
from datetime import datetime
from .base_spider import PropertyBaseSpider
from scrapy_playwright.page import PageMethod


class MeqasaListingSpider(PropertyBaseSpider):
    name = "meqasa_listings"

    custom_settings = {
        "FEEDS": {
            f"outputs/data/meqasa_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv": {
                "format": "csv",
            }
        },
    }

    def __init__(self, csv_path="outputs/urls/meqasa_urls.csv", *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not os.path.isabs(csv_path):
            self.csv_path = os.path.join(os.getcwd(), csv_path)
        else:
            self.csv_path = csv_path

        self.items_to_scrape = self.load_urls()
        self.total_count = len(self.items_to_scrape)

    def load_urls(self):
        urls = []
        if os.path.exists(self.csv_path):
            with open(self.csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                urls = [row["url"] for row in reader if row.get("url")]
        return urls

    def start_requests(self):
        if not self.items_to_scrape:
            self.logger.error(f"❌ No URLs found in {self.csv_path}")
            return

        for url in self.items_to_scrape:
            yield scrapy.Request(
                url,
                meta={
                    "playwright": True,
                    "playwright_include_page": True,
                    "playwright_page_methods": [
                        PageMethod("wait_for_selector", "table.table", timeout=15000)
                    ],
                },
                callback=self.parse,
                errback=self.errback_close_page,
            )

    async def parse(self, response):
        page = response.meta.get("playwright_page")

        try:
            data = {
                "URL": response.url,
                "Title": response.css("h1::text").get("").strip(),
                "Price": response.css("p.h3::text")
                .get("")
                .strip()
                .replace("Price:", "")
                .strip(),
            }

            for row in response.css("table.table tr"):
                header = row.css("td[style*='font-weight: bold']::text, th::text").get()
                value_list = row.css(
                    "td:nth-child(2) ::text, td:nth-child(2) li::text"
                ).getall()

                if header:
                    clean_header = header.strip().rstrip(":")
                    clean_value = ", ".join(
                        [v.strip() for v in value_list if v.strip()]
                    )
                    data[clean_header] = clean_value

            desc = response.css(".description p::text").get()
            data["Description"] = desc.strip() if desc else "Description not found"

            self.scraped_count += 1

            self.update_ui(
                current_page=self.scraped_count, total_pages=self.total_count
            )

            yield data

        except Exception as e:
            self.failures += 1
            self.logger.error(f"Error parsing {response.url}: {str(e)}")

        finally:
            if page:
                await page.close()
