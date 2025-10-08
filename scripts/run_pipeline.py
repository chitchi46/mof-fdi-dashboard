#!/usr/bin/env python3
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from typing import Dict, List

# Ensure local src/ is importable when running from repo root
_HERE = os.path.dirname(__file__)
_SRC = os.path.abspath(os.path.join(_HERE, "..", "src"))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from mof_investviz.io import write_csv
from mof_investviz.normalize import (
    SCHEMA_HEADERS,
    build_summary_multi_measure,
    normalize_file,
)
from mof_investviz.schema import copy_schema_to_build, schema_meta
from mof_investviz.ui import write_index_html


def find_input_files(path: str) -> List[str]:
    if os.path.isdir(path):
        # Grab CSV files directly under the directory
        files = sorted(glob.glob(os.path.join(path, "*.csv")))
    else:
        files = [path]
    return [f for f in files if os.path.isfile(f)]


def main() -> None:
    ap = argparse.ArgumentParser(description="Run minimal normalization pipeline")
    ap.add_argument("--input", "-i", required=True, help="CSV file or directory containing CSVs")
    ap.add_argument("--build-dir", "-b", default="build", help="Output build directory")
    args = ap.parse_args()

    os.makedirs(args.build_dir, exist_ok=True)
    files = find_input_files(args.input)
    if not files:
        raise SystemExit("No CSV files found in input")

    parse_log: Dict[str, object] = {
        "pipeline": "mvp",
        "inputs": [],
        **schema_meta(),
    }

    all_norm: List[Dict[str, object]] = []
    for path in files:
        result = normalize_file(path)
        all_norm.extend(result.rows)
        parse_log["inputs"].append({
            "path": result.meta.get("path"),
            "encoding": result.meta.get("encoding"),
            "delimiter": result.meta.get("delimiter"),
            "header_rows": result.meta.get("header_rows"),
            "headers": result.headers,
            "unit_detected": result.meta.get("unit_detected"),
            "scale_factor": result.meta.get("scale_factor"),
            "side": result.meta.get("side"),
            "metric": result.meta.get("metric"),
            "stats": result.stats,
        })

    # Write normalized CSV
    out_csv = os.path.join(args.build_dir, "normalized.csv")
    write_csv(out_csv, all_norm, SCHEMA_HEADERS)

    # Summary for dashboard (multi-measure)
    summary = build_summary_multi_measure(all_norm)
    with open(os.path.join(args.build_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # Copy schema for reference
    copy_schema_to_build(args.build_dir)

    # Write parse_log.json
    with open(os.path.join(args.build_dir, "parse_log.json"), "w", encoding="utf-8") as f:
        json.dump(parse_log, f, ensure_ascii=False, indent=2)

    # Optional: year x measure pivot for spreadsheet analysis
    pivot_map = {}
    measures = set()
    for r in all_norm:
        y = r.get('year')
        if y is None:
            continue
        m = str(r.get('measure'))
        v = float(r.get('value_100m_yen') or 0.0)
        measures.add(m)
        d = pivot_map.setdefault(int(y), {})
        d[m] = d.get(m, 0.0) + v
    measures_sorted = sorted(measures)
    pivot_headers = ['year'] + measures_sorted
    pivot_rows = []
    for y in sorted(pivot_map.keys()):
        row = {'year': y}
        row.update({m: pivot_map[y].get(m, 0.0) for m in measures_sorted})
        pivot_rows.append(row)
    write_csv(os.path.join(args.build_dir, 'pivot_year_measure.csv'), pivot_rows, pivot_headers)

    # Write dashboard page
    write_index_html(args.build_dir)

    print(f"Wrote: {out_csv}")
    print(f"Wrote: {os.path.join(args.build_dir, 'summary.json')}")
    print(f"Wrote: {os.path.join(args.build_dir, 'parse_log.json')}")
    print(f"Wrote: {os.path.join(args.build_dir, 'pivot_year_measure.csv')}")
    print(f"Wrote: {os.path.join(args.build_dir, 'index.html')}")
    print("Next: python scripts/serve_dashboard.py --build-dir", args.build_dir)


if __name__ == "__main__":
    main()
