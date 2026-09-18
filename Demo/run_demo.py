"""Run the small, deterministic AI cooling example."""

import csv
import json
from pathlib import Path

from burden_model import climate_change
from cooling_model import calculate_cooling
from scale_model import project_scale


HERE = Path(__file__).resolve().parent


def read_quarters(path):
    with path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError("quarterly.csv is empty")
    return [
        {key: value if key == "period" else float(value) for key, value in row.items()}
        for row in rows
    ]


def read_retirement(path):
    with path.open(newline="") as handle:
        probabilities = [float(row["probability"]) for row in csv.DictReader(handle)]
    if not probabilities or any(value < 0 for value in probabilities) or abs(sum(probabilities) - 1.0) > 1e-8:
        raise ValueError("Retirement probabilities must be nonnegative and sum to one")
    return probabilities


def main():
    input_dir = HERE / "input"
    rows = read_quarters(input_dir / "quarterly.csv")
    retirement = read_retirement(input_dir / "retirement.csv")
    settings = json.loads((input_dir / "settings.json").read_text())
    scale = project_scale(rows, retirement, settings)

    results = []
    previous_inventory = {"single": 0.0, "two": 0.0}
    for row, quarter in zip(rows, scale):
        for phase in ("single", "two"):
            cooling = calculate_cooling(quarter, row, phase, settings, previous_inventory[phase])
            previous_inventory[phase] = cooling["coolant_inventory_kg"]
            impacts = climate_change(cooling, phase, settings)
            results.append({
                "period": row["period"],
                "phase": phase,
                "training_racks": quarter["training"]["rack_stock"],
                "inference_racks": quarter["inference"]["rack_stock"],
                **cooling,
                **impacts,
            })

    output = HERE / "output" / "demo_results.csv"
    output.parent.mkdir(exist_ok=True)
    with output.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)
    print(f"Wrote {len(results)} rows to {output}")


if __name__ == "__main__":
    main()
