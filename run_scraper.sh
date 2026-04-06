#!/usr/bin/env bash
set -euo pipefail

# Generate the latest list of states before scraping.
python state_scraper.py --save-states

states_file="output/states.txt"

if [[ ! -f "$states_file" ]]; then
  echo "Expected $states_file to exist after running --save-states." >&2
  exit 1
fi

while IFS= read -r state; do
  python state_scraper.py "$state"
done < "$states_file"
