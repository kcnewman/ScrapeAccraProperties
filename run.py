#!/usr/bin/env python3
import os
import sys
import time
from pathlib import Path

import pandas as pd

os.environ.setdefault("SCRAPY_SETTINGS_MODULE", "property_bot.settings")
from twisted.internet import asyncioreactor

if "twisted.internet.reactor" not in sys.modules:
    asyncioreactor.install()

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table
from scrapy.crawler import CrawlerRunner
from scrapy.utils.log import configure_logging
from scrapy.utils.project import get_project_settings
from twisted.internet import defer, reactor

from property_bot.spiders.jiji_listing import JijiListingSpider
from property_bot.spiders.jiji_urls import JijiUrlSpider
from property_bot.spiders.meqasa_listing import MeqasaListingSpider
from property_bot.spiders.meqasa_urls import MeqasaUrlSpider

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

console = Console()


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def banner():
    console.print(
        Panel.fit(
            "[cyan bold] Property Scraper[/]\n[dim]Jiji Ghana · Meqasa[/]",
            border_style="cyan",
            padding=(1, 4),
        )
    )
    console.print()


def menu():
    t = Table(show_header=False, box=box.ROUNDED, border_style="dim", padding=(0, 2))
    t.add_column(style="green bold", width=4)
    t.add_column()
    t.add_row("[1]", " Collect listing URLs")
    t.add_row("[2]", " Scrape listing details")
    t.add_row("[3]", " Resume — scrape missing listings")
    t.add_row("[q]", " Quit")
    console.print(t)
    console.print()


def ask(prompt, default=None, cast=None, allow_empty=False):
    while True:
        raw = Prompt.ask(
            f"[yellow]{prompt}[/]",
            default=str(default) if default is not None else None,
            console=console,
        )
        if not raw and not allow_empty and default is None:
            console.print("[red] Please enter a value.[/]")
            continue
        if not raw and allow_empty:
            return None
        if not raw and default is not None:
            return default
        if cast:
            try:
                return cast(raw)
            except ValueError:
                console.print("[red] Invalid input type.[/]")
                continue
        return raw


def summary_table(jobs):
    t = Table(show_header=True, header_style="bold dim", box=box.SIMPLE, padding=(0, 2))
    t.add_column("Spider")
    t.add_column("Parameters")
    for cls, kw in jobs:
        t.add_row(cls.name, str(kw) if kw else "[dim](defaults)[/]")
    console.print(t)


def collect_url_params():
    jobs = []

    console.rule("[cyan bold]Jiji URL Spider[/]", style="dim")
    mode = (
        ask("Mode — (a)uto (f)ixed pages (t)otal listings (s)kip", default="a") or "a"
    ).lower()

    if not mode.startswith("s"):
        jiji = {"start_page": ask("Start page", default=1, cast=int)}
        if mode.startswith("f"):
            jiji["max_pages"] = ask("Max pages", default=10, cast=int)
        elif mode.startswith("t"):
            jiji["total_listing"] = ask("Total listings", default=200, cast=int)

        max_pages = jiji.get("max_pages", 1)
        total_listing = jiji.get("total_listing", 1)
        if (
            isinstance(max_pages, int)
            and max_pages > 0
            and isinstance(total_listing, int)
            and total_listing > 0
        ):
            jobs.append((JijiUrlSpider, jiji))

    console.print()
    console.rule("[cyan bold]Meqasa URL Spider[/]", style="dim")

    if (ask("Run Meqasa? (y/n)", default="y") or "n").lower().startswith("y"):
        tp = ask("Total pages (blank = auto)", default=None, cast=int, allow_empty=True)
        if tp is None or (isinstance(tp, int) and tp > 0):
            meqasa = {"start_page": ask("Start page", default=1, cast=int)}
            if tp:
                meqasa["total_pages"] = tp
            jobs.append((MeqasaUrlSpider, meqasa))

    return jobs


def collect_listing_params():
    jobs = []

    console.rule("[cyan bold]Jiji Listing Spider[/]", style="dim")
    if (ask("Run Jiji listings? (y/n)", default="y") or "n").lower().startswith("y"):
        jobs.append(
            (
                JijiListingSpider,
                {
                    "csv_path": ask(
                        "Jiji URLs CSV", default="outputs/urls/jiji_urls.csv"
                    )
                },
            )
        )

    console.print()
    console.rule("[cyan bold]Meqasa Listing Spider[/]", style="dim")
    if (ask("Run Meqasa listings? (y/n)", default="y") or "n").lower().startswith("y"):
        jobs.append(
            (
                MeqasaListingSpider,
                {
                    "csv_path": ask(
                        "Meqasa URLs CSV", default="outputs/urls/meqasa_urls.csv"
                    )
                },
            )
        )

    return jobs


def build_resume_jobs():
    """
    For each site, diff the URL list against already-scraped data.
    Writes a temp CSV of unscraped URLs and returns spider jobs for those.
    Returns (jobs, temp_files) — caller must delete temp_files after scraping.
    """
    sites = [
        {
            "name": "Jiji",
            "url_csv": PROJECT_ROOT / "outputs" / "urls" / "jiji_urls.csv",
            "data_csv": PROJECT_ROOT / "outputs" / "data" / "jiji_data.csv",
            "url_field": "url",
            "spider": JijiListingSpider,
            "temp": PROJECT_ROOT / "outputs" / "urls" / "jiji_resume_queue.csv",
        },
        {
            "name": "Meqasa",
            "url_csv": PROJECT_ROOT / "outputs" / "urls" / "meqasa_urls.csv",
            "data_csv": PROJECT_ROOT / "outputs" / "data" / "meqasa_data.csv",
            "url_field": "url",
            "spider": MeqasaListingSpider,
            "temp": PROJECT_ROOT / "outputs" / "urls" / "meqasa_resume_queue.csv",
        },
    ]

    jobs, temp_files = [], []

    for site in sites:
        if not site["url_csv"].exists():
            console.print(f"[yellow]  {site['name']}: no URL file found, skipping.[/]")
            continue

        df_urls = pd.read_csv(site["url_csv"])
        url_col = "url"

        if url_col not in df_urls.columns:
            console.print(
                f"[red]  {site['name']}: URL column not found in {site['url_csv'].name}[/]"
            )
            continue

        scraped_urls = set()
        if site["data_csv"].exists():
            try:
                df_data = pd.read_csv(site["data_csv"])
                field = site["url_field"]
                if field in df_data.columns:
                    scraped_urls = set(df_data[field].dropna().str.strip())
            except Exception as e:
                console.print(
                    f"[yellow]  {site['name']}: could not read data CSV — {e}[/]"
                )

        remaining = df_urls[~df_urls[url_col].str.strip().isin(scraped_urls)]

        total = len(df_urls)
        done = total - len(remaining)
        console.print(
            f"  [cyan]{site['name']}:[/] {done:,}/{total:,} scraped — "
            f"[green]{len(remaining):,} remaining[/]"
        )

        if remaining.empty:
            console.print(f"  [dim]{site['name']} is fully scraped.[/]")
            continue

        remaining.to_csv(site["temp"], index=False)
        temp_files.append(site["temp"])
        jobs.append((site["spider"], {"csv_path": str(site["temp"])}))

    return jobs, temp_files


def run_spiders(jobs, temp_files=None):
    configure_logging()
    runner = CrawlerRunner(settings=get_project_settings())

    @defer.inlineCallbacks
    def crawl():
        yield defer.DeferredList(
            [runner.crawl(cls, **kw) for cls, kw in jobs], consumeErrors=True
        )
        reactor.stop()  # type: ignore

    clear_screen()
    console.print(f"\n[green bold] Starting {len(jobs)} spider(s) …[/]\n")
    crawl()
    reactor.run()  # type: ignore

    for f in temp_files or []:
        try:
            Path(f).unlink()
            console.print(f"[dim]  Deleted temp file: {Path(f).name}[/]")
        except Exception:
            pass


def main():
    try:
        while True:
            clear_screen()
            banner()
            menu()
            choice = (ask("Choice", default="q") or "q").lower()

            if choice == "3":
                clear_screen()
                banner()
                console.rule("[bold]Resume Scraper[/]", style="dim")
                console.print()
                jobs, temp_files = build_resume_jobs()

                if not jobs:
                    console.print(
                        "\n[green] All listings are up to date — nothing to resume.[/]"
                    )
                    time.sleep(2)
                    continue

                console.print()
                console.rule("[bold]Summary[/]", style="dim")
                summary_table(jobs)
                console.print()

                if Confirm.ask(
                    "[yellow]Start resuming?[/]", default=True, console=console
                ):
                    run_spiders(jobs, temp_files=temp_files)
                    break

            elif choice in ("1", "2"):
                clear_screen()
                banner()
                jobs = (
                    collect_url_params() if choice == "1" else collect_listing_params()
                )

                if not jobs:
                    console.print("\n[yellow] All spiders skipped — nothing to run.[/]")
                    time.sleep(1.5)
                    continue

                if choice == "2":
                    missing = [
                        f"  {cls.name}: {kw['csv_path']}"
                        for cls, kw in jobs
                        if not Path(kw["csv_path"]).exists()
                    ]
                    if missing:
                        console.print("\n[red] CSV files not found:[/]")
                        for m in missing:
                            console.print(f"[red]{m}[/]")
                        if not Confirm.ask(
                            "[yellow]Continue anyway?[/]",
                            default=False,
                            console=console,
                        ):
                            continue

                clear_screen()
                banner()
                console.rule("[bold]Summary[/]", style="dim")
                summary_table(jobs)
                console.print()

                action = "collecting URLs" if choice == "1" else "scraping listings"
                if Confirm.ask(
                    f"[yellow]Start {action}?[/]", default=True, console=console
                ):
                    run_spiders(jobs)
                    break

            elif choice in ("q", "quit", "exit", ""):
                clear_screen()
                console.print("\n[dim]Terminated! [/]\n")
                break
            else:
                console.print("[red] Enter 1, 2, or q.[/]")
                time.sleep(1)

    except KeyboardInterrupt:
        clear_screen()
        console.print("\n[dim]Interrupted.[/]\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
