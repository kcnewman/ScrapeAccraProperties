#!/usr/bin/env python3
"""
Central runner for property scrapers.
Runs Jiji + Meqasa spiders concurrently.

Usage:
    python run.py
"""

import os
import sys
import pathlib

os.environ.setdefault("SCRAPY_SETTINGS_MODULE", "property_bot.settings")

# Install asyncio reactor BEFORE any Twisted/Scrapy import
from twisted.internet import asyncioreactor

asyncioreactor.install()

from twisted.internet.asyncioreactor import AsyncioSelectorReactor
from twisted.internet import reactor as _reactor
from twisted.internet import defer

reactor: AsyncioSelectorReactor = _reactor  # type: ignore[assignment]

from scrapy.crawler import CrawlerRunner
from scrapy.utils.log import configure_logging
from scrapy.utils.project import get_project_settings

from property_bot.spiders.jiji_listing import JijiListingSpider
from property_bot.spiders.jiji_urls import JijiUrlSpider
from property_bot.spiders.meqasa_listing import MeqasaListingSpider
from property_bot.spiders.meqasa_urls import MeqasaUrlSpider

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich import box

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

console = Console()


# ── UI components ─────────────────────────────────────────────────────────────


def print_banner():
    console.print(
        Panel.fit(
            "[cyan bold]🏠  Property Scraper — Central Runner[/]\n"
            "[dim]Jiji Ghana  ·  Meqasa  [/]",
            border_style="cyan",
            padding=(1, 4),
        )
    )
    console.print()


def print_menu():
    t = Table(show_header=False, box=box.ROUNDED, border_style="dim", padding=(0, 2))
    t.add_column(style="green bold", width=4)
    t.add_column()
    t.add_row("[1]", "🔗  Collect listing URLs")
    t.add_row("[2]", "📄  Scrape listing details")
    t.add_row("[q]", "🚪  Quit")
    console.print(t)
    console.print()


def section(title: str):
    console.rule(f"[cyan bold]{title}[/]", style="dim")
    console.print()


def ask(prompt: str, default=None, cast=None, allow_empty: bool = False):
    """Thin wrapper around Rich Prompt that supports type casting."""
    default_str = str(default) if default is not None else None
    while True:
        raw = Prompt.ask(f"[yellow]{prompt}[/]", default=default_str, console=console)
        if raw is None or raw == "":
            if allow_empty:
                return None
            if default is not None:
                return default
            console.print("[red]⚠  Please enter a value.[/]")
            continue
        if cast:
            try:
                return cast(raw)
            except (ValueError, TypeError):
                console.print("[red]⚠  Expected a number.[/]")
                continue
        return raw


def confirm(prompt: str, default: bool = True) -> bool:
    return Confirm.ask(f"[yellow]{prompt}[/]", default=default, console=console)


def print_summary_table(params: dict):
    t = Table(show_header=True, header_style="bold dim", box=box.SIMPLE, padding=(0, 2))
    t.add_column("Spider")
    t.add_column("Parameters")
    for site, kw in params.items():
        t.add_row(site.capitalize(), str(kw) if kw else "[dim](defaults)[/]")
    console.print(t)


# ── Parameter collection ──────────────────────────────────────────────────────


def collect_url_params() -> dict:
    params: dict = {"jiji": {}, "meqasa": {}}

    section("Jiji URL Spider")
    console.print(
        "[dim]jiji.com.gh › Greater Accra › Houses & Apartments for Rent[/]\n"
    )

    mode = str(
        ask("Mode — (a)uto  (f)ixed pages  (t)otal listings", default="a")
    ).lower()
    if mode.startswith("f"):
        params["jiji"]["max_pages"] = ask("Max pages", default=10, cast=int)
    elif mode.startswith("t"):
        params["jiji"]["total_listing"] = ask("Total listings", default=200, cast=int)
    params["jiji"]["start_page"] = ask("Start page", default=1, cast=int)

    console.print()
    section("Meqasa URL Spider")
    console.print("[dim]meqasa.com › Greater Accra › For Rent[/]\n")

    tp = ask(
        "Total pages (leave blank = auto-detect)",
        default=None,
        cast=int,
        allow_empty=True,
    )
    if tp:
        params["meqasa"]["total_pages"] = tp
    params["meqasa"]["start_page"] = ask("Start page", default=1, cast=int)

    return params


def collect_listing_params() -> dict:
    params: dict = {"jiji": {}, "meqasa": {}}

    section("Jiji Listing Spider")
    params["jiji"]["csv_path"] = ask(
        "Jiji URLs CSV", default="outputs/urls/jiji_urls.csv"
    )

    console.print()
    section("Meqasa Listing Spider")
    params["meqasa"]["csv_path"] = ask(
        "Meqasa URLs CSV", default="outputs/urls/meqasa_urls.csv"
    )

    return params


# ── Runner ────────────────────────────────────────────────────────────────────


def run_spiders(spider_jobs: list):
    configure_logging()
    settings = get_project_settings()
    runner = CrawlerRunner(settings=settings)

    @defer.inlineCallbacks
    def crawl():
        deferreds = [runner.crawl(cls, **kw) for cls, kw in spider_jobs]
        yield defer.DeferredList(deferreds, consumeErrors=True)
        reactor.stop()

    crawl()
    n = len(spider_jobs)
    console.print(
        f"\n[green bold]🚀  Starting {n} spider{'s' if n > 1 else ''} in parallel …[/]\n"
    )
    reactor.run()


# ── Main ──────────────────────────────────────────────────────────────────────


def main():
    print_banner()

    while True:
        print_menu()
        choice = str(ask("Choice", default="q")).lower()

        if choice == "1":
            console.print()
            params = collect_url_params()

            console.print()
            console.rule("[bold]Summary[/]", style="dim")
            print_summary_table(params)

            if not confirm("\nStart scraping URLs?"):
                continue

            run_spiders(
                [
                    (JijiUrlSpider, params["jiji"]),
                    (MeqasaUrlSpider, params["meqasa"]),
                ]
            )
            break

        elif choice == "2":
            console.print()
            params = collect_listing_params()

            missing = [
                f"  {site}: {kw['csv_path']}"
                for site, kw in params.items()
                if not os.path.exists(kw.get("csv_path", ""))
            ]
            if missing:
                console.print(f"\n[red]⚠  CSV files not found:[/]")
                for m in missing:
                    console.print(f"[red]{m}[/]")
                if not confirm("Continue anyway?", default=False):
                    continue

            console.print()
            console.rule("[bold]Summary[/]", style="dim")
            print_summary_table(params)

            if not confirm("\nStart scraping listings?"):
                continue

            run_spiders(
                [
                    (JijiListingSpider, params["jiji"]),
                    (MeqasaListingSpider, params["meqasa"]),
                ]
            )
            break

        elif choice in ("q", "quit", "exit", ""):
            console.print("\n[dim]Bye! 👋[/]\n")
            break

        else:
            console.print("[red]⚠  Enter 1, 2, or q.[/]\n")


if __name__ == "__main__":
    main()
