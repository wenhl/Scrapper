import json
import os
import re
import sys
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from scrapers.common import OUTPUT_DIR, fetch_html, log_error, write_agents_to_csv


BASE_URL = "https://agency.nationwide.com"
NATIONWIDE_DIR = os.path.join(OUTPUT_DIR, "Nationwide")
STATE_NAMES = {
    "alabama",
    "alaska",
    "arizona",
    "arkansas",
    "california",
    "colorado",
    "connecticut",
    "delaware",
    "florida",
    "georgia",
    "hawaii",
    "idaho",
    "illinois",
    "indiana",
    "iowa",
    "kansas",
    "kentucky",
    "louisiana",
    "maine",
    "maryland",
    "massachusetts",
    "michigan",
    "minnesota",
    "mississippi",
    "missouri",
    "montana",
    "nebraska",
    "nevada",
    "new hampshire",
    "new jersey",
    "new mexico",
    "new york",
    "north carolina",
    "north dakota",
    "ohio",
    "oklahoma",
    "oregon",
    "pennsylvania",
    "rhode island",
    "south carolina",
    "south dakota",
    "tennessee",
    "texas",
    "utah",
    "vermont",
    "virginia",
    "washington",
    "washington dc",
    "west virginia",
    "wisconsin",
    "wyoming",
}

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
    "offer": "Offer",
}
FIELDNAMES = list(COLUMN_MAPPING.values())


def classify_url(path_segments):
    # City: /<state-code>/<city>/
    # Agency: /<state-code>/<city>/<postal-code>/<agency>/
    if len(path_segments) == 2:
        return "city"
    if len(path_segments) >= 3:
        return "agency"
    return None


def normalize_url(href):
    return urljoin(BASE_URL, href)


def dedupe(values):
    seen = set()
    results = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            results.append(value)
    return results


def text_or_empty(element):
    return element.get_text(" ", strip=True) if element else ""


def save_states_list():
    print(f"Fetching states from {BASE_URL}")
    html = fetch_html(BASE_URL)
    state_codes = parse_state_links(html)
    if not state_codes:
        raise RuntimeError("No states found on the Nationwide base URL page.")

    os.makedirs(NATIONWIDE_DIR, exist_ok=True)
    states_path = os.path.join(NATIONWIDE_DIR, "states.txt")
    with open(states_path, "w", encoding="utf-8") as states_file:
        for state_code in state_codes:
            states_file.write(f"{state_code}\n")
    print(f"Saved {len(state_codes)} states to {states_path}")


def parse_state_links(html):
    soup = BeautifulSoup(html, "html.parser")
    state_codes = []
    for anchor in soup.find_all("a", href=True):
        anchor_text = anchor.get_text(" ", strip=True).lower()
        if anchor_text not in STATE_NAMES:
            continue

        parsed = urlparse(normalize_url(anchor["href"]))
        if parsed.netloc != "agency.nationwide.com":
            continue
        segments = [segment for segment in parsed.path.split("/") if segment]
        if segments and re.fullmatch(r"[a-z]{2}", segments[0]):
            state_codes.append(segments[0])
    return sorted(dedupe(state_codes))


def parse_state_city_links(html, state):
    soup = BeautifulSoup(html, "html.parser")
    city_links = []
    for anchor in soup.find_all("a", href=True):
        url = normalize_url(anchor["href"])
        parsed = urlparse(url)
        if parsed.netloc != "agency.nationwide.com":
            continue
        segments = [segment for segment in parsed.path.split("/") if segment]
        if len(segments) == 2 and segments[0].lower() == state.lower():
            city_links.append(url)
    city_links = sorted(dedupe(city_links))
    print(f"Found {len(city_links)} city links in the state page.")
    return city_links


def parse_city_agent_links(html):
    soup = BeautifulSoup(html, "html.parser")
    agent_links = []
    for anchor in soup.find_all("a", href=True):
        url = normalize_url(anchor["href"])
        parsed = urlparse(url)
        if parsed.netloc != "agency.nationwide.com":
            continue
        segments = [segment for segment in parsed.path.split("/") if segment]
        if len(segments) >= 3 and re.fullmatch(r"[a-z]{2}", segments[0]):
            agent_links.append(url)
    agent_links = sorted(dedupe(agent_links))
    print(f"Found {len(agent_links)} agent links in the city page.")
    return agent_links


def iter_json_ld_objects(value):
    if isinstance(value, dict):
        yield value
        graph = value.get("@graph")
        if isinstance(graph, list):
            for item in graph:
                yield from iter_json_ld_objects(item)
    elif isinstance(value, list):
        for item in value:
            yield from iter_json_ld_objects(item)


def extract_json_ld_objects(html):
    soup = BeautifulSoup(html, "html.parser")
    objects = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw_json = script.get_text(strip=True)
        if not raw_json:
            continue
        try:
            parsed = json.loads(raw_json)
        except json.JSONDecodeError:
            continue
        objects.extend(iter_json_ld_objects(parsed))
    return objects


def first_agency_json(html):
    for item in extract_json_ld_objects(html):
        item_type = item.get("@type", "")
        if isinstance(item_type, list):
            types = {str(value).lower() for value in item_type}
        else:
            types = {str(item_type).lower()}
        if types.intersection({"insuranceagency", "localbusiness"}):
            if item.get("address") or item.get("telephone") or item.get("name"):
                return item
    return {}


def extract_products(html):
    soup = BeautifulSoup(html, "html.parser")
    scoped_products = [
        item.get_text(" ", strip=True)
        for item in soup.select("li.Core-product")
        if item.get_text(" ", strip=True)
    ]
    if scoped_products:
        return ", ".join(dedupe(scoped_products))

    header = soup.find(
        string=lambda text: text and "insurable products" in text.lower()
    )
    if header:
        product_list = header.find_parent().find_next("ul")
        if product_list:
            products = [item.get_text(" ", strip=True) for item in product_list.find_all("li")]
            products = [product for product in products if product]
            if products:
                return ", ".join(dedupe(products))

    product_names = {
        "All business insurance",
        "Auto",
        "Business auto",
        "Business property",
        "Businessowners policy (BOP)",
        "Commercial",
        "Commercial agribusiness",
        "Condo",
        "Farm",
        "Financial",
        "Home",
        "Human Services",
        "Life",
        "Powersports",
        "Renters",
    }
    products = []
    for text in soup.stripped_strings:
        if text in product_names:
            products.append(text)
    return ", ".join(dedupe(products))


def extract_languages(html):
    soup = BeautifulSoup(html, "html.parser")
    for header in soup.select(".AgentAbout-sectionTitle"):
        if "languages spoken" not in header.get_text(" ", strip=True).lower():
            continue
        section = header.find_parent(class_="AgentAbout-section")
        if not section:
            continue
        languages = [
            item.get_text(" ", strip=True)
            for item in section.select(".AgentAbout-sectionListItem, li")
            if item.get_text(" ", strip=True)
        ]
        if languages:
            return ", ".join(dedupe(languages))

        section_text = section.get_text(" ", strip=True)
        return re.sub(r"^Languages Spoken\\s*", "", section_text, flags=re.I).strip()

    faq_answer = soup.find(
        string=lambda text: text and "following languages:" in text.lower()
    )
    if faq_answer:
        return faq_answer.split(":", 1)[-1].strip()

    return ""


def microdata_value(scope, itemprop):
    element = scope.find(attrs={"itemprop": itemprop}) if scope else None
    if not element:
        return ""
    if element.has_attr("content"):
        return element["content"].strip()
    if element.has_attr("href") and itemprop in {"url", "email"}:
        value = element["href"].strip()
        return value.removeprefix("mailto:")
    return element.get_text(" ", strip=True)


def extract_contact_links(html):
    soup = BeautifulSoup(html, "html.parser")
    email = ""
    website = ""
    ignored_hosts = {
        "nationwidefinancial.com",
        "www.nationwidefinancial.com",
        "www.petinsurance.com",
        "petinsurance.com",
        "www.farmagentfinder.com",
        "farmagentfinder.com",
        "maps.google.com",
        "www.google.com",
        "portal.hud.gov",
    }
    ignored_social_hosts = {
        "facebook.com",
        "www.facebook.com",
        "twitter.com",
        "x.com",
        "linkedin.com",
        "www.linkedin.com",
        "instagram.com",
        "www.instagram.com",
        "youtube.com",
        "www.youtube.com",
    }

    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        if href.startswith("mailto:") and not email:
            email = href.removeprefix("mailto:").split("?", 1)[0]
            continue

        parsed = urlparse(href)
        if parsed.scheme not in {"http", "https"}:
            continue
        host = parsed.netloc.lower()
        if "nationwide" in host:
            continue
        if host in ignored_hosts or host in ignored_social_hosts:
            continue
        if not website:
            website = href

    return email, website


def extract_microdata_agent_data(html, agent_url, offer_info, language_info):
    soup = BeautifulSoup(html, "html.parser")
    scope = soup.find("main", itemtype=lambda value: value and "InsuranceAgency" in value)
    name_element = soup.find(id="location-name") or soup.select_one(".Core-agencyName")
    name = text_or_empty(name_element)
    if " in " in name:
        name = name.split(" in ", 1)[0].strip()
    email, website = extract_contact_links(html)

    return {
        COLUMN_MAPPING["agency_name"]: name,
        COLUMN_MAPPING["street_address"]: microdata_value(scope, "streetAddress"),
        COLUMN_MAPPING["city"]: microdata_value(scope, "addressLocality"),
        COLUMN_MAPPING["state"]: microdata_value(scope, "addressRegion"),
        COLUMN_MAPPING["postal_code"]: microdata_value(scope, "postalCode"),
        COLUMN_MAPPING["email"]: (microdata_value(scope, "email") or email).lower(),
        COLUMN_MAPPING["phone"]: microdata_value(scope, "telephone"),
        COLUMN_MAPPING["language"]: language_info,
        COLUMN_MAPPING["web_site"]: microdata_value(scope, "url") or website,
        COLUMN_MAPPING["link"]: agent_url,
        COLUMN_MAPPING["offer"]: offer_info,
        COLUMN_MAPPING["commercial"]: "Y" if re.search(r"\b(commercial|business)\b", offer_info, re.I) else "N",
    }


def extract_agent_data_from_json(agent_json, agent_url, offer_info, language_info):
    address = agent_json.get("address") or {}
    if isinstance(address, list):
        address = address[0] if address else {}

    return {
        COLUMN_MAPPING["agency_name"]: agent_json.get("name", ""),
        COLUMN_MAPPING["street_address"]: address.get("streetAddress", ""),
        COLUMN_MAPPING["city"]: address.get("addressLocality", ""),
        COLUMN_MAPPING["state"]: address.get("addressRegion", ""),
        COLUMN_MAPPING["postal_code"]: address.get("postalCode", ""),
        COLUMN_MAPPING["email"]: agent_json.get("email", "").lower(),
        COLUMN_MAPPING["phone"]: agent_json.get("telephone", ""),
        COLUMN_MAPPING["language"]: language_info,
        COLUMN_MAPPING["web_site"]: agent_json.get("url", ""),
        COLUMN_MAPPING["link"]: agent_url,
        COLUMN_MAPPING["offer"]: offer_info,
        COLUMN_MAPPING["commercial"]: "Y" if re.search(r"\b(commercial|business)\b", offer_info, re.I) else "N",
    }


def process_agent_page(agent_url):
    html = fetch_html(agent_url)
    offer_info = extract_products(html)
    language_info = extract_languages(html)
    agent_json = first_agency_json(html)
    if agent_json:
        agent_data = extract_agent_data_from_json(
            agent_json, agent_url, offer_info, language_info
        )
    else:
        agent_data = extract_microdata_agent_data(
            html, agent_url, offer_info, language_info
        )

    if not agent_data[COLUMN_MAPPING["agency_name"]]:
        soup = BeautifulSoup(html, "html.parser")
        heading = soup.find(["h1", "h2"])
        agent_data[COLUMN_MAPPING["agency_name"]] = text_or_empty(heading)
    return agent_data


def process_agents(agent_links, error_path):
    results = []
    for index, agent_link in enumerate(agent_links, start=1):
        print(f"Processing agent {index}...")
        try:
            results.append(process_agent_page(agent_link))
        except Exception as exc:
            log_error(error_path, f"Error processing agent page {agent_link}: {exc}")
    return results


def collect_city_agents(city_url, error_path):
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
    candidates = [
        os.path.join(NATIONWIDE_DIR, f"{state}Errors.txt"),
        os.path.join(NATIONWIDE_DIR, "error", f"{state}Errors.txt"),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    raise FileNotFoundError(
        f"Could not find an error log for state '{state}'. Looked in: {', '.join(candidates)}"
    )


def parse_agent_urls_from_error_log(error_path):
    prefix = "Error processing agent page "
    urls = []
    with open(error_path, "r", encoding="utf-8") as error_file:
        for raw_line in error_file:
            line = raw_line.strip()
            if line.startswith(prefix):
                urls.append(line[len(prefix):].split(": ", 1)[0].strip())
    return dedupe(urls)


def parse_city_urls_from_error_log(error_path):
    prefixes = ["Error fetching city page ", "No agent links found for city "]
    urls = []
    with open(error_path, "r", encoding="utf-8") as error_file:
        for raw_line in error_file:
            line = raw_line.strip()
            for prefix in prefixes:
                if line.startswith(prefix):
                    urls.append(line[len(prefix):].split(": ", 1)[0].strip())
                    break
    return dedupe(urls)


def write_agent_outputs(output_path, agent_results):
    write_agents_to_csv(output_path, FIELDNAMES, agent_results)
    return len(agent_results)


def process_city_for_state(city_url, output_path, error_path):
    agent_results = collect_city_agents(city_url, error_path)
    if not agent_results:
        return 0
    return write_agent_outputs(output_path, agent_results)


def retry_failed_agents(state):
    os.makedirs(NATIONWIDE_DIR, exist_ok=True)
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

    output_path = os.path.join(NATIONWIDE_DIR, f"{state}Agents.csv")

    if agent_urls:
        successful_agents = []
        print(f"Retrying {len(agent_urls)} agent pages listed in {error_path}...")
        for url in agent_urls:
            try:
                successful_agents.append(process_agent_page(url))
            except Exception as exc:
                log_error(error_path, f"Retry failed for {url}: {exc}")
        if successful_agents:
            agent_count = write_agent_outputs(output_path, successful_agents)
            print(f"Appended {agent_count} retried agents to {output_path}.")

    if city_urls:
        total_agents = 0
        print(f"Retrying {len(city_urls)} city pages listed in {error_path}...")
        for city_url in city_urls:
            agent_count = process_city_for_state(city_url, output_path, error_path)
            total_agents += agent_count
        print(f"Appended {total_agents} agents from city retries to {output_path}.")


def scrape_state(state):
    os.makedirs(NATIONWIDE_DIR, exist_ok=True)
    output_path = os.path.join(NATIONWIDE_DIR, f"{state}Agents.csv")
    error_path = os.path.join(NATIONWIDE_DIR, f"{state}Errors.txt")

    state_url = f"{BASE_URL}/{state.lower()}"
    print(f"Fetching state page: {state_url}")
    try:
        state_html = fetch_html(state_url)
        city_links = parse_state_city_links(state_html, state)
    except Exception as exc:
        log_error(error_path, f"Error processing state page {state_url}: {exc}")
        sys.exit(1)

    if not city_links:
        print("No city links found on the state page.")
        sys.exit(1)

    for city_url in city_links:
        print(f"Getting agents for city URL: {city_url}")
        agent_results = collect_city_agents(city_url, error_path)
        if agent_results:
            write_agent_outputs(output_path, agent_results)


def scrape_city(city_link):
    print(f"Fetching city page: {city_link}")
    parts = [segment for segment in urlparse(city_link).path.split("/") if segment]
    state, city = parts[:2] if len(parts) >= 2 else ("Unknown", "Unknown")

    os.makedirs(NATIONWIDE_DIR, exist_ok=True)
    output_path = os.path.join(NATIONWIDE_DIR, f"{state}_{city}_Agents.csv")
    error_path = os.path.join(NATIONWIDE_DIR, f"{state}_{city}_Errors.txt")

    agent_results = collect_city_agents(city_link, error_path)
    if not agent_results:
        print("No agents collected for the provided city. See error log for details.")
        sys.exit(1)

    write_agents_to_csv(output_path, FIELDNAMES, agent_results)
    print(f"Processed {len(agent_results)} agents. Output saved to {output_path}")


def scrape_agency(agent_url):
    print(f"Fetching agency page: {agent_url}")
    parts = [segment for segment in urlparse(agent_url).path.split("/") if segment]
    if len(parts) >= 3:
        state, city = parts[:2]
        agency = "_".join(parts[2:])
    else:
        state, city, agency = "Unknown", "Unknown", "Unknown"

    os.makedirs(NATIONWIDE_DIR, exist_ok=True)
    output_path = os.path.join(NATIONWIDE_DIR, f"{state}_{city}_{agency}_Agent.csv")
    error_path = os.path.join(NATIONWIDE_DIR, f"{state}_{city}_{agency}_Errors.txt")

    try:
        agent_data = process_agent_page(agent_url)
    except Exception as exc:
        log_error(error_path, f"Error processing agent page {agent_url}: {exc}")
        sys.exit(1)

    write_agents_to_csv(output_path, FIELDNAMES, [agent_data])
    print(f"Processed agency page. Output saved to {output_path}")
