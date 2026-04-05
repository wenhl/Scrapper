# read the states from the file
while IFS= read -r state; do
  # run the Python script with the current state
  python state_scraper.py "$state"
done < states.txt