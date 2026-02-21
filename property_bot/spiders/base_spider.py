import scrapy
import time
import sys
from scrapy import signals


class PropertyBaseSpider(scrapy.Spider):
    """Base class to handle shared Terminal UI and stats tracking."""

    def __init__(self, *args, **kwargs):
        super(PropertyBaseSpider, self).__init__(*args, **kwargs)
        self.start_time_ts = time.time()
        self.scraped_count = 0
        self.failures = 0

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super(PropertyBaseSpider, cls).from_crawler(crawler, *args, **kwargs)
        crawler.signals.connect(spider.base_spider_opened, signal=signals.spider_opened)
        crawler.signals.connect(spider.base_spider_closed, signal=signals.spider_closed)
        return spider

    def base_spider_opened(self, spider):
        print(f"\n Starting {self.name}...")

    def base_spider_closed(self, spider, reason):
        self.print_progress(force=True)
        duration = time.time() - self.start_time_ts
        print(f"\n\n{'=' * 40}")
        print(f" {self.name.upper()} DONE")
        print(f" Successful: {self.scraped_count}")
        print(f" Failures:   {self.failures}")
        print(f" Duration:   {duration / 60:.1f} minutes")
        print(f"{'=' * 40}\n")

    def print_progress(self, total=None, force=False):
        """Your exact UI logic, unified for all spiders."""
        elapsed = time.time() - self.start_time_ts
        speed = (self.scraped_count / elapsed) * 60 if elapsed > 0 else 0

        # Build the string
        progress_str = f"\r {self.name.capitalize()} Progress: [{self.scraped_count}]"
        if total:
            progress_str = (
                f"\r {self.name.capitalize()} Progress: [{self.scraped_count}/{total}]"
            )

        sys.stdout.write(f"{progress_str} | ⚡ Speed: {speed:.0f} items/min   ")
        sys.stdout.flush()
