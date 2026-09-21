"""IT electricity and the overhead attributed to liquid cooling."""


def calculate_energy(scale, settings, phase):
    energy = {}
    rack_it_kw = settings["rack_gpu_kw"] * settings["gpu_to_it_factor"]
    idle = settings["idle_power_fraction"]
    for workload in ("training", "inference"):
        load = idle + (settings["max_power_fraction"] - idle) * settings[f"{workload}_utilization"]
        energy[f"{workload}_it_kwh"] = (
            scale[workload]["average_racks"] * rack_it_kw * load * settings["quarter_hours"]
        )
    energy["total_it_kwh"] = energy["training_it_kwh"] + energy["inference_it_kwh"]
    energy["liquid_it_kwh"] = energy["total_it_kwh"] * settings["liquid_share"]
    energy["cooling_kwh"] = energy["liquid_it_kwh"] * (phase["pue"] - 1)
    return energy
