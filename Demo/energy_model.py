"""Quarter-average operating electricity and liquid-cooling overhead."""


def calculate_energy(scale, cooling, row, settings, phase):
    energy = {}
    liquid_it = 0.0
    for workload in ("training", "inference"):
        load = settings["idle_power_fraction"] + (
            settings["max_power_fraction"] - settings["idle_power_fraction"]
        ) * row[f"{workload}_utilization"]
        hours = settings["quarter_hours"]
        energy[f"{workload}_it_kwh"] = (
            scale[workload]["average_gpu_kw"] * settings["gpu_to_it_factor"] * load * hours
        )
        liquid_it += cooling[f"{workload}_liquid_average_kw"] * load * hours
    energy["total_it_kwh"] = energy["training_it_kwh"] + energy["inference_it_kwh"]
    energy["liquid_it_kwh"] = liquid_it
    energy["cooling_kwh"] = liquid_it * (phase["pue"] - 1)
    energy["pue"] = phase["pue"]
    return energy
