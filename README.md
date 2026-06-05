# Scrapper

Python utilities for harvesting insurance agency directory listings and exporting the results. The main `state_scraper.py` script walks state and city pages, scrapes each agency profile, and appends the data to carrier-specific CSV files inside `output/`. Helper scripts let you batch-run multiple states and convert generated CSVs into an Excel workbook.

## Features
- Resilient state → city → agent scraping with retries/backoff and informative error logging.
- Carrier selection for Progressive and Nationwide directories.
- Support for scraping a single city or agency URL without processing an entire state.
- Automatic CSV output for every agent plus a commercial-only CSV filtered on the “What we offer” section.
- Retry mode that reads previous error logs, re-fetches only the failed agent/city URLs, and appends any recovered rows.
- `csv_to_excel.py` utility that merges all CSVs from a folder into one XLSX file (one sheet per CSV).

## Requirements
- Python 3.9+ (tested with macOS Python 3)
- Dependencies: `requests`, `urllib3`, `bs4`, `pandas`, `openpyxl`

Create/activate a virtual environment, then install the packages:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt  # or install the packages listed above manually
```

## Usage

### Scrape an Entire State
Progressive is the default carrier. Outputs land in `output/<Carrier>/<State>Agents.csv`, with errors logged to `output/<Carrier>/<State>Errors.txt`. Commercial rows are identified by the `Commercial` column.

```bash
python state_scraper.py pennsylvania
python state_scraper.py --carrier nationwide pa
```

### Scrape a Single City or Agency
Pass `--url` with the exact carrier link:

```bash
# Progressive city
python state_scraper.py --url "https://www.progressiveagent.com/local-agent/pennsylvania/apollo/"

# Progressive agency
python state_scraper.py --url "https://www.progressiveagent.com/local-agent/pennsylvania/apollo/example-agency/"

# Nationwide city
python state_scraper.py --carrier nationwide --url "https://agency.nationwide.com/pa/apollo"

# Nationwide agency
python state_scraper.py --carrier nationwide --url "https://agency.nationwide.com/pa/apollo/15613/example-agency"
```

### Retry Only Failed URLs
Re-run any agent or city links captured in the state’s error log:

```bash
python state_scraper.py pennsylvania --retry-errors
python state_scraper.py --carrier nationwide pa --retry-errors
```

### Batch Multiple States
Run all generated states for a carrier:

```bash
./run_scraper.sh progressive
./run_scraper.sh nationwide
nohup ./run_scraper.sh nationwide > run.log 2>&1 &
```

### Convert CSVs to Excel
Generate separate all-agent and commercial-agent workbooks from a carrier output directory. The commercial workbook is filtered from `*Agents.csv` rows where `Commercial` is `Y`.

```bash
python csv_to_excel.py output/Progressive --all-output output/ProgressiveAllAgents.xlsx --commercial-output output/ProgressiveCommercialAgents.xlsx
python csv_to_excel.py output/Nationwide --all-output output/NationwideAllAgents.xlsx --commercial-output output/NationwideCommercialAgents.xlsx
```

To combine every CSV in a directory into one workbook instead:

```bash
python csv_to_excel.py output/Nationwide --output output/NationwideAllCsvs.xlsx
```

## Project Structure
- `state_scraper.py` – CLI dispatcher for supported carriers.
- `scrapers/common.py` – shared HTTP, CSV, and error-log utilities.
- `scrapers/progressive.py` – Progressive directory parser and retry logic.
- `scrapers/nationwide.py` – Nationwide directory parser and retry logic.
- `run_scraper.sh` – generates carrier states and calls the scraper per state.
- `csv_to_excel.py` – CSV ➜ XLSX converter for the generated outputs.
- `output/<Carrier>/` – created automatically to store CSVs and error logs.

## Notes
- Scraper uses a browser-like User-Agent header and retry-enabled `requests.Session` to reduce throttling.
- `.venv/`, `output/`, `input/`, and `archive/` are gitignored so local artifacts stay out of commits.
- Inspect `output/<Carrier>/*Errors.txt` if an execution terminates earlier than expected; each line includes enough context to diagnose or retry.
