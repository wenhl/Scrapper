#!/usr/bin/env python3
import os
import glob
import argparse
import pandas as pd
import re


def csvs_to_excel(input_dir: str, output_file: str):
    # Build a glob pattern for CSVs in the given directory
    pattern = os.path.join(input_dir, "*.csv")
    csv_files = glob.glob(pattern)
    if not csv_files:
        print(f"No CSV files found in {input_dir!r}.")
        return

    # Create the Excel workbook
    with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
        for csv_path in csv_files:
            df = pd.read_csv(csv_path)

            # Derive sheet name (filename without extension, <=31 chars)
            base = os.path.splitext(os.path.basename(csv_path))[0][:31]
            sheet_name = re.split(r"(?<=[a-z])(?=[A-Z])", base, maxsplit=1)[0][:31]
            print(f"base = {base}")
            print(sheet_name)

            df.to_excel(writer, sheet_name=sheet_name, index=False)
            print(f" • Wrote {os.path.basename(csv_path)} -> sheet '{sheet_name}'")

    print(f"\nDone! {len(csv_files)} sheets written to {output_file!r}.")


def main():
    parser = argparse.ArgumentParser(
        description="Combine all CSV files in a directory into one XLSX workbook (one sheet per CSV)."
    )
    parser.add_argument(
        "input_dir",
        help="Path to the directory containing CSV files.",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="combined.xlsx",
        help="Output Excel filename (default: combined.xlsx).",
    )
    args = parser.parse_args()

    if not os.path.isdir(args.input_dir):
        parser.error(f"{args.input_dir!r} is not a directory.")

    csvs_to_excel(args.input_dir, args.output)


if __name__ == "__main__":
    main()
