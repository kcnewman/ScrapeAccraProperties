import csv
import pathlib
import threading
import time
import scrapy

from scrapy import signals
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table
from rich import box

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]

console = Console()

_progress = Progress(
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

_lock = threading.Lock()
_csv_lock = threading.Lock()
_active_spiders = 0
_progress_started = False


def _start_progress():
    global _progress_started
    with _lock:
        if not _progress_started:
            _progress.start()
            _progress_started = True


def _stop_progress():
    global _progress_started, _active_spiders
    with _lock:
        if _active_spiders == 0 and _progress_started:
            _progress.stop()
            _progress_started = False


class PropertyBaseSpider(scrapy.Spider):
    OUTPUT_CSV: pathlib.Path
    URL_FIELD: str = "url"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_time_ts = time.time()
        self.scraped_count = 0
        self.failures = 0
        self._seen_urls: set[str] = set()
        self._task_id = None

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super().from_crawler(crawler, *args, **kwargs)
        crawler.signals.connect(spider._opened, signal=signals.spider_opened)
        crawler.signals.connect(spider._closed, signal=signals.spider_closed)
        return spider

    def _opened(self, spider):
        global _active_spiders
        _start_progress()
        with _lock:
            _active_spiders += 1
        self._task_id = _progress.add_task(
            self.name.upper(), total=None, scraped=0, speed=0.0, errors=0, page=""
        )
        _progress.console.print(f"[cyan]▶ Starting {self.name.upper()}[/]")

    def _closed(self, spider, reason):
        global _active_spiders
        if self._task_id is not None:
            _progress.update(self._task_id, description=f"[dim]✅ {self.name.upper()}[/]")
        with _lock:
            _active_spiders -= 1
        _stop_progress()
        self._print_summary()

    def save_item(self, item: dict):
        output_csv = getattr(self, "OUTPUT_CSV", None)
        if not output_csv:
            return

        url_key = getattr(self, "URL_FIELD", "url")
        url_val = str(item.get(url_key, "")).strip()

        if url_val and url_val in self._seen_urls:
            return
        if url_val:
            self._seen_urls.add(url_val)

        output_csv.parent.mkdir(parents=True, exist_ok=True)

        with _csv_lock:
            file_exists = output_csv.exists() and output_csv.stat().st_size > 0
            with open(output_csv, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=item.keys(), extrasaction="ignore")
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
        _progress.update(
            self._task_id,
            scraped=self.scraped_count,
            speed=speed,
            errors=self.failures,
            page=page_text,
        )

    def _print_summary(self):
        duration = time.time() - self.start_time_ts
        mins, secs = divmod(int(duration), 60)
        t = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
        t.add_column(style="dim")
        t.add_column(style="bold")
        t.add_row("Spider", f"[cyan]{self.name.upper()}[/]")
        t.add_row("Scraped", f"[green]{self.scraped_count:,}[/]")
        t.add_row("Errors", f"[red]{self.failures}[/]")
        t.add_row("Duration", f"{mins}m {secs}s")
        console.print(Panel(t, title="[bold]🏁 Complete[/]", border_style="green", expand=False))

    async def errback_close_page(self, failure):
        self.failures += 1
        page = failure.request.meta.get("playwright_page")
        if page:
            await page.close()
