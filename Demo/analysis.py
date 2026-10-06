"""Monte Carlo propagation and one-at-a-time sensitivity for a selected case."""

from collections import defaultdict
from copy import deepcopy
import random
from statistics import mean

from simulation import FLOW_TOTALS, IMPACTS, run_case

METRICS = (*FLOW_TOTALS, "cooling_kwh", *IMPACTS.values())


def perturb(data, parameter, factor):
    if parameter == "demand":
        for row in data["rows"]:
            row["parameters_billion"] *= factor
            row["training_flop_per_run"] *= factor
    elif parameter == "hardware":
        for row in data["rows"]:
            row["gpu_pflops"] *= factor
            row["gpu_board_kw"] *= factor
    elif parameter == "liquid_share":
        data["settings"]["share_multiplier"] = factor
    elif parameter == "impact_factors":
        data["factors"] = {key: value * factor for key, value in data["factors"].items()}
    elif parameter in ("coolant_intensity", "pue_overhead"):
        for phase in data["settings"]["phases"].values():
            if parameter == "coolant_intensity":
                phase["litres_per_kw"] *= factor
            else:
                phase["pue"] = 1 + (phase["pue"] - 1) * factor
    else:
        raise ValueError(f"Unknown analysis parameter: {parameter}")


def selected_summary(data, phase):
    cfg = data["settings"]["analysis"]
    _, summary = run_case(data, cfg["growth"], cfg["cooling"], cfg["strategy"], phase, cfg["background"])
    return summary


def quantile(values, probability):
    values = sorted(values)
    position = (len(values) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    return values[lower] + (values[upper] - values[lower]) * (position - lower)


def monte_carlo(data, runs=None):
    cfg = data["settings"]["analysis"]
    runs = cfg["runs"] if runs is None else runs
    if runs < 2:
        raise ValueError("Use at least two Monte Carlo runs")
    rng = random.Random(cfg["seed"])
    samples, draws = [], []
    groups = defaultdict(list)
    for run in range(runs):
        sample = deepcopy(data)
        # One draw per parameter is held across all quarters and both phases.
        for parameter, half_range in cfg["relative_ranges"].items():
            factor = rng.uniform(1 - half_range, 1 + half_range)
            perturb(sample, parameter, factor)
            draws.append({"run": run + 1, "parameter": parameter, "multiplier": factor})
        for phase in sample["settings"]["phases"]:
            result = selected_summary(sample, phase)
            samples.append({"run": run + 1, **result})
            for metric in METRICS:
                groups[phase, metric].append(result[metric])
    summaries = []
    for (phase, metric), values in groups.items():
        summaries.append({"growth": cfg["growth"], "cooling": cfg["cooling"],
                          "strategy": cfg["strategy"], "background": cfg["background"],
                          "phase": phase, "metric": metric, "runs": runs,
                          "mean": mean(values), "p05": quantile(values, 0.05),
                          "p50": quantile(values, 0.5), "p95": quantile(values, 0.95)})
    return {"uncertainty_runs": samples, "uncertainty_draws": draws, "uncertainty_summary": summaries}


def sensitivity(data):
    cfg = data["settings"]["analysis"]
    references = {phase: selected_summary(data, phase) for phase in data["settings"]["phases"]}
    results = []
    for parameter in ("demand", "hardware", "liquid_share", "coolant_intensity", "pue_overhead"):
        for level, factor in (("low", 1 - cfg["sensitivity_fraction"]),
                              ("high", 1 + cfg["sensitivity_fraction"])):
            sample = deepcopy(data)
            perturb(sample, parameter, factor)
            for phase, reference in references.items():
                changed = selected_summary(sample, phase)
                for metric in METRICS:
                    base, value = reference[metric], changed[metric]
                    results.append({"growth": cfg["growth"], "cooling": cfg["cooling"],
                                    "strategy": cfg["strategy"], "background": cfg["background"],
                                    "phase": phase, "parameter": parameter, "level": level,
                                    "multiplier": factor, "metric": metric, "baseline": base,
                                    "value": value, "change_percent": 100 * (value / base - 1) if base else ""})
    return results
