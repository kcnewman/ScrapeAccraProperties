import csv
from datetime import datetime
from pathlib import Path

import scrapy
from scrapy_playwright.page import PageMethod

from .base_spider import PropertyBaseSpider

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class MeqasaListingSpider(PropertyBaseSpider):
    name = "meqasa_listings"
    OUTPUT_CSV = PROJECT_ROOT / "outputs" / "data" / "meqasa_data.csv"
    URL_FIELD = "URL"

    def __init__(self, csv_path="outputs/urls/meqasa_urls.csv", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.csv_path = (
            Path(csv_path) if Path(csv_path).is_absolute() else PROJECT_ROOT / csv_path
        )
        self.urls = self._load_urls()
        self.total_count = len(self.urls)

    def _load_urls(self):
        if not self.csv_path.exists():
            return []
        with open(self.csv_path, "r", encoding="utf-8") as f:
            return [row["url"] for row in csv.DictReader(f) if row.get("url")]

    def start_requests(self):
        if not self.urls:
            self.logger.error(f"No URLs found in {self.csv_path}")
            return

        for url in self.urls:
            yield scrapy.Request(
                url,
                meta={
                    "playwright": True,
                    "playwright_context": "meqasa_listings",
                    "playwright_page_methods": [
                        PageMethod("wait_for_selector", "table.table", timeout=10000)
                    ],
                },
                callback=self.parse,
                errback=self.errback_close_page,
            )

    def parse(self, response):
        try:
            data = {
                "URL": response.url,
                "Title": response.css("h1::text").get("").strip(),
                "Price": response.css(".price-wrapper > div:nth-child(1)::text")
                .get("")
                .strip(),
                "Rate": response.css(".price-wrapper > div:nth-child(2)::text")
                .get("")
                .strip(),
                "Description": (
                    response.css(".description p::text").get() or ""
                ).strip(),
                "fetch_date": datetime.now().strftime("%Y-%m-%d"),
            }

            for row in response.css("table.table tr"):
                if header := row.css(
                    "td[style*='font-weight: bold']::text, th::text"
                ).get():
                    values = row.css(
                        "td:nth-child(2) ::text, td:nth-child(2) li::text"
                    ).getall()
                    data[header.strip().rstrip(":")] = ", ".join(
                        v.strip() for v in values if v.strip()
                    )

            self.save_item(data)
            self.scraped_count += 1
            self.update_ui(
                current_page=self.scraped_count, total_pages=self.total_count
            )

        except Exception as e:
            self.failures += 1
            self.logger.error(f"Error parsing {response.url}: {e}")
