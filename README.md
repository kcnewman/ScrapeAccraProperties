# ScrapeAccraProperties

ScrapeAccraProperties is a Scrapy + Playwright project for collecting rental listings in Greater Accra from:

- Jiji Ghana
- Meqasa

The scraper runs in two phases:

1. Collect listing URLs from search/result pages.
2. Visit each listing URL and extract structured listing data.

All outputs are written to CSV files under `outputs/`.

## Current Features

- JS-rendered scraping with `scrapy-playwright` (Chromium)
- Interactive CLI runner in `main.py`
- URL discovery and listing extraction for both sites
- Incremental CSV writes with URL deduplication
- Resume mode that queues only missing URLs
- Rich progress UI with per-spider summaries

## Requirements

- Python `3.12+` (project currently uses `3.12`)
- Chromium browser binaries for Playwright
- OS libraries needed by Playwright on Linux

Dependencies are defined in `pyproject.toml` and include:

- `scrapy`
- `scrapy-playwright`
- `playwright`
- `rich`
- `pandas`

## Setup

### 1. Install Python dependencies

Using `uv` (recommended):

```bash
uv sync
```

Using `pip`:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 2. Install Playwright browser

```bash
python -m playwright install chromium
```

If required on your OS:

```bash
python -m playwright install-deps chromium
```

## Interactive Usage (Recommended)

Run:

```bash
python main.py
```

Or with `uv`:

```bash
uv run python main.py
```

The menu offers:

- `Collect listing URLs`
- `Scrape listing details`
- `Resume listing scrape (missing URLs only)`

For each action, you can choose:

- `Jiji only`
- `Meqasa only`
- `Both Jiji and Meqasa`

## Workflow

### 1. Collect URLs

Runs URL spiders and writes:

- `jiji_urls` -> `outputs/urls/jiji_urls.csv`
- `meqasa_urls` -> `outputs/urls/meqasa_urls.csv`

URL-collection options:

- Jiji: `start_page` + auto detect, `max_pages`, or `total_listing`
- Meqasa: `start_page` + auto detect or `total_pages`

### 2. Scrape Listing Details

Runs listing spiders and writes:

- `jiji_listings` reads `outputs/urls/jiji_urls.csv` and writes `outputs/data/jiji_data.csv`
- `meqasa_listings` reads `outputs/urls/meqasa_urls.csv` and writes `outputs/data/meqasa_data.csv`

### 3. Resume Missing Listings

Resume mode compares URL CSVs to data CSVs using the `url` column and creates temporary queue files for unscraped URLs only:

- `outputs/urls/jiji_resume_queue.csv`
- `outputs/urls/meqasa_resume_queue.csv`

Queue files are removed automatically after the run finishes.

## Running Spiders Directly

You can bypass the interactive runner and call spiders directly:

```bash
scrapy crawl jiji_urls -a start_page=1 -a max_pages=5
scrapy crawl jiji_urls -a start_page=1 -a total_listing=200
scrapy crawl meqasa_urls -a start_page=1 -a total_pages=5

scrapy crawl jiji_listings -a csv_path=outputs/urls/jiji_urls.csv
scrapy crawl meqasa_listings -a csv_path=outputs/urls/meqasa_urls.csv
```

## Output Files

Auto-created directories:

- `outputs/urls/`
- `outputs/data/`

Primary outputs:

- `outputs/urls/jiji_urls.csv`
- `outputs/urls/meqasa_urls.csv`
- `outputs/data/jiji_data.csv`
- `outputs/data/meqasa_data.csv`

## Data Schema

### URL CSVs (`jiji_urls.csv`, `meqasa_urls.csv`)

- `url`
- `page`
- `fetch_date`

### Jiji listing CSV (`jiji_data.csv`)

Key fields:

- `url`
- `fetch_date`
- `title`
- `location`
- `house_type`
- `bedrooms`
- `bathrooms`
- `price`
- `properties` (serialized mapping)
- `amenities` (serialized list)
- `description`

### Meqasa listing CSV (`meqasa_data.csv`)

Base fields:

- `url`
- `Title`
- `Price`
- `Rate`
- `Description`
- `fetch_date`

Additional columns are extracted from listing detail tables and can vary by listing.

## Project Structure

```text
.
├── main.py
├── property_bot/
│   ├── settings.py
│   └── spiders/
│       ├── base_spider.py
│       ├── jiji_urls.py
│       ├── jiji_listing.py
│       ├── meqasa_urls.py
│       └── meqasa_listing.py
├── outputs/
│   ├── urls/
│   └── data/
├── scrapy.cfg
├── pyproject.toml
└── README.md
```

## Configuration Notes

Highlights from `property_bot/settings.py`:

- `ROBOTSTXT_OBEY = True`
- Asyncio reactor enabled for Playwright integration
- High concurrency with short delays and autothrottle
- Asset blocking for heavy resource types (images/media/fonts/stylesheet)
- Chromium launch options tuned for headless scraping
- Retries enabled for transient HTTP failures (including `403`)

## Troubleshooting

- `No URLs found in ...csv`: run URL collection first or pass the correct `csv_path`.
- Browser launch failures: run `python -m playwright install chromium`.
- Linux dependency errors: run `python -m playwright install-deps chromium`.
- Empty/partial fields: target site HTML changed and selectors may need updates.

## Legal and Responsible Use

- Review and respect target site Terms of Service and `robots.txt`.
- Keep request volume and crawl frequency reasonable.
- Use scraped data in line with applicable laws and privacy obligations.

## License

MIT (see `LICENSE`).
