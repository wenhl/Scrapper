#!/usr/bin/env python3
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
import json
import csv
import os
import sys
from urllib.parse import quote, urlparse
import argparse

# Define a mapping for the CSV columns.
# The key is the internal name used in the code,
# and the value is the CSV column header.
COLUMN_MAPPING = {
    "commercial": "Commercial",
    "agency_name": "AgencyName",
    "street_address": "StreetAddress",
    "city": "City",
    "state": "State",
    "postal_code": "PostalCode",
    "email": "Email",
    "phone": "Phone",
    "language": "Language",
    "web_site": "Website",
    "link": "Link",
    "offer": "Offer"
}

# Global constant for CSV field names.
FIELDNAMES = list(COLUMN_MAPPING.values())

# Configure a single session with retries and a browser-like user agent to
# reduce the chance of getting throttled mid-run.
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
REQUEST_TIMEOUT = 30  # seconds


def fetch_html(url, timeout=REQUEST_TIMEOUT):
    """
    Fetches the HTML content for a given URL.
    Raises requests.HTTPError if the request fails.
    """
    try:
        response = SESSION.get(url, timeout=timeout)
        response.raise_for_status()
        return response.text
    except requests.RequestException as exc:
        raise RuntimeError(f"Request failed for {url}: {exc}") from exc

def parse_state_city_links(html):
    """
    Given the HTML content of a state page, extract a list of city page links.
    Looks for all <ul> elements with class "city-list" and extracts the href from each <a> tag.
    """
    soup = BeautifulSoup(html, "html.parser")
    ul_elements = soup.find_all("ul", class_="city-list")
    if not ul_elements:
        raise ValueError("No <ul class='city-list'> elements found in the state page.")
    
    city_links = []
    for ul in ul_elements:
        for li in ul.find_all("li"):
            a = li.find("a")
            if a:
                href = a.get("href")
                if href:
                    city_links.append(href)
    print(f"Found {len(city_links)} city links in the state page.")
    return city_links

def parse_city_agent_links(html):
    """
    Extracts a list of agent detail page links from a city page's HTML.
    Searches for <a> tags whose text contains "agency details" (case insensitive).
    """
    soup = BeautifulSoup(html, "html.parser")
    agent_links = soup.find_all("a", string=lambda text: text and "agency details" in text.lower())
    links = [a.get("href") for a in agent_links if a.get("href")]
    print(f"Found {len(links)} agent links in the city page.")
    return links

def extract_agent_json_from_html(html):
    """
    Extracts a JSON object embedded in the first <script> tag inside a <main> tag.
    """
    soup = BeautifulSoup(html, "html.parser")
    main_tag = soup.find("main")
    if not main_tag:
        raise ValueError("No <main> tag found in the agent page.")
    
    script_tag = main_tag.find("script")
    if not script_tag:
        raise ValueError("No <script> tag found in <main> of the agent page.")
    
    js_text = script_tag.get_text().strip()
    try:
        data = json.loads(js_text)
    except Exception as e:
        raise ValueError(f"Error parsing JSON: {e}")
    return data

def extract_what_we_offer(html):
    """
    Extracts items from the "What we offer:" section.
    Looks for an <h2> tag with the text and then the first <ul> with class "bullets".
    Returns the items as a comma-separated string.
    """
    soup = BeautifulSoup(html, "html.parser")
    header = soup.find("h2", string=lambda text: text and "What we offer:" in text)
    if header:
        ul = header.find_next("ul", class_="bullets")
        if ul:
            items = [li.get_text(strip=True) for li in ul.find_all("li")]
            return ", ".join(items)
    return ""

def extract_agent_data(agent_json):
    """
    Extracts key agent data from a JSON object.
    """
    return {
        COLUMN_MAPPING["agency_name"]: agent_json.get("name", ""),
        COLUMN_MAPPING["street_address"]: agent_json.get("address", {}).get("streetAddress", ""),
        COLUMN_MAPPING["city"]: agent_json.get("address", {}).get("addressLocality", ""),
        COLUMN_MAPPING["state"]: agent_json.get("address", {}).get("addressRegion", ""),
        COLUMN_MAPPING["postal_code"]: agent_json.get("address", {}).get("postalCode", ""),
        COLUMN_MAPPING["email"]: agent_json.get("email", "").lower(),
        COLUMN_MAPPING["phone"]: agent_json.get("telephone", ""),
        COLUMN_MAPPING["language"]: agent_json.get("knowsLanguage", ""),
        COLUMN_MAPPING["web_site"]: agent_json.get("url", ""),
        COLUMN_MAPPING["link"]: agent_json.get("@id", "")
    }

def process_agent_page(agent_url):
    """
    Fetches an agent page, extracts JSON data and the "What we offer:" section,
    then returns the combined agent data as a dictionary.
    """
    html = fetch_html(agent_url)
    agent_json = extract_agent_json_from_html(html)
    agent_data = extract_agent_data(agent_json)
    offer_info = extract_what_we_offer(html)
    agent_data[COLUMN_MAPPING["offer"]] = offer_info
    agent_data[COLUMN_MAPPING["commercial"]] = "Y" if "Commercial Auto" in offer_info else "N"
    return agent_data

def process_agents(agent_links, error_path):
    """
    Processes a list of agent page URLs.
    For each link, tries to process it and collects the data.
    Logs any errors encountered.
    """
    results = []
    for i, agent_link in enumerate(agent_links, start=1):
        print(f"Processing agent {i}...")
        try:
            agent_data = process_agent_page(agent_link)
            results.append(agent_data)
        except Exception as e:
            error_message = f"Error processing agent page {agent_link}: {e}"
            log_error(error_path, error_message)
    return results

def write_agents_to_csv(output_path, fieldnames, agent_data_list):
    """
    Writes the agent data to a CSV file.
    Creates a header if the file does not already exist.
    """
    file_exists = os.path.isfile(output_path)
    with open(output_path, "a", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        for agent in agent_data_list:
            writer.writerow(agent)

def log_error(error_path, message):
    """
    Logs error messages by appending them to an error file.
    """
    print(message)
    os.makedirs(os.path.dirname(error_path), exist_ok=True)
    with open(error_path, "a", encoding="utf-8") as ef:
        ef.write(message + "\n")


def collect_city_agents(city_url, error_path):
    """
    Fetches a city page, extracts its agent links, processes each agent,
    and returns the resulting list. Errors are logged to error_path.
    """
    try:
        city_html = fetch_html(city_url)
    except Exception as exc:
        log_error(error_path, f"Error fetching city page {city_url}: {exc}")
        return []

    agent_links = parse_city_agent_links(city_html)
    if not agent_links:
        log_error(error_path, f"No agent links found for city {city_url}")
        return []

    return process_agents(agent_links, error_path)


def find_error_file(state):
    """
    Returns the most likely error log file for the given state.
    Looks both in Progressive/<state>Errors.txt and Progressive/error/<state>Errors.txt.
    """
    output_dir = os.path.join(os.getcwd(), "Progressive")
    candidates = [
        os.path.join(output_dir, f"{state}Errors.txt"),
        os.path.join(output_dir, "error", f"{state}Errors.txt"),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    raise FileNotFoundError(
        f"Could not find an error log for state '{state}'. Looked in: {', '.join(candidates)}"
    )


def parse_agent_urls_from_error_log(error_path):
    """
    Extracts agent detail page URLs from an error log.
    Only lines that start with 'Error processing agent page' are considered.
    """
    prefix = "Error processing agent page "
    urls = []
    seen = set()
    with open(error_path, "r", encoding="utf-8") as ef:
        for raw_line in ef:
            line = raw_line.strip()
            if not line.startswith(prefix):
                continue
            remainder = line[len(prefix):]
            url = remainder.split(": ", 1)[0].strip()
            if url and url not in seen:
                seen.add(url)
                urls.append(url)
    return urls


def parse_city_urls_from_error_log(error_path):
    """
    Extracts city page URLs from an error log.
    Looks for common messages generated when a city fetch or parse failed.
    """
    prefixes = [
        "Error fetching city page ",
        "No agent links found for city ",
    ]
    urls = []
    seen = set()
    with open(error_path, "r", encoding="utf-8") as ef:
        for raw_line in ef:
            line = raw_line.strip()
            for prefix in prefixes:
                if line.startswith(prefix):
                    remainder = line[len(prefix):]
                    url = remainder.split(": ", 1)[0].strip()
                    if url and url not in seen:
                        seen.add(url)
                        urls.append(url)
                    break
    return urls


def process_city_for_state(city_url, output_path, commercial_output_path, error_path):
    """
    Re-scrapes a single city and appends its agents to the state-level outputs.
    """
    agent_results = collect_city_agents(city_url, error_path)
    if not agent_results:
        return 0, 0

    write_agents_to_csv(output_path, FIELDNAMES, agent_results)
    commercial_agents = [
        agent for agent in agent_results
        if agent[COLUMN_MAPPING["commercial"]].upper() == "Y"
    ]
    if commercial_agents:
        write_agents_to_csv(commercial_output_path, FIELDNAMES, commercial_agents)

    return len(agent_results), len(commercial_agents)


def retry_failed_agents(state):
    """
    Reprocesses agent and city pages that previously failed and were logged to the error file.
    Successful retries are appended to the standard state CSV outputs.
    """
    output_dir = os.path.join(os.getcwd(), "Progressive")
    os.makedirs(output_dir, exist_ok=True)
    try:
        error_path = find_error_file(state)
    except FileNotFoundError as exc:
        print(str(exc))
        return

    agent_urls = parse_agent_urls_from_error_log(error_path)
    city_urls = parse_city_urls_from_error_log(error_path)
    if not agent_urls and not city_urls:
        print(f"No agent or city URLs found in {error_path}. Nothing to retry.")
        return

    output_path = os.path.join(output_dir, f"{state}Agents.csv")
    commercial_output_path = os.path.join(output_dir, f"{state}CommercialAgents.csv")
    total_agents_from_cities = 0
    total_commercial_from_cities = 0

    if agent_urls:
        print(f"Retrying {len(agent_urls)} agent pages listed in {error_path}...")
        successful_agents = []
        for url in agent_urls:
            try:
                agent_data = process_agent_page(url)
                successful_agents.append(agent_data)
            except Exception as exc:
                log_error(error_path, f"Retry failed for {url}: {exc}")

        if successful_agents:
            write_agents_to_csv(output_path, FIELDNAMES, successful_agents)
            commercial_agents = [
                agent for agent in successful_agents
                if agent[COLUMN_MAPPING["commercial"]].upper() == "Y"
            ]
            if commercial_agents:
                write_agents_to_csv(commercial_output_path, FIELDNAMES, commercial_agents)

            print(
                f"Appended {len(successful_agents)} retried agents to {output_path} "
                f"and {len(commercial_agents)} to {commercial_output_path}."
            )
        else:
            print("No agent pages were successfully retried.")

    if city_urls:
        print(f"Retrying {len(city_urls)} city pages listed in {error_path}...")
        for city_url in city_urls:
            agents_added, commercial_added = process_city_for_state(
                city_url, output_path, commercial_output_path, error_path
            )
            total_agents_from_cities += agents_added
            total_commercial_from_cities += commercial_added

        if total_agents_from_cities:
            print(
                f"Appended {total_agents_from_cities} agents from city retries to {output_path} "
                f"and {total_commercial_from_cities} to {commercial_output_path}."
            )
        else:
            print("No city pages were successfully retried.")

def scrape_state(state):
    """
    Scrapes all the cities in a given state:
     - Constructs the state URL.
     - Fetches and parses the list of cities.
     - For each city, processes agent pages using shared helper functions.
     - Writes agent data to a CSV file and logs errors.
    """
    output_dir = os.path.join(os.getcwd(), "Progressive")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{state}Agents.csv")
    commercial_output_path = os.path.join(output_dir, f"{state}CommercialAgents.csv")
    error_path = os.path.join(output_dir, f"{state}Errors.txt")

    base_url = "https://www.progressiveagent.com/local-agent"
    state_url = f"{base_url}/{state}/"
    print(f"Fetching state page: {state_url}")

    try:
        state_html = fetch_html(state_url)
    except Exception as e:
        error_message = f"Error fetching state page {state_url}: {e}"
        log_error(error_path, error_message)
        sys.exit(1)
    
    try:
        city_links = parse_state_city_links(state_html)
    except Exception as e:
        error_message = f"Error parsing state page: {e}"
        log_error(error_path, error_message)
        sys.exit(1)

    if not city_links:
        print("No city links found on the state page.")
        sys.exit(1)
    

    for city_url in city_links:
        print(f"Getting agents for city URL: {city_url}")
        agent_results = collect_city_agents(city_url, error_path)
        if agent_results:
            write_agents_to_csv(output_path, FIELDNAMES, agent_results)
            commercial_agents = [agent for agent in agent_results if agent[COLUMN_MAPPING["commercial"]].upper() == "Y"]
            if commercial_agents:
                write_agents_to_csv(commercial_output_path, FIELDNAMES, commercial_agents)
        

def scrape_city(city_link):
    """
    Scrapes a single city page:
     - Fetches the page and extracts agent links.
     - Processes each agent page.
     - Writes results into a CSV file.
    """
    print(f"Fetching city page: {city_link}")

    # Derive output file names based on URL segments.
    parts = [seg for seg in city_link.rstrip("/").split("/") if seg]
    if len(parts) >= 3:
        state = parts[-2]  # e.g. 'pennsylvania'
        city = parts[-1]   # e.g. 'apollo'
    else:
        state, city = "Unknown", "Unknown"

    output_dir = os.path.join(os.getcwd(), "Progressive")
    os.makedirs(output_dir, exist_ok=True)
    output_filename = f"{state}_{city}_Agents.csv"
    output_path = os.path.join(output_dir, output_filename)
    error_filename = f"{state}_{city}_Errors.txt"
    error_path = os.path.join(output_dir, error_filename)

    agent_results = collect_city_agents(city_link, error_path)
    if not agent_results:
        print("No agents collected for the provided city. See error log for details.")
        sys.exit(1)

    write_agents_to_csv(output_path, FIELDNAMES, agent_results)
    print(f"Processed {len(agent_results)} agents. Output saved to {output_path}")

def scrape_agency(agent_url):
    """
    Scrapes a single agency page:
     - Fetches the agency page.
     - Extracts agent data and the "What we offer:" section.
     - Saves the result in a CSV file.
    """
    print(f"Fetching agency page: {agent_url}")
    parts = [seg for seg in agent_url.rstrip("/").split("/") if seg]
    if len(parts) >= 4:
        state = parts[1]
        city = parts[2]
        agency = parts[3]
    else:
        state, city, agency = "Unknown", "Unknown", "Unknown"
    
    output_dir = os.path.join(os.getcwd(), "Progressive")
    os.makedirs(output_dir, exist_ok=True)
    output_filename = f"{state}_{city}_{agency}_Agent.csv"
    output_path = os.path.join(output_dir, output_filename)
    error_filename = f"{state}_{city}_{agency}_Errors.txt"
    error_path = os.path.join(output_dir, error_filename)

    try:
        agency_html = fetch_html(agent_url)
    except Exception as e:
        error_message = f"Error fetching agency page {agent_url}: {e}"
        log_error(error_path, error_message)
        sys.exit(1)
    
    try:
        agent_data = process_agent_page(agent_url)
    except Exception as e:
        error_message = f"Error processing agent page {agent_url}: {e}"
        log_error(error_path, error_message)
        sys.exit(1)

    write_agents_to_csv(output_path, FIELDNAMES, [agent_data])
    print(f"Processed agency page. Output saved to {output_path}")

def main():
    parser = argparse.ArgumentParser(
        description="Scrape Progressive Agent pages.\n"
                    "Run in state mode by supplying a state (e.g., 'pennsylvania'),\n"
                    "or pass a full URL using --url for a city page or an agency page."
    )
    parser.add_argument("state", nargs="?", help="State code to scrape (e.g., pennsylvania)")
    parser.add_argument("--url", help="Full URL to a city page (e.g., 'https://www.progressiveagent.com/local-agent/pennsylvania/apollo/') or an agency page (e.g., 'https://www.progressiveagent.com/local-agent/pennsylvania/apollo/agency-name/')")
    parser.add_argument(
        "--retry-errors",
        action="store_true",
        help="Retry the agent URLs listed in the state's error log instead of running a full scrape.",
    )
    args = parser.parse_args()

    if args.url:
        parsed = urlparse(args.url)
        path_segments = [seg for seg in parsed.path.split("/") if seg]
        # Expected URL structures:
        # City mode: ["local-agent", "state", "city"]  --> 3 segments
        # Agency mode: ["local-agent", "state", "city", "agency"]  --> 4 segments
        if len(path_segments) == 3:
            scrape_city(args.url)
        elif len(path_segments) == 4:
            scrape_agency(args.url)
        else:
            print("Unrecognized URL format. Please supply a state, a city URL, or an agency URL.")
            sys.exit(1)
    elif args.retry_errors:
        if not args.state:
            parser.error("--retry-errors requires a state to be specified.")
        retry_failed_agents(args.state)
    elif args.state:
        scrape_state(args.state)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
