"""Run the synthetic data-center model and export its results."""

import argparse
import csv
import hashlib
import json
from pathlib import Path

from analysis import monte_carlo, sensitivity
from model_inputs import load_inputs
from simulation import run_model

HERE = Path(__file__).resolve().parent


def write_results(tables, output):
    output.mkdir(parents=True, exist_ok=True)
    for name, rows in tables.items():
        with (output / f"{name}.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=rows[0])
            writer.writeheader()
            writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=HERE / "input")
    parser.add_argument("--output", type=Path, default=HERE / "output")
    parser.add_argument("--runs", type=int, help="Override the Monte Carlo sample count (at least 2)")
    args = parser.parse_args()
    data = load_inputs(args.input)
    runs = data["settings"]["analysis"]["runs"] if args.runs is None else args.runs
    if runs < 2:
        parser.error("--runs must be at least 2")
    tables = run_model(data)
    tables.update(monte_carlo(data, runs))
    tables["sensitivity_results"] = sensitivity(data)
    write_results(tables, args.output)
    manifest = {
        "data_origin": data["settings"]["data_origin"],
        "monte_carlo_runs": runs, "seed": data["settings"]["analysis"]["seed"],
        "cumulative_start": data["settings"]["cumulative_start"],
        "input_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                         for p in sorted(args.input.glob("illustrative_*"))},
        "rows": {name: len(rows) for name, rows in tables.items()},
    }
    (args.output / "run_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Completed {len(tables['scenario_summary'])} cases and {runs} Monte Carlo runs.")
    print(f"Results: {args.output.resolve()}")


if __name__ == "__main__":
    main()
