import csv
import threading
import time
from pathlib import Path

import scrapy
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table
from scrapy import signals

PROJECT_ROOT = Path(__file__).resolve().parents[2]
console = Console()


class SpiderProgressTracker:
    def __init__(self):
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[cyan bold]{task.description:<22}"),
            TextColumn("[green]{task.fields[scraped]:>6,} scraped"),
            TextColumn("[yellow]{task.fields[speed]:>5.0f}/min"),
            TextColumn("[red]{task.fields[errors]:>2} err"),
            TextColumn("[dim]{task.fields[page]:<10}"),
            TimeElapsedColumn(),
            console=console,
            transient=False,
            refresh_per_second=10,
        )
        self.lock = threading.Lock()
        self.csv_lock = threading.Lock()
        self.active_spiders = 0
        self.started = False

    def start(self):
        with self.lock:
            if not self.started:
                self.progress.start()
                self.started = True

    def stop(self):
        with self.lock:
            if self.active_spiders <= 0 and self.started:
                self.progress.stop()
                self.started = False


tracker = SpiderProgressTracker()


class PropertyBaseSpider(scrapy.Spider):
    OUTPUT_CSV: Path
    URL_FIELD: str = "url"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_time_ts = time.time()
        self.scraped_count = 0
        self.failures = 0
        self._seen_urls = set()
        self._task_id = None

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super().from_crawler(crawler, *args, **kwargs)
        crawler.signals.connect(spider._opened, signal=signals.spider_opened)
        crawler.signals.connect(spider._closed, signal=signals.spider_closed)
        return spider

    def _opened(self, spider):
        if hasattr(self, "OUTPUT_CSV") and self.OUTPUT_CSV.exists():
            try:
                with open(self.OUTPUT_CSV, newline="", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        try:
                            val = row.get(self.URL_FIELD, "").strip()
                            if val:
                                self._seen_urls.add(val)
                        except Exception:
                            continue
            except Exception:
                pass

        tracker.start()
        with tracker.lock:
            tracker.active_spiders += 1

        self._task_id = tracker.progress.add_task(
            self.name.upper(), total=None, scraped=0, speed=0.0, errors=0, page=""
        )
        tracker.progress.console.print(
            f"[cyan]▶ Starting {self.name.upper()} ({len(self._seen_urls):,} already in CSV)[/]"
        )

    def _closed(self, spider, reason):
        if self._task_id is not None:
            tracker.progress.update(
                self._task_id, description=f"[dim]✅ {self.name.upper()}[/]"
            )
        with tracker.lock:
            tracker.active_spiders -= 1
        tracker.stop()
        self._print_summary()

    def save_item(self, item: dict):
        if not hasattr(self, "OUTPUT_CSV"):
            return

        url_val = str(item.get(self.URL_FIELD, "")).strip()

        with tracker.csv_lock:
            if url_val and url_val in self._seen_urls:
                return
            if url_val:
                self._seen_urls.add(url_val)

            self.OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
            file_exists = (
                self.OUTPUT_CSV.exists() and self.OUTPUT_CSV.stat().st_size > 0
            )
            with open(self.OUTPUT_CSV, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(
                    f, fieldnames=item.keys(), extrasaction="ignore",
                    quoting=csv.QUOTE_ALL,
                )
                if not file_exists:
                    writer.writeheader()
                writer.writerow(item)

    def update_ui(self, current_page=None, total_pages=None):
        if self._task_id is None:
            return

        elapsed = time.time() - self.start_time_ts
        speed = (self.scraped_count / elapsed) * 60 if elapsed > 0 else 0

        page_text = f"p.{current_page}" if current_page else ""
        if total_pages:
            page_text += f"/{total_pages}"

        tracker.progress.update(
            self._task_id,
            scraped=self.scraped_count,
            speed=speed,
            errors=self.failures,
            page=page_text,
        )

    def _print_summary(self):
        mins, secs = divmod(int(time.time() - self.start_time_ts), 60)
        t = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
        t.add_column(style="dim")
        t.add_column(style="bold")
        t.add_row("Spider", f"[cyan]{self.name.upper()}[/]")
        t.add_row("Scraped", f"[green]{self.scraped_count:,}[/]")
        t.add_row("Errors", f"[red]{self.failures}[/]")
        t.add_row("Duration", f"{mins}m {secs}s")
        console.print(
            Panel(t, title="[bold] Complete[/]", border_style="green", expand=False)
        )

    async def errback_close_page(self, failure):
        self.failures += 1
        if page := failure.request.meta.get("playwright_page"):
            await page.close()
