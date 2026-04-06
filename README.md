# Scrapper

Python utilities for harvesting XXXX local-agent listings and exporting the results. The main `state_scraper.py` script walks state and city pages, scrapes each agent profile, and appends the data to CSV files inside `XXXX/`. Helper scripts let you batch-run multiple states and convert the generated CSVs into an Excel workbook.

## Features
- Resilient state → city → agent scraping with retries/backoff and informative error logging.
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
Outputs land in `output/XXXX/<State>Agents.csv` and `ouput/XXXX/<State>CommercialAgents.csv`, with errors logged to `output/XXXX/<State>Errors.txt`.

```bash
python state_scraper.py pennsylvania
```

### Scrape a Single City or Agency
Pass `--url` with the exact XXXX link:

```bash
# City (creates XXXX/pennsylvania_apollo_Agents.csv)
python state_scraper.py --url "https://xxxxx/local-agent/pennsylvania/apollo/"

# Agency (creates XXXX/pennsylvania_apollo_example-agency_Agent.csv)
python state_scraper.py --url "https://xxxx/local-agent/pennsylvania/apollo/example-agency/"
```

### Retry Only Failed URLs
Re-run any agent or city links captured in the state’s error log:

```bash
python state_scraper.py pennsylvania --retry-errors
```

### Batch Multiple States
Populate `states.txt` (one state slug per line) and run:

```bash
./run_scraper.sh
 nohup ./run_scraper.sh > run.log 2>&1 & 
```

### Convert CSVs to Excel
Combine every CSV in a directory into one workbook (one sheet per file):

```bash
python csv_to_excel.py XXXX --output XXXX_agents.xlsx
```

## Project Structure
- `state_scraper.py` – core scraper and retry logic.
- `run_scraper.sh` – loops through `states.txt` and calls the scraper per state.
- `csv_to_excel.py` – CSV ➜ XLSX converter for the generated outputs.
- `XXXX/` – created automatically to store CSVs and error logs.

## Notes
- Scraper uses a browser-like User-Agent header and retry-enabled `requests.Session` to reduce throttling.
- `.venv/`, `output/`, `input/`, and `archive/` are gitignored so local artifacts stay out of commits.
- Inspect `XXXX/*Errors.txt` if an execution terminates earlier than expected; each line includes enough context to diagnose or retry.
