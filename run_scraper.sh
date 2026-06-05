#!/usr/bin/env bash
set -euo pipefail

carrier="${1:-progressive}"
python_bin="${PYTHON_BIN:-.venv/bin/python}"
custom_states_file="${2:-}"
case "$carrier" in
  progressive)
    carrier_dir="Progressive"
    ;;
  nationwide)
    carrier_dir="Nationwide"
    ;;
  *)
    echo "Unsupported carrier: $carrier" >&2
    exit 1
    ;;
esac
states_file="${custom_states_file:-output/${carrier_dir}/states.txt}"

if [[ -z "$custom_states_file" ]]; then
  "$python_bin" state_scraper.py --carrier "$carrier" --save-states
fi

if [[ ! -f "$states_file" ]]; then
  echo "Expected states file $states_file to exist." >&2
  exit 1
fi

while IFS= read -r state; do
  [[ -z "$state" ]] && continue
  "$python_bin" state_scraper.py --carrier "$carrier" "$state"
done < "$states_file"
