import asyncio
import csv
from datetime import datetime
from pathlib import Path

import scrapy

from .base_spider import PropertyBaseSpider

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class JijiListingSpider(PropertyBaseSpider):
    name = "jiji_listings"
    OUTPUT_CSV = PROJECT_ROOT / "outputs" / "data" / "jiji_data.csv"
    URL_FIELD = "url"
    OUTPUT_FIELDS = (
        "url",
        "fetch_date",
        "title",
        "location",
        "house_type",
        "bedrooms",
        "bathrooms",
        "price",
        "properties",
        "amenities",
        "description",
    )

    def __init__(self, csv_path="outputs/urls/jiji_urls.csv", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.csv_path = (
            Path(csv_path) if Path(csv_path).is_absolute() else PROJECT_ROOT / csv_path
        )
        self.urls = self._load_urls()
        self.total_count = len(self.urls)

    def _load_urls(self):
        today = datetime.now().strftime("%Y-%m-%d")
        urls = []
        if self.csv_path.exists():
            with open(self.csv_path, "r", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    if url := row.get("url", "").strip():
                        urls.append(
                            {"url": url, "fetch_date": row.get("fetch_date") or today}
                        )
        return urls

    def start_requests(self):
        for entry in self.urls:
            yield scrapy.Request(
                entry["url"],
                meta={
                    "playwright": True,
                    "playwright_context": "jiji_listings",
                    "playwright_page_goto_kwargs": {
                        "wait_until": "domcontentloaded",
                        "timeout": 30000,
                    },
                    "playwright_include_page": True,
                    "fetch_date": entry["fetch_date"],
                },
                callback=self.parse,
                errback=self.errback_close_page,
            )

    async def parse(self, response):
        page = response.meta.get("playwright_page")
        try:
            properties = {
                prop.css(".b-advert-attribute__key::text")
                .get("")
                .strip()
                .rstrip(":"): prop.css(".b-advert-attribute__value::text")
                .get("")
                .strip()
                for prop in response.css(".b-advert-attribute")
                if prop.css(".b-advert-attribute__key::text").get()
            }

            house_type, bathrooms, bedrooms = None, None, None
            for detail in response.css(
                ".b-advert-icon-attribute span::text, .b-advert-icon-attribute__value::text"
            ).getall():
                dl = detail.lower()
                if "bed" in dl:
                    bedrooms = detail.strip()
                elif "bath" in dl:
                    bathrooms = detail.strip()
                elif not house_type:
                    house_type = detail.strip()

            amenities = []
            if page:
                try:
                    if await asyncio.wait_for(
                        page.query_selector(".b-advert-attributes--tags"), timeout=1.5
                    ):
                        elements = await page.query_selector_all(
                            ".b-advert-attributes__tag"
                        )
                        texts = await asyncio.gather(
                            *[el.text_content() for el in elements],
                            return_exceptions=True,
                        )
                        amenities = [
                            t.strip() for t in texts if isinstance(t, str) and t.strip()
                        ]
                except Exception:
                    pass

            self.save_item(
                {
                    "url": response.url,
                    "fetch_date": response.meta.get("fetch_date")
                    or datetime.now().strftime("%Y-%m-%d"),
                    "title": response.css(
                        "h1 div::text, .b-advert-title-outer h1::text"
                    )
                    .get("")
                    .strip()
                    or None,
                    "location": response.css(".b-advert-info-statistics--region::text")
                    .get("")
                    .strip()
                    or None,
                    "house_type": house_type
                    or properties.get("Subtype")
                    or properties.get("Type"),
                    "bedrooms": bedrooms or properties.get("Bedrooms"),
                    "bathrooms": bathrooms
                    or properties.get("Bathrooms")
                    or properties.get("Toilets"),
                    "price": response.css(
                        ".b-alt-advert-price-wrapper span.qa-advert-price-view-value::text, .b-alt-advert-price-wrapper .qa-advert-price::text, .b-alt-advert-price-wrapper div::text"
                    )
                    .get("")
                    .strip()
                    or None,
                    "properties": properties,
                    "amenities": amenities,
                    "description": response.css(".qa-description-text::text")
                    .get("")
                    .strip()
                    or None,
                }
            )

            self.scraped_count += 1
            self.update_ui(
                current_page=self.scraped_count, total_pages=self.total_count
            )

        except Exception as e:
            self.failures += 1
            self.logger.error(f"Error parsing {response.url}: {e}")
        finally:
            if page:
                await page.close()
