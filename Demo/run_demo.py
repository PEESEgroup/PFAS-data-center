"""Run all illustrative scenarios and write quarterly and aggregate CSVs."""

import csv
import json
from math import isfinite
from pathlib import Path

from burden_model import calculate_burden, prepare_factors
from cooling_model import size_cooling
from energy_model import calculate_energy
from material_flow_model import coolant_flows
from scale_model import project_scale
from scenario_model import apply_scenario

HERE = Path(__file__).resolve().parent


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load_inputs(input_dir):
    settings = json.loads((input_dir / "illustrative_settings.json").read_text())
    scenarios = json.loads((input_dir / "illustrative_scenarios.json").read_text())
    rows = read_csv(input_dir / "illustrative_quarterly.csv")
    if not rows or [r["period"] for r in rows] != [f"Q{i:02}" for i in range(1, len(rows) + 1)]:
        raise ValueError("Periods must be consecutive: Q01, Q02, ...")
    for row in rows:
        for key in ("training_demand_pflops", "inference_demand_pflops"):
            row[key] = float(row[key])
            if not isfinite(row[key]) or row[key] < 0:
                raise ValueError(f"Invalid demand in {row['period']}")
    for key in ("rack_gpu_kw", "gpu_to_it_factor", "quarter_hours",
                "training_pflops_per_rack", "inference_pflops_per_rack"):
        if not isfinite(settings[key]) or settings[key] <= 0:
            raise ValueError(f"{key} must be positive")
    life = settings["rack_lifetime_quarters"]
    if not isinstance(life, int) or life <= 0:
        raise ValueError("rack_lifetime_quarters must be a positive integer")
    for key in ("liquid_share", "training_utilization", "inference_utilization",
                "idle_power_fraction", "max_power_fraction"):
        if not 0 <= settings[key] <= 1:
            raise ValueError(f"{key} must be between zero and one")
    if settings["idle_power_fraction"] > settings["max_power_fraction"]:
        raise ValueError("Idle power must not exceed maximum power")
    for phase in settings["phases"].values():
        if (not all(isfinite(v) for v in phase.values()) or phase["pue"] < 1
                or phase["litres_per_kw"] <= 0 or phase["density_kg_per_litre"] <= 0
                or not 0 <= phase["annual_loss_fraction"] < 1):
            raise ValueError("Invalid cooling phase parameters")
    if not scenarios:
        raise ValueError("At least one scenario is required")
    factors = prepare_factors(read_csv(input_dir / "illustrative_impact_factors.csv"), settings["phases"])
    return rows, settings, scenarios, factors


def run_model(rows, settings, scenarios, factors):
    tables = {name: [] for name in ("scale_results", "material_flows", "energy_results",
                                   "burden_results", "scenario_summary")}
    scale = project_scale(rows, settings)
    for quarter in scale:
        for workload in ("training", "inference"):
            tables["scale_results"].append({"period": quarter["period"],
                                           "workload": workload, **quarter[workload]})
    for name, strategy in scenarios.items():
        config = apply_scenario(settings, strategy)
        for phase_name, phase in config["phases"].items():
            inventory = bank = 0.0
            summary = dict.fromkeys(("virgin_coolant_kg", "treated_coolant_kg",
                                     "recovered_coolant_kg", "cooling_kwh",
                                     "CC_kg_co2e", "HTC_ctuh", "CED_mj_eq"), 0.0)
            for quarter in scale:
                key = {"period": quarter["period"], "scenario": name, "phase": phase_name}
                cooling = size_cooling(quarter, config, phase)
                flows = coolant_flows(cooling, inventory, bank, phase, config["recovery_rate"])
                inventory, bank = flows["installed_coolant_kg"], flows["recovery_bank_kg"]
                energy = calculate_energy(quarter, config, phase)
                burdens, totals = calculate_burden(flows, energy, phase_name, factors)
                tables["material_flows"].append({**key, "liquid_it_kw": cooling["liquid_it_kw"], **flows})
                tables["energy_results"].append({**key, **energy})
                tables["burden_results"].extend({**key, **item} for item in burdens)
                for field in ("virgin_coolant_kg", "treated_coolant_kg", "recovered_coolant_kg"):
                    summary[field] += flows[field]
                summary["cooling_kwh"] += energy["cooling_kwh"]
                for indicator, field in (("CC", "CC_kg_co2e"), ("HTC", "HTC_ctuh"), ("CED", "CED_mj_eq")):
                    summary[field] += totals[indicator]
            tables["scenario_summary"].append({"scenario": name, "phase": phase_name,
                                               **summary, "final_inventory_kg": inventory,
                                               "final_recovery_bank_kg": bank})
    return tables


def main():
    tables = run_model(*load_inputs(HERE / "input"))
    output_dir = HERE / "output"
    output_dir.mkdir(exist_ok=True)
    for name, rows in tables.items():
        with (output_dir / f"{name}.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=rows[0])
            writer.writeheader()
            writer.writerows(rows)
    print(f"Wrote {len(tables)} CSV files to {output_dir} (synthetic example only)")


if __name__ == "__main__":
    main()
