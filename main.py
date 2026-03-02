from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from scrapy.crawler import CrawlerProcess
from scrapy.spiders import Spider
from scrapy.utils.project import get_project_settings

from property_bot.spiders.jiji_listing import JijiListingSpider
from property_bot.spiders.jiji_urls import JijiUrlSpider
from property_bot.spiders.meqasa_listing import MeqasaListingSpider
from property_bot.spiders.meqasa_urls import MeqasaUrlSpider

os.environ.setdefault("SCRAPY_SETTINGS_MODULE", "property_bot.settings")

PROJECT_ROOT = Path(__file__).resolve().parent
JIJI_RAW_OUTPUT_CSV = PROJECT_ROOT / "outputs" / "data" / "raw.csv"
console = Console()


@dataclass(frozen=True)
class SiteConfig:
    key: str
    label: str
    url_spider: type[Spider]
    listing_spider: type[Spider]
    urls_csv: Path
    data_csv: Path
    resume_queue_csv: Path


SITE_CONFIGS: dict[str, SiteConfig] = {
    "jiji": SiteConfig(
        key="jiji",
        label="Jiji",
        url_spider=JijiUrlSpider,
        listing_spider=JijiListingSpider,
        urls_csv=PROJECT_ROOT / "outputs" / "urls" / "jiji_urls.csv",
        data_csv=PROJECT_ROOT / "outputs" / "data" / "jiji_data.csv",
        resume_queue_csv=PROJECT_ROOT / "outputs" / "urls" / "jiji_resume_queue.csv",
    ),
    "meqasa": SiteConfig(
        key="meqasa",
        label="Meqasa",
        url_spider=MeqasaUrlSpider,
        listing_spider=MeqasaListingSpider,
        urls_csv=PROJECT_ROOT / "outputs" / "urls" / "meqasa_urls.csv",
        data_csv=PROJECT_ROOT / "outputs" / "data" / "meqasa_data.csv",
        resume_queue_csv=PROJECT_ROOT / "outputs" / "urls" / "meqasa_resume_queue.csv",
    ),
}


def relpath(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def ask_choice(prompt: str, options: list[tuple[str, str]], default: str) -> str:
    option_index = {str(i): value for i, (value, _) in enumerate(options, start=1)}
    option_values = {value for value, _ in options}

    while True:
        console.print(f"\n[bold]{prompt}[/]")
        for i, (_, label) in enumerate(options, start=1):
            console.print(f"  [cyan]{i}[/]. {label}")

        default_index = next(
            str(i) for i, (value, _) in enumerate(options, start=1) if value == default
        )
        raw = input(f"Enter choice [{default_index}]: ").strip().lower()

        if not raw:
            return default
        if raw in option_index:
            return option_index[raw]
        if raw in option_values:
            return raw

        console.print("[red]Invalid choice. Try again.[/]")


def ask_yes_no(prompt: str, default: bool = True) -> bool:
    suffix = "Y/n" if default else "y/N"
    while True:
        raw = input(f"{prompt} [{suffix}]: ").strip().lower()
        if not raw:
            return default
        if raw in {"y", "yes"}:
            return True
        if raw in {"n", "no"}:
            return False
        console.print("[red]Please answer y or n.[/]")


def ask_int(prompt: str, default: int, min_value: int = 1) -> int:
    while True:
        raw = input(f"{prompt} [{default}]: ").strip()
        if not raw:
            return default
        try:
            value = int(raw)
            if value < min_value:
                raise ValueError
            return value
        except ValueError:
            console.print(f"[red]Enter an integer >= {min_value}.[/]")


def ask_path(prompt: str, default: Path) -> Path:
    raw = input(f"{prompt} [{relpath(default)}]: ").strip()
    chosen = Path(raw) if raw else default
    return chosen if chosen.is_absolute() else PROJECT_ROOT / chosen


def choose_sites() -> list[SiteConfig]:
    choice = ask_choice(
        "Select source",
        [
            ("jiji", "Jiji only"),
            ("meqasa", "Meqasa only"),
            ("both", "Both Jiji and Meqasa"),
        ],
        default="both",
    )
    if choice == "both":
        return [SITE_CONFIGS["jiji"], SITE_CONFIGS["meqasa"]]
    return [SITE_CONFIGS[choice]]


def read_url_set(path: Path, field_name: str = "url") -> set[str]:
    urls: set[str] = set()
    if not path.exists():
        return urls

    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if url := (row.get(field_name) or "").strip():
                urls.add(url)
    return urls


def build_resume_queue(
    urls_csv: Path, data_csv: Path, queue_csv: Path
) -> tuple[int, int, int]:
    if not urls_csv.exists():
        if queue_csv.exists():
            queue_csv.unlink()
        return (0, 0, 0)

    with open(urls_csv, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        if queue_csv.exists():
            queue_csv.unlink()
        return (0, 0, 0)

    scraped_urls = read_url_set(data_csv, "url")
    source_seen: set[str] = set()
    pending_rows: list[dict[str, str]] = []
    fieldnames: list[str] = []

    for row in rows:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(key)

        url = (row.get("url") or "").strip()
        if not url or url in source_seen:
            continue
        source_seen.add(url)
        if url in scraped_urls:
            continue
        pending_rows.append(row)

    source_total = len(source_seen)
    pending_total = len(pending_rows)
    already_scraped = source_total - pending_total

    if pending_total == 0:
        if queue_csv.exists():
            queue_csv.unlink()
        return (source_total, already_scraped, pending_total)

    queue_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(queue_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames,
            extrasaction="ignore",
            quoting=csv.QUOTE_ALL,
        )
        writer.writeheader()
        writer.writerows(pending_rows)

    return (source_total, already_scraped, pending_total)


def run_spiders(jobs: list[tuple[type[Spider], dict[str, Any]]]) -> None:
    if not jobs:
        console.print("[yellow]No spiders queued.[/]")
        return

    process = CrawlerProcess(get_project_settings())
    for spider_cls, kwargs in jobs:
        process.crawl(spider_cls, **kwargs)
    process.start(stop_after_crawl=True)


def run_jiji_cleaning() -> None:
    try:
        from clean import clean_jiji_csv
    except Exception as exc:
        console.print(f"[red]Skipping Jiji cleaning:[/] unable to load clean.py ({exc})")
        return

    jiji_data_csv = SITE_CONFIGS["jiji"].data_csv
    if not jiji_data_csv.exists():
        console.print(
            f"[yellow]Skipping Jiji cleaning: {relpath(jiji_data_csv)} not found.[/]"
        )
        return

    try:
        cleaned_df = clean_jiji_csv(jiji_data_csv, JIJI_RAW_OUTPUT_CSV)
    except Exception as exc:
        console.print(f"[red]Jiji cleaning failed:[/] {exc}")
        return

    console.print(
        f"[green]Jiji cleaned CSV saved:[/] {relpath(JIJI_RAW_OUTPUT_CSV)}"
        f" ({len(cleaned_df):,} rows)"
    )


def prompt_jiji_url_args() -> dict[str, Any]:
    start_page = ask_int("Jiji start page", default=1, min_value=1)
    mode = ask_choice(
        "Jiji URL mode",
        [
            ("auto", "Auto detect total pages"),
            ("max_pages", "Fixed number of pages"),
            ("total_listing", "Convert expected listings to page count"),
        ],
        default="auto",
    )

    args: dict[str, Any] = {"start_page": start_page}
    if mode == "max_pages":
        args["max_pages"] = ask_int("Jiji max pages", default=5, min_value=1)
    elif mode == "total_listing":
        args["total_listing"] = ask_int(
            "Jiji expected total listings", default=100, min_value=1
        )
    return args


def prompt_meqasa_url_args() -> dict[str, Any]:
    start_page = ask_int("Meqasa start page", default=1, min_value=1)
    mode = ask_choice(
        "Meqasa URL mode",
        [
            ("auto", "Auto detect total pages"),
            ("total_pages", "Fixed number of pages"),
        ],
        default="auto",
    )

    args: dict[str, Any] = {"start_page": start_page}
    if mode == "total_pages":
        args["total_pages"] = ask_int("Meqasa total pages", default=5, min_value=1)
    return args


def run_url_collection() -> None:
    sites = choose_sites()
    jobs: list[tuple[type[Spider], dict[str, Any]]] = []

    for site in sites:
        args = (
            prompt_jiji_url_args() if site.key == "jiji" else prompt_meqasa_url_args()
        )
        jobs.append((site.url_spider, args))

    run_spiders(jobs)


def run_listing_scrape(resume: bool) -> None:
    sites = choose_sites()
    jobs: list[tuple[type[Spider], dict[str, Any]]] = []
    cleanup_paths: list[Path] = []
    jiji_job_scheduled = False

    if resume:
        use_defaults = ask_yes_no(
            "Use default URL/data CSV paths for resume mode?", True
        )
        summary = Table(title="Resume Queue Summary")
        summary.add_column("Source", style="cyan")
        summary.add_column("URL Pool", justify="right")
        summary.add_column("Already Scraped", justify="right")
        summary.add_column("Pending", justify="right", style="green")

        for site in sites:
            urls_csv = (
                site.urls_csv
                if use_defaults
                else ask_path(f"{site.label} URL CSV", site.urls_csv)
            )
            data_csv = (
                site.data_csv
                if use_defaults
                else ask_path(f"{site.label} data CSV", site.data_csv)
            )
            source_total, already_scraped, pending_total = build_resume_queue(
                urls_csv, data_csv, site.resume_queue_csv
            )

            summary.add_row(
                site.label,
                f"{source_total:,}",
                f"{already_scraped:,}",
                f"{pending_total:,}",
            )
            if pending_total > 0:
                jobs.append(
                    (site.listing_spider, {"csv_path": str(site.resume_queue_csv)})
                )
                cleanup_paths.append(site.resume_queue_csv)
                if site.key == "jiji":
                    jiji_job_scheduled = True

        console.print(summary)

    else:
        for site in sites:
            urls_csv = ask_path(f"{site.label} URL CSV", site.urls_csv)
            if not urls_csv.exists():
                console.print(
                    f"[yellow]Skipping {site.label}: {relpath(urls_csv)} not found.[/]"
                )
                continue
            jobs.append((site.listing_spider, {"csv_path": str(urls_csv)}))
            if site.key == "jiji":
                jiji_job_scheduled = True

    try:
        run_spiders(jobs)
    finally:
        for temp_file in cleanup_paths:
            if temp_file.exists():
                temp_file.unlink()

    if jiji_job_scheduled:
        run_jiji_cleaning()


def print_header() -> None:
    console.print(
        Panel.fit(
            "Accra Property Scraper\n"
            "- Interactive multi-spider runner\n"
            "- Listing resume mode queues only missing URLs\n"
            "- CSV writes happen item-by-item during crawl\n"
            "- Jiji listings are cleaned to outputs/data/raw.csv",
            title="main.py",
            border_style="cyan",
        )
    )


def main() -> None:
    print_header()
    action = ask_choice(
        "Choose action",
        [
            ("urls", "Collect listing URLs"),
            ("listings", "Scrape listing details"),
            ("resume", "Resume listing scrape (missing URLs only)"),
            ("exit", "Exit"),
        ],
        default="urls",
    )

    if action == "urls":
        run_url_collection()
    elif action == "listings":
        run_listing_scrape(resume=False)
    elif action == "resume":
        run_listing_scrape(resume=True)

    console.print("[bold green]Done.[/]")


if __name__ == "__main__":
    main()
