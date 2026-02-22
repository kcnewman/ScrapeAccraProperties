import asyncio
import pathlib
import scrapy
import csv
import os
from scrapy_playwright.page import PageMethod
from datetime import datetime
from .base_spider import PropertyBaseSpider

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]


class JijiListingSpider(PropertyBaseSpider):
    name = "jiji_listings"
    OUTPUT_CSV = PROJECT_ROOT / "outputs" / "data" / "jiji_data.csv"
    URL_FIELD = "url"

    def __init__(self, csv_path="outputs/urls/jiji_urls.csv", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.csv_path = (
            csv_path
            if os.path.isabs(csv_path)
            else os.path.join(PROJECT_ROOT, csv_path)
        )
        self.urls = self._load_urls()
        self.total_count = len(self.urls)

    def _load_urls(self):
        today_str = datetime.now().strftime("%Y-%m-%d")
        urls = []
        try:
            with open(self.csv_path, "r", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    url = row.get("url", "").strip()
                    if not url:
                        continue
                    f_date = row.get("fetch_date", "").strip()
                    if not f_date or f_date.lower() == "nan":
                        f_date = today_str
                    urls.append({"url": url, "fetch_date": f_date})
        except FileNotFoundError:
            pass
        return urls

    def start_requests(self):
        for url_data in self.urls:
            yield scrapy.Request(
                url_data["url"],
                meta={
                    "playwright": True,
                    "playwright_context": "default",
                    "playwright_page_goto_kwargs": {
                        "wait_until": "domcontentloaded",
                        "timeout": 20000,
                    },
                    "playwright_page_methods": [
                        PageMethod("wait_for_selector", "h1", timeout=8000),
                    ],
                    "playwright_include_page": True,
                    "fetch_date": url_data["fetch_date"],
                },
                callback=self.parse,
                errback=self.errback_close_page,
            )

    async def parse(self, response):
        page = response.meta.get("playwright_page")

        try:
            title = response.css("h1 div::text, .b-advert-title-outer h1::text").get()
            location = response.css(".b-advert-info-statistics--region::text").get()

            properties = {}
            for prop in response.css(".b-advert-attribute"):
                key = prop.css(".b-advert-attribute__key::text").get()
                value = prop.css(".b-advert-attribute__value::text").get()
                if key and value:
                    properties[key.strip().rstrip(":")] = value.strip()

            house_type, bathrooms, bedrooms = None, None, None
            for detail in response.css(
                ".b-advert-icon-attribute span::text, .b-advert-icon-attribute__value::text"
            ).getall():
                detail_lower = detail.lower()
                if "bed" in detail_lower:
                    bedrooms = detail.strip()
                elif "bath" in detail_lower:
                    bathrooms = detail.strip()
                elif not house_type:
                    house_type = detail.strip()

            house_type = house_type or properties.get("Subtype") or properties.get("Type")
            bedrooms = bedrooms or properties.get("Bedrooms")
            bathrooms = bathrooms or properties.get("Bathrooms") or properties.get("Toilets")

            amenities = []
            if page:
                try:
                    amenities_section = await asyncio.wait_for(
                        page.query_selector(".b-advert-attributes--tags"), timeout=1.5
                    )
                    if amenities_section:
                        elements = await page.query_selector_all(".b-advert-attributes__tag")
                        texts = await asyncio.gather(
                            *[el.text_content() for el in elements],
                            return_exceptions=True,
                        )
                        amenities = [
                            t.strip() for t in texts if isinstance(t, str) and t.strip()
                        ]
                except Exception:
                    pass

            price = response.css(
                ".b-alt-advert-price-wrapper span.qa-advert-price-view-value::text, "
                ".b-alt-advert-price-wrapper .qa-advert-price::text, "
                ".b-alt-advert-price-wrapper div::text"
            ).get()

            description = response.css(".qa-description-text::text").get()

            item = {
                "url": response.url,
                "fetch_date": response.meta.get("fetch_date") or datetime.now().strftime("%Y-%m-%d"),
                "title": title.strip() if title else None,
                "location": location.strip() if location else None,
                "house_type": house_type,
                "bedrooms": bedrooms,
                "bathrooms": bathrooms,
                "price": price.strip() if price else None,
                "properties": properties,
                "amenities": amenities,
                "description": description.strip() if description else None,
            }
            self._collected_items.append(item)

            self.scraped_count += 1
            if self.scraped_count % 10 == 0:
                self.update_ui(current_page=self.scraped_count, total_pages=self.total_count)

        except Exception as e:
            self.failures += 1
            self.logger.error(f"Error parsing {response.url}: {e}")

        finally:
            if page:
                await page.close()
