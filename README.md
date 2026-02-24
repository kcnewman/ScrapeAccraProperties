# ScrapeAccraProperties

ScrapeAccraProperties is a Scrapy + Playwright project for collecting rental property listings in the Greater Accra region from:

- Jiji Ghana
- Meqasa

The project has a two-step scraping flow:

1. Collect listing URLs from search/result pages
2. Visit each listing URL and extract structured property data

Data is stored in CSV files under `outputs/`.

## Features

- Headless browser scraping via `scrapy-playwright` (for JS-rendered pages)
- Interactive terminal runner (`run.py`) to choose scraping mode and parameters
- Parallel spider runs for Jiji and Meqasa
- Incremental CSV persistence with URL de-duplication
- Resume mode that scrapes only missing listings
- Real-time Rich progress UI and per-spider summary

## Project Structure

```text
.
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
├── run.py
├── scrapy.cfg
└── pyproject.toml
```

## Requirements

- Python 3.12+
- Chromium dependencies required by Playwright (OS-level)

Python dependencies are managed in `pyproject.toml`:

- `scrapy`
- `playwright`
- `scrapy-playwright`
- `rich`
- `pandas`

## Setup

### 1. Create environment and install dependencies

Using `uv` (recommended):

```bash
uv sync
```

Or with `pip`:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 2. Install Playwright browser

```bash
python -m playwright install chromium
```

If your OS needs extra system libraries:

```bash
python -m playwright install-deps chromium
```

## How To Run

### Interactive runner (recommended)

```bash
python run.py
```

You will see:

- `1` Collect listing URLs
- `2` Scrape listing details
- `3` Resume and scrape only missing listings

The runner allows you to configure page ranges, total listing/page limits, source CSV paths, and whether each spider should run.

## Scraping Workflow

### Step 1: Collect URLs

This runs one or both URL spiders:

- `jiji_urls` -> writes `outputs/urls/jiji_urls.csv`
- `meqasa_urls` -> writes `outputs/urls/meqasa_urls.csv`

#### Jiji URL modes (in runner)

- Auto detect total pages
- Fixed page count (`max_pages`)
- From expected total listings (`total_listing`, converted to pages)

#### Meqasa URL modes

- Auto detect total pages
- Fixed page count (`total_pages`)

### Step 2: Scrape listing pages

This runs one or both listing spiders:

- `jiji_listings` reads URL CSV (default `outputs/urls/jiji_urls.csv`) and writes `outputs/data/jiji_data.csv`
- `meqasa_listings` reads URL CSV (default `outputs/urls/meqasa_urls.csv`) and writes `outputs/data/meqasa_data.csv`

### Step 3: Resume missing listings

Resume mode compares URL CSVs vs already-scraped data CSVs and only queues URLs that are not in data outputs:

- Jiji compare: `outputs/urls/jiji_urls.csv` vs `outputs/data/jiji_data.csv` using `url`
- Meqasa compare: `outputs/urls/meqasa_urls.csv` vs `outputs/data/meqasa_data.csv` using `url`

Temporary queue files are generated during resume and removed after run:

- `outputs/urls/jiji_resume_queue.csv`
- `outputs/urls/meqasa_resume_queue.csv`

## Output Files

The project auto-creates these folders if missing:

- `outputs/urls/`
- `outputs/data/`

Typical output files:

- `outputs/urls/jiji_urls.csv`
- `outputs/urls/meqasa_urls.csv`
- `outputs/data/jiji_data.csv`
- `outputs/data/meqasa_data.csv`

Temporary (resume mode only):

- `outputs/urls/jiji_resume_queue.csv`
- `outputs/urls/meqasa_resume_queue.csv`

## Data Schema (Current)

### Jiji URL CSV

- `url`
- `page`
- `fetch_date`

### Meqasa URL CSV

- `url`
- `page`
- `fetch_date`

### Jiji data CSV (key fields)

- `url`
- `fetch_date`
- `title`
- `location`
- `house_type`
- `bedrooms`
- `bathrooms`
- `price`
- `properties`
- `amenities`
- `description`

### Meqasa data CSV (key fields)

- `url`
- `Title`
- `Price`
- `Rate`
- `Description`
- `fetch_date`
- Additional table-derived columns from listing detail pages

## Running Spiders Directly (Optional)

You can run spiders without the interactive menu:

```bash
scrapy crawl jiji_urls -a start_page=1 -a max_pages=5
scrapy crawl meqasa_urls -a start_page=1 -a total_pages=5

scrapy crawl jiji_listings -a csv_path=outputs/urls/jiji_urls.csv
scrapy crawl meqasa_listings -a csv_path=outputs/urls/meqasa_urls.csv
```

## Configuration Notes

Key behavior in `property_bot/settings.py`:

- `ROBOTSTXT_OBEY = True`
- Asyncio Twisted reactor for Playwright
- High concurrency + short delays
- Request aborting for heavy assets (images/fonts/media/stylesheet)
- Headless Chromium launch args optimized for scraping speed
- Retries enabled for transient failures (including `403`)

## Operational Notes

- Existing rows are used for URL de-duplication by each spider before writing.
- URL and listing spiders can be launched together from the runner.
- CSV rows are written with full quoting to reduce malformed-row issues when fields contain commas/newlines.
- Logs are intentionally minimized in settings for cleaner terminal output.

## Troubleshooting

- `No URLs found in ...csv`: run URL collection first or provide the correct `csv_path`.
- Playwright launch/browser errors: ensure Chromium is installed with `python -m playwright install chromium`.
- Empty/partial extraction: source sites can change HTML structures; selectors in spiders may need updates.

## Legal and Responsible Use

- Review and respect each target site's Terms of Service and `robots.txt`.
- Scrape responsibly (frequency, load, and data usage).
- Use collected data in compliance with applicable laws and privacy requirements.

## License

MIT (see `LICENSE`).
