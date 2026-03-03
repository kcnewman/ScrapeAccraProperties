# Data Card: `outputs/data/raw.csv`

## 1) Dataset Identity

| Field | Value |
|---|---|
| Dataset name | `raw.csv` (cleaned Jiji rental listings) |
| File path | `outputs/data/raw.csv` |
| Data card version | `1.0` |
| Data card generated on | `2026-03-02` |
| Geographic scope | Greater Accra, Ghana |
| Primary source platform | `jiji.com.gh` |
| Task domain | Residential rental market analysis |
| License context | Project is MIT licensed; source platform terms still apply |

## 2) Executive Summary

`raw.csv` is a cleaned, model-ready tabular dataset of rental property listings scraped from Jiji Ghana and post-processed by `clean.py`.

Current snapshot profile:

- Total rows: `24,696`
- Total columns: `29`
- Unique listing URLs: `24,696` (`0` duplicate URLs)
- Fetch date range: `2025-12-26` to `2026-03-01` (9 scrape dates)
- Missingness: very low (`Condition` 0.29%, `Property Size` 0.49%; all other columns complete)

## 3) Intended Use

### Recommended uses

- Rental price benchmarking by area and property type
- Feature engineering for rent prediction models
- Market segmentation and amenity prevalence analysis
- Descriptive analytics for locality-level trends

### Not recommended uses

- Legal valuation or financial underwriting without independent validation
- Fully automated decision-making affecting people without human review
- Any claim that requires exact listing freshness at inference time

## 4) Data Provenance

Source and pipeline:

1. URL discovery spiders collect listing URLs into `outputs/urls/jiji_urls.csv`.
2. Listing spider extracts structured listing fields into `outputs/data/jiji_data.csv`.
3. `clean.py` transforms and filters `jiji_data.csv` into `outputs/data/raw.csv`.

Key cleaning operations applied in `clean.py`:

- Derives `locality` from the raw `location` text.
- Standardizes select locality spellings and aliases.
- Fills missing `house_type` with `Bedsitter`.
- Drops rows with missing `bathrooms` or `bedrooms`.
- Converts `price` from currency text to float.
- Expands `properties` and `amenities` into structured columns.
- Merges `Facilities` into amenity flags when present.
- Filters probable sale or short-stay listings using keyword patterns in title/description.
- Produces a fixed final schema.

## 5) Schema

### Column-level dictionary

| Column | Type | Description |
|---|---|---|
| `url` | string | Canonical listing URL |
| `fetch_date` | date (`YYYY-MM-DD`) | Crawl date |
| `house_type` | categorical string | Property type label |
| `bathrooms` | integer-like numeric | Number of bathrooms |
| `bedrooms` | integer-like numeric | Number of bedrooms |
| `price` | float | Asking rent (numeric text normalized from Jiji listing) |
| `locality` | categorical string | Locality derived and standardized from listing location |
| `Condition` | categorical string | Listing condition (for example `Newly-Built`, `Fairly Used`) |
| `Furnishing` | categorical string | Furnishing status (`Unfurnished`, `Semi-Furnished`, `Furnished`) |
| `Property Size` | float (nullable) | Parsed property size value (unit not guaranteed) |
| `24-hour Electricity` | binary int (`0/1`) | Amenity indicator |
| `Air Conditioning` | binary int (`0/1`) | Amenity indicator |
| `Apartment` | binary int (`0/1`) | Amenity/property flag from source metadata |
| `Balcony` | binary int (`0/1`) | Amenity indicator |
| `Chandelier` | binary int (`0/1`) | Amenity indicator |
| `Dining Area` | binary int (`0/1`) | Amenity indicator |
| `Dishwasher` | binary int (`0/1`) | Amenity indicator |
| `Hot Water` | binary int (`0/1`) | Amenity indicator |
| `Kitchen Cabinets` | binary int (`0/1`) | Amenity indicator |
| `Kitchen Shelf` | binary int (`0/1`) | Amenity indicator |
| `Microwave` | binary int (`0/1`) | Amenity indicator |
| `Pop Ceiling` | binary int (`0/1`) | Amenity indicator |
| `Pre-Paid Meter` | binary int (`0/1`) | Amenity indicator |
| `Refrigerator` | binary int (`0/1`) | Amenity indicator |
| `TV` | binary int (`0/1`) | Amenity indicator |
| `Tiled Floor` | binary int (`0/1`) | Amenity indicator |
| `Wardrobe` | binary int (`0/1`) | Amenity indicator |
| `Wi-Fi` | binary int (`0/1`) | Amenity indicator |
| `loc` | categorical string | Normalized locality alias used for downstream grouping |

## 6) Snapshot Distribution (Current File)

### Core numeric columns

| Field | Min | Q1 | Median | Q3 | Max |
|---|---:|---:|---:|---:|---:|
| `price` | 90 | 2,000 | 4,500 | 11,999.25 | 1,655,500,000 |
| `bedrooms` | 1 | 2 | 2 | 3 | 20 |
| `bathrooms` | 1 | 1 | 2 | 3 | 20 |
| `Property Size` | 10 | 100 | 121 | 500 | 5,000 |

### Top property types

| `house_type` | Count | Share |
|---|---:|---:|
| Apartment | 14,551 | 58.92% |
| House | 7,205 | 29.17% |
| Duplex | 981 | 3.97% |
| Townhouse / Terrace | 623 | 2.52% |
| Room & Parlour | 380 | 1.54% |

### Top localities

| `locality` | Count | Share |
|---|---:|---:|
| East Legon | 2,777 | 11.24% |
| Spintex | 2,370 | 9.60% |
| Teshie | 1,744 | 7.06% |
| Adenta | 1,385 | 5.61% |
| Accra Metropolitan | 1,244 | 5.04% |

## 7) Data Quality and Validation

Checks run against this snapshot:

- Structural validation:
  - `29` expected columns present.
  - Amenity fields are strictly binary (`0/1`) with no invalid tokens.
- Uniqueness:
  - `url` duplicates: `0`.
- Completeness:
  - Missing `Condition`: `72` rows (`0.29%`).
  - Missing `Property Size`: `121` rows (`0.49%`).
  - All other columns complete.
- Temporal coverage:
  - Listings came from `9` distinct fetch dates.
  - Largest scrape day: `2025-12-26` (`14,107` rows).

## 8) Known Risks and Limitations

1. Extreme price outliers exist (for example values > `1,000,000`; max `1,655,500,000`), likely from source formatting, unit mismatch, or listing errors.
2. `Property Size` units are not explicitly standardized in `raw.csv`; treat as numeric signal with caution.
3. Coverage is single-platform (`jiji.com.gh`) and may not represent the full rental market.
4. Data is a point-in-time crawl and may include stale or changed listings.
5. Keyword filtering in `clean.py` reduces sale/short-stay contamination but is heuristic and can produce false positives/negatives.

## 9) Responsible Use

- Re-validate high-value or high-impact records directly against source URLs.
- Apply robust outlier handling before training models or publishing metrics.
- Respect platform terms, robots directives, and local legal/privacy requirements.
- Avoid use cases that materially affect individuals without human oversight.

## 10) Reproducibility Notes

To regenerate this dataset from project root:

1. Run URL collection (`python main.py` -> collect URLs for Jiji).
2. Run listing scrape (`python main.py` -> scrape Jiji listings).
3. Cleaning runs automatically after Jiji listing scrape and outputs `outputs/data/raw.csv`.

Direct cleaning entrypoint:

```bash
python clean.py
```

## 11) Maintenance

- Trigger an updated data card whenever `raw.csv` is refreshed.
- Version this card with date-stamped snapshots if used for model training.
- Add automated profiling checks (duplicates, missingness, outlier thresholds) as a CI gate for future production use.
