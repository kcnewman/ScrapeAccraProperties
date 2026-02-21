import scrapy
import time
import sys
from scrapy import signals


class PropertyBaseSpider(scrapy.Spider):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_time_ts = time.time()
        self.scraped_count = 0
        self.failures = 0

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super().from_crawler(crawler, *args, **kwargs)
        crawler.signals.connect(spider.base_spider_opened, signal=signals.spider_opened)
        crawler.signals.connect(spider.base_spider_closed, signal=signals.spider_closed)
        return spider

    def base_spider_opened(self, spider):
        print(f"\n🚀 {self.name.upper()} started...")

    def base_spider_closed(self, spider, reason):
        self.update_ui(force=True)
        duration = time.time() - self.start_time_ts
        print(f"\n\n{'=' * 40}")
        print(f"🏁 FINISHED: {self.name.upper()}")
        print(f"✅ Successful: {self.scraped_count}")
        print(f"❌ Failures:   {self.failures}")
        print(f"⏱️  Duration:   {duration / 60:.1f} minutes")
        print(f"{'=' * 40}\n")

    def update_ui(self, current_page=None, total_pages=None, force=False):
        """Universal UI logic shared by all spiders."""
        elapsed = time.time() - self.start_time_ts
        speed = (self.scraped_count / elapsed) * 60 if elapsed > 0 else 0

        page_ctx = f"[{current_page}/{total_pages or '?'}]" if current_page else ""

        sys.stdout.write(
            f"\r⏳ Progress: {page_ctx} | 🔗 Scraped: {self.scraped_count} "
            f"| ⚡ Speed: {speed:.0f} items/min    "
        )
        sys.stdout.flush()

    async def errback_close_page(self, failure):
        self.failures += 1
        page = failure.request.meta.get("playwright_page")
        if page:
            await page.close()
