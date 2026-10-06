"""Independent growth, cooling-share and technology settings."""


def phase_parameters(base, strategy, progress):
    phase = dict(base)
    intensity = 1 + (strategy.get("coolant_intensity_factor", 1) - 1) * progress
    overhead = 1 + (strategy.get("pue_overhead_factor", 1) - 1) * progress
    phase["litres_per_kw"] *= intensity
    phase["pue"] = 1 + (phase["pue"] - 1) * overhead
    return phase


def cooling_share(row, path, multiplier=1.0):
    return min(1.0, row[f"liquid_share_{path}"] * multiplier)
