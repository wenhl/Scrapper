#!/usr/bin/env python3
import argparse
import sys
from urllib.parse import urlparse

from scrapers import nationwide, progressive


CARRIERS = {
    "progressive": progressive,
    "nationwide": nationwide,
}


def get_carrier(name):
    try:
        return CARRIERS[name]
    except KeyError:
        valid_carriers = ", ".join(sorted(CARRIERS))
        raise ValueError(f"Unknown carrier '{name}'. Expected one of: {valid_carriers}")


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Scrape insurance agency directory pages.\n"
            "Run in state mode by supplying a state, or pass --url for a city or agency page."
        )
    )
    parser.add_argument("state", nargs="?", help="State slug/code to scrape.")
    parser.add_argument(
        "--carrier",
        choices=sorted(CARRIERS),
        default="progressive",
        help="Carrier directory to scrape. Defaults to progressive.",
    )
    parser.add_argument("--url", help="Full URL to a city page or agency page.")
    parser.add_argument(
        "--retry-errors",
        action="store_true",
        help="Retry URLs listed in the carrier/state error log instead of running a full scrape.",
    )
    parser.add_argument(
        "--save-states",
        action="store_true",
        help="Fetch the carrier directory and write its state list.",
    )
    args = parser.parse_args()

    carrier = get_carrier(args.carrier)

    if args.save_states:
        carrier.save_states_list()
        return

    if args.url:
        parsed = urlparse(args.url)
        path_segments = [seg for seg in parsed.path.split("/") if seg]
        page_type = carrier.classify_url(path_segments)
        if page_type == "city":
            carrier.scrape_city(args.url)
        elif page_type == "agency":
            carrier.scrape_agency(args.url)
        else:
            print("Unrecognized URL format for selected carrier.")
            sys.exit(1)
    elif args.retry_errors:
        if not args.state:
            parser.error("--retry-errors requires a state to be specified.")
        carrier.retry_failed_agents(args.state)
    elif args.state:
        carrier.scrape_state(args.state)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
