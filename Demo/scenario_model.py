"""Apply each strategy to an independent copy of the baseline parameters."""

from copy import deepcopy


def apply_scenario(settings, strategy):
    allowed = {"pue_overhead_factor", "coolant_intensity_factor", "recovery_rate"}
    if set(strategy) - allowed:
        raise ValueError(f"Unknown strategy keys: {set(strategy) - allowed}")
    for key, value in strategy.items():
        if not 0 <= value <= 1 or (key != "recovery_rate" and value == 0):
            raise ValueError(f"Invalid strategy value: {key}={value}")
    result = deepcopy(settings)
    result["recovery_rate"] = strategy.get("recovery_rate", 0)
    for phase in result["phases"].values():
        phase["pue"] = 1 + (phase["pue"] - 1) * strategy.get("pue_overhead_factor", 1)
        phase["litres_per_kw"] *= strategy.get("coolant_intensity_factor", 1)
    return result
