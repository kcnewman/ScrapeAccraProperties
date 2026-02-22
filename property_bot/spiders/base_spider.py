import csv
import pathlib
import select
import sys
import termios
import threading
import time
import tty
import scrapy

from scrapy import signals
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
    TaskID,
)
from rich.table import Table
from rich import box

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
JOBS_DIR = PROJECT_ROOT / "outputs" / "jobs"
PAUSE_KEY = "\x10"  # Ctrl+P

console = Console()

_progress = Progress(
    SpinnerColumn(),
    TextColumn("[cyan bold]{task.description:<20}"),
    TextColumn("[green]{task.fields[scraped]:>6,} scraped"),
    TextColumn("[yellow]{task.fields[speed]:>5.0f}/min"),
    TextColumn("[red]{task.fields[errors]:>2} err"),
    TextColumn("[dim]{task.fields[page]:<10}"),
    TimeElapsedColumn(),
    console=console,
    transient=False,
    refresh_per_second=10,
)

_progress_lock = threading.Lock()
_active_spiders = 0
_progress_started = False


def _ensure_progress_started():
    global _progress_started
    with _progress_lock:
        if not _progress_started:
            _progress.start()
            _progress_started = True


def _maybe_stop_progress():
    global _progress_started, _active_spiders
    with _progress_lock:
        if _active_spiders == 0 and _progress_started:
            _progress.stop()
            _progress_started = False


class PropertyBaseSpider(scrapy.Spider):
    """
    Base spider with:
      - Ctrl+P pause / resume (always active)
      - Single CSV output with URL dedup on close

    Subclasses declare:
        OUTPUT_CSV = pathlib.Path(...)
        URL_FIELD  = "url"
    """

    OUTPUT_CSV: pathlib.Path
    URL_FIELD: str = "url"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_time_ts = time.time()
        self.scraped_count = 0
        self.failures = 0
        self._paused = False
        self._pause_checker = None
        self._key_listener_thread = None
        self._stop_key_listener = threading.Event()
        self._collected_items: list[dict] = []
        self._task_id: TaskID | None = None

    def _pause_flag_path(self) -> pathlib.Path:
        return JOBS_DIR / self.name / "pause.flag"

    def _toggle_pause(self):
        flag = self._pause_flag_path()
        flag.unlink() if flag.exists() else flag.touch()

    def _key_listener(self):
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            while not self._stop_key_listener.is_set():
                if select.select([sys.stdin], [], [], 0.5)[0]:
                    if sys.stdin.read(1) == PAUSE_KEY:
                        self._toggle_pause()
        except Exception:
            pass
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)

    def _check_pause_flag(self):
        flag = self._pause_flag_path()
        if flag.exists() and not self._paused:
            self._paused = True
            self.crawler.engine.pause()  # type: ignore
            _progress.console.print("[yellow]⏸  Paused — Ctrl+P to resume[/]")
        elif not flag.exists() and self._paused:
            self._paused = False
            self.crawler.engine.unpause()  # type: ignore
            _progress.console.print("[green]▶  Resumed[/]")

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super().from_crawler(crawler, *args, **kwargs)
        crawler.signals.connect(spider.base_spider_opened, signal=signals.spider_opened)
        crawler.signals.connect(spider.base_spider_closed, signal=signals.spider_closed)
        return spider

    def base_spider_opened(self, spider):
        global _active_spiders
        JOBS_DIR.mkdir(parents=True, exist_ok=True)
        (JOBS_DIR / self.name).mkdir(parents=True, exist_ok=True)

        _ensure_progress_started()
        with _progress_lock:
            _active_spiders += 1

        self._task_id = _progress.add_task(
            self.name.upper(),
            total=None,
            scraped=0,
            speed=0.0,
            errors=0,
            page="",
        )

        _progress.console.print(f"[cyan]▶ Starting {self.name.upper()}...[/]")

    def base_spider_closed(self, spider, reason):
        global _active_spiders
        self._stop_key_listener.set()

        if self._task_id is not None:
            _progress.update(
                self._task_id, description=f"[dim]✅ {self.name.upper()}[/]"
            )

        with _progress_lock:
            _active_spiders -= 1

        if _active_spiders <= 0:
            _maybe_stop_progress()

        output_path = getattr(self, "OUTPUT_CSV", None)
        if self._collected_items and output_path:
            self._merge_and_save(self.OUTPUT_CSV, getattr(self, "URL_FIELD", "url"))

        self._print_summary()

    def _merge_and_save(self, output_path: pathlib.Path, url_key: str = "url"):
        existing: dict[str, dict] = {}
        if output_path.exists():
            try:
                with open(output_path, newline="", encoding="utf-8") as f:
                    for row in csv.DictReader(f):
                        k = row.get(url_key, "").strip()
                        if k:
                            existing[k] = row
            except Exception as exc:
                self.logger.warning(f"Could not read {output_path}: {exc}")

        added = 0
        for item in self._collected_items:
            k = str(item.get(url_key, "")).strip()
            if not k:
                continue
            if k not in existing:
                added += 1
            existing[k] = dict(item)

        if not existing:
            return

        all_rows = list(existing.values())
        fieldnames: list[str] = []
        seen: set[str] = set()
        for row in all_rows:
            for field in row:
                if field not in seen:
                    fieldnames.append(field)
                    seen.add(field)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(all_rows)

        console.print(
            f"[green]💾  Saved[/] [bold]{len(all_rows):,}[/] rows "
            f"([cyan]+{added:,} new[/]) → [dim]{output_path}[/]"
        )

    def update_ui(self, current_page=None, total_pages=None):
        if self._task_id is None:
            return
        elapsed = time.time() - self.start_time_ts
        speed = (self.scraped_count / elapsed) * 60 if elapsed > 0 else 0

        # Cleaner page formatting
        p_text = f"p.{current_page}" if current_page else ""
        if total_pages:
            p_text += f"/{total_pages}"

        _progress.update(
            self._task_id,
            scraped=self.scraped_count,
            speed=speed,
            errors=self.failures,
            page=p_text,
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
        console.print(
            Panel(t, title="[bold]🏁 Complete[/]", border_style="green", expand=False)
        )

    async def errback_close_page(self, failure):
        self.failures += 1
        page = failure.request.meta.get("playwright_page")
        if page:
            await page.close()
