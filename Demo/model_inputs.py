"""Read CSV/JSON inputs and check their units and quarterly alignment."""

import csv
import json
from math import isfinite

from burden_model import INDICATOR_UNITS, prepare_factors


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def number(value, name, low=0, high=float("inf")):
    value = float(value)
    if not isfinite(value) or not low <= value <= high:
        raise ValueError(f"Invalid {name}: {value}")
    return value


def load_inputs(folder):
    settings = json.loads((folder / "illustrative_settings.json").read_text())
    strategies = json.loads((folder / "illustrative_scenarios.json").read_text())
    rows = read_csv(folder / "illustrative_quarterly.csv")
    periods = [f"Q{i + 1:02}" for i in range(len(rows))]
    if len(rows) < 2 or [r["period"] for r in rows] != periods:
        raise ValueError("Quarterly rows must be consecutive, beginning at Q01")
    for row in rows:
        for key in row.keys() - {"period"}:
            upper = 1 if "share" in key or "utilization" in key else float("inf")
            lower = 1e-12 if key in ("gpu_pflops", "gpu_board_kw") else 0
            row[key] = number(row[key], key, lower, upper)
    cooling_paths = ("low", "central", "high")
    for name in cooling_paths:
        shares = [r[f"liquid_share_{name}"] for r in rows]
        if any(b < a for a, b in zip(shares, shares[1:])):
            raise ValueError("Cooling shares must be nondecreasing; reverse conversion is not modeled")
    life = read_csv(folder / "illustrative_retirement.csv")
    if [r["age_quarter"] for r in life] != [str(i + 1) for i in range(len(life))]:
        raise ValueError("Retirement ages must begin at one and be consecutive")
    pmf = [number(r["probability"], "retirement probability", 0, 1) for r in life]
    if abs(sum(pmf) - 1) > 1e-10:
        raise ValueError("Retirement probabilities must sum to one")
    for key in ("gpus_per_rack", "rack_mass_kg", "gpu_to_it_factor", "quarter_hours"):
        settings[key] = number(settings[key], key, 1e-12)
    for key in ("training_efficiency", "inference_efficiency"):
        settings[key] = number(settings[key], key, 1e-12, 1)
    for key in ("tokens_per_user_day", "training_runs_per_year"):
        settings[key] = number(settings[key], key)
    for key in ("idle_power_fraction", "max_power_fraction", "recovery_yield"):
        settings[key] = number(settings[key], key, 0, 1)
    if settings["idle_power_fraction"] > settings["max_power_fraction"]:
        raise ValueError("Idle power exceeds maximum power")
    if settings["cumulative_start"] not in periods:
        raise ValueError("Cumulative start must be a modeled quarter")
    for growth in settings["growth"].values():
        for key in ("architecture_factor", "user_factor", "training_frequency_factor"):
            growth[key] = number(growth[key], key, 1e-12)
    for phase in settings["phases"].values():
        for key in ("litres_per_kw", "density_kg_per_litre"):
            phase[key] = number(phase[key], key, 1e-12)
        phase["pue"] = number(phase["pue"], "pue", 1)
        phase["annual_loss_fraction"] = number(phase["annual_loss_fraction"], "loss", 0, 1 - 1e-12)
        phase["evaporation_share"] = number(phase["evaporation_share"], "evaporation_share", 0, 1)
    allowed = {"pue_overhead_factor", "coolant_intensity_factor", "recovery_rate"}
    if not strategies or not settings["growth"] or not settings["phases"]:
        raise ValueError("At least one strategy, growth path and cooling phase are required")
    for strategy in strategies.values():
        if strategy.keys() - allowed:
            raise ValueError("Unknown strategy parameter")
        for key in strategy:
            strategy[key] = number(strategy[key], key, 0 if key == "recovery_rate" else 1e-12, 1)
    grids = {}
    for row in read_csv(folder / "illustrative_electricity.csv"):
        grid = grids.setdefault(row["background"], {})
        if row["period"] in grid:
            raise ValueError("Duplicate electricity factor quarter")
        grid[row["period"]] = {i: number(row[i], i) for i in INDICATOR_UNITS}
    if not grids or any(set(grid) != set(periods) for grid in grids.values()):
        raise ValueError("Each electricity background must cover every quarter")
    analysis = settings["analysis"]
    for key, choices in (("growth", settings["growth"]), ("cooling", cooling_paths),
                         ("strategy", strategies), ("background", grids)):
        if analysis[key] not in choices:
            raise ValueError(f"Unknown analysis {key}")
    if not isinstance(analysis["runs"], int) or analysis["runs"] < 2:
        raise ValueError("Monte Carlo runs must be an integer of at least two")
    for key, value in analysis["relative_ranges"].items():
        number(value, key, 0, 0.9)
    number(analysis["sensitivity_fraction"], "sensitivity_fraction", 0, 0.9)
    factors = prepare_factors(read_csv(folder / "illustrative_impact_factors.csv"), settings["phases"])
    return {"rows": rows, "settings": settings, "strategies": strategies,
            "pmf": pmf, "backgrounds": grids, "factors": factors}
