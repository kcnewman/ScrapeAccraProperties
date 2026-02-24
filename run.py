#!/usr/bin/env python3
"""Central runner for property scrapers. Runs Jiji + Meqasa spiders."""

import os
import sys
import pathlib

os.environ.setdefault("SCRAPY_SETTINGS_MODULE", "property_bot.settings")

from twisted.internet import asyncioreactor

asyncioreactor.install()

from twisted.internet import reactor, defer
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


def clear():
    console.clear()


def banner():
    console.print(
        Panel.fit(
            "[cyan bold]  Property Scraper[/]\n[dim]Jiji Ghana  ·  Meqasa[/]",
            border_style="cyan",
            padding=(1, 4),
        )
    )
    console.print()


def menu():
    t = Table(show_header=False, box=box.ROUNDED, border_style="dim", padding=(0, 2))
    t.add_column(style="green bold", width=4)
    t.add_column()
    t.add_row("[1]", "🔗  Collect listing URLs")
    t.add_row("[2]", "📄  Scrape listing details")
    t.add_row("[q]", "🚪  Quit")
    console.print(t)
    console.print()


def ask(prompt, default=None, cast=None, allow_empty=False):
    default_str = str(default) if default is not None else None
    while True:
        raw = Prompt.ask(f"[yellow]{prompt}[/]", default=default_str, console=console)
        if not raw:
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


def summary_table(params: dict):
    t = Table(show_header=True, header_style="bold dim", box=box.SIMPLE, padding=(0, 2))
    t.add_column("Spider")
    t.add_column("Parameters")
    for site, kw in params.items():
        t.add_row(site.capitalize(), str(kw) if kw else "[dim](defaults)[/]")
    console.print(t)


def collect_url_params():
    console.rule("[cyan bold]Jiji URL Spider[/]", style="dim")
    console.print("[dim]jiji.com.gh › Greater Accra › Houses & Apartments for Rent[/]\n")

    jiji = {}
    mode = ask("Mode — (a)uto  (f)ixed pages  (t)otal listings", default="a").lower()
    if mode.startswith("f"):
        jiji["max_pages"] = ask("Max pages", default=10, cast=int)
    elif mode.startswith("t"):
        jiji["total_listing"] = ask("Total listings", default=200, cast=int)
    jiji["start_page"] = ask("Start page", default=1, cast=int)

    console.print()
    console.rule("[cyan bold]Meqasa URL Spider[/]", style="dim")
    console.print("[dim]meqasa.com › Greater Accra › For Rent[/]\n")

    meqasa = {}
    tp = ask("Total pages (blank = auto-detect)", default=None, cast=int, allow_empty=True)
    if tp:
        meqasa["total_pages"] = tp
    meqasa["start_page"] = ask("Start page", default=1, cast=int)

    return {"jiji": jiji, "meqasa": meqasa}


def collect_listing_params():
    console.rule("[cyan bold]Jiji Listing Spider[/]", style="dim")
    jiji_csv = ask("Jiji URLs CSV", default="outputs/urls/jiji_urls.csv")

    console.print()
    console.rule("[cyan bold]Meqasa Listing Spider[/]", style="dim")
    meqasa_csv = ask("Meqasa URLs CSV", default="outputs/urls/meqasa_urls.csv")

    return {
        "jiji": {"csv_path": jiji_csv},
        "meqasa": {"csv_path": meqasa_csv},
    }


def run_spiders(jobs: list):
    configure_logging()
    runner = CrawlerRunner(settings=get_project_settings())

    @defer.inlineCallbacks
    def crawl():
        deferreds = [runner.crawl(cls, **kw) for cls, kw in jobs]
        yield defer.DeferredList(deferreds, consumeErrors=True)
        reactor.stop()

    crawl()
    console.print(f"\n[green bold]🚀  Starting {len(jobs)} spider(s) in parallel…[/]\n")
    reactor.run()


def main():
    clear()
    banner()

    while True:
        menu()
        choice = ask("Choice", default="q").lower()

        if choice == "1":
            clear()
            banner()
            params = collect_url_params()

            clear()
            banner()
            console.rule("[bold]Summary[/]", style="dim")
            summary_table(params)
            console.print()

            if not Confirm.ask("[yellow]Start collecting URLs?[/]", default=True, console=console):
                clear()
                banner()
                continue

            run_spiders([(JijiUrlSpider, params["jiji"]), (MeqasaUrlSpider, params["meqasa"])])
            break

        elif choice == "2":
            clear()
            banner()
            params = collect_listing_params()

            missing = [
                f"  {site}: {kw['csv_path']}"
                for site, kw in params.items()
                if not os.path.exists(kw.get("csv_path", ""))
            ]
            if missing:
                console.print("\n[red]⚠  CSV files not found:[/]")
                for m in missing:
                    console.print(f"[red]{m}[/]")
                if not Confirm.ask("[yellow]Continue anyway?[/]", default=False, console=console):
                    clear()
                    banner()
                    continue

            clear()
            banner()
            console.rule("[bold]Summary[/]", style="dim")
            summary_table(params)
            console.print()

            if not Confirm.ask("[yellow]Start scraping listings?[/]", default=True, console=console):
                clear()
                banner()
                continue

            run_spiders([(JijiListingSpider, params["jiji"]), (MeqasaListingSpider, params["meqasa"])])
            break

        elif choice in ("q", "quit", "exit", ""):
            console.print("\n[dim]Bye! 👋[/]\n")
            break

        else:
            console.print("[red]⚠  Enter 1, 2, or q.[/]\n")
            clear()
            banner()


if __name__ == "__main__":
    main()
