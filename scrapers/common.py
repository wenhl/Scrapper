import csv
import os

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
REQUEST_TIMEOUT = 30


SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    )
})

retry_strategy = Retry(
    total=5,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["HEAD", "GET", "OPTIONS"],
    raise_on_status=False,
)
adapter = HTTPAdapter(max_retries=retry_strategy)
SESSION.mount("https://", adapter)
SESSION.mount("http://", adapter)


def fetch_html(url, timeout=REQUEST_TIMEOUT):
    try:
        response = SESSION.get(url, timeout=timeout)
        response.raise_for_status()
        return response.text
    except requests.RequestException as exc:
        raise RuntimeError(f"Request failed for {url}: {exc}") from exc


def write_agents_to_csv(output_path, fieldnames, agent_data_list):
    file_exists = os.path.isfile(output_path)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "a", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        for agent in agent_data_list:
            writer.writerow(agent)


def log_error(error_path, message):
    print(message)
    os.makedirs(os.path.dirname(error_path), exist_ok=True)
    with open(error_path, "a", encoding="utf-8") as error_file:
        error_file.write(message + "\n")
