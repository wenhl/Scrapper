#!/usr/bin/env python3
import os
import glob
import argparse
import pandas as pd
import re


def sheet_name_from_csv(csv_path: str, used_names: set[str]) -> str:
    base = os.path.splitext(os.path.basename(csv_path))[0]
    base = re.sub(r"Agents$", "", base)
    base = re.sub(r"Agent$", "", base)
    base = base.strip("_-") or "Sheet"
    sheet_name = base[:31]

    if sheet_name not in used_names:
        used_names.add(sheet_name)
        return sheet_name

    index = 2
    while True:
        suffix = f"_{index}"
        candidate = f"{sheet_name[:31 - len(suffix)]}{suffix}"
        if candidate not in used_names:
            used_names.add(candidate)
            return candidate
        index += 1


def commercial_rows(dataframe: pd.DataFrame) -> pd.DataFrame:
    if "Commercial" not in dataframe.columns:
        return dataframe.iloc[0:0]
    return dataframe[
        dataframe["Commercial"].fillna("").astype(str).str.strip().str.upper() == "Y"
    ]


def csvs_to_excel(
    input_dir: str,
    output_file: str,
    csv_files: list[str] | None = None,
    commercial_only: bool = False,
):
    if csv_files is None:
        pattern = os.path.join(input_dir, "*.csv")
        csv_files = glob.glob(pattern)

    csv_files = sorted(csv_files)
    if not csv_files:
        print(f"No CSV files found for {output_file!r}.")
        return

    used_names = set()
    with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
        for csv_path in csv_files:
            df = pd.read_csv(csv_path)
            if commercial_only:
                df = commercial_rows(df)
            sheet_name = sheet_name_from_csv(csv_path, used_names)
            df.to_excel(writer, sheet_name=sheet_name, index=False)
            print(f" • Wrote {os.path.basename(csv_path)} -> sheet '{sheet_name}'")

    print(f"\nDone! {len(csv_files)} sheets written to {output_file!r}.")


def agent_csvs(input_dir: str):
    pattern = os.path.join(input_dir, "*.csv")
    csv_files = sorted(glob.glob(pattern))
    return [
        csv_path for csv_path in csv_files
        if os.path.basename(csv_path).endswith("Agents.csv")
        and not os.path.basename(csv_path).endswith("CommercialAgents.csv")
    ]


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Combine CSV files in a directory into Excel workbooks. "
            "By default, writes one workbook with every CSV. "
            "Use --all-output and/or --commercial-output to create all-agent "
            "and Commercial=Y workbooks from '*Agents.csv' files."
        )
    )
    parser.add_argument(
        "input_dir",
        help="Path to the directory containing CSV files.",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="combined.xlsx",
        help="Output Excel filename for all CSVs (default: combined.xlsx).",
    )
    parser.add_argument(
        "--all-output",
        help="Output workbook for all rows in '*Agents.csv' files.",
    )
    parser.add_argument(
        "--commercial-output",
        help="Output workbook filtered to rows where Commercial is Y.",
    )
    args = parser.parse_args()

    if not os.path.isdir(args.input_dir):
        parser.error(f"{args.input_dir!r} is not a directory.")

    if args.all_output or args.commercial_output:
        csv_files = agent_csvs(args.input_dir)
        if args.all_output:
            csvs_to_excel(args.input_dir, args.all_output, csv_files)
        if args.commercial_output:
            csvs_to_excel(
                args.input_dir,
                args.commercial_output,
                csv_files,
                commercial_only=True,
            )
    else:
        csvs_to_excel(args.input_dir, args.output)


if __name__ == "__main__":
    main()
