"""Coolant inventory, make-up, and cooling electricity for one phase."""


def utilization(period, start, end):
    year, quarter = period.split(" Q")
    decimal_year = int(year) + (int(quarter) - 1) / 4.0
    progress = min(1.0, max(0.0, (decimal_year - 2024.0) / 6.75))
    return start + (end - start) * progress


def calculate_cooling(scale, row, phase, settings, previous_inventory):
    closing_gpu_kw = scale["training"]["closing_gpu_kw"] + scale["inference"]["closing_gpu_kw"]
    liquid_it_kw = closing_gpu_kw * settings["gpu_to_it_factor"] * row["liquid_share"]
    intensity = row[f"{phase}_l_per_kw"]
    density = row[f"{phase}_density_kg_per_l"]
    inventory_kg = liquid_it_kw * intensity * density

    annual_loss = settings[f"{phase}_annual_loss"]
    quarterly_loss = 1.0 - (1.0 - annual_loss) ** 0.25
    new_coolant_kg = max(0.0, inventory_kg - previous_inventory) + inventory_kg * quarterly_loss

    idle = settings["idle_power_rate"]
    spread = settings["max_power_rate"] - idle
    training_use = utilization(scale["period"], settings["training_use_start"], settings["training_use_end"])
    inference_use = utilization(scale["period"], settings["inference_use_start"], settings["inference_use_end"])
    actual_it_kw = settings["gpu_to_it_factor"] * (
        scale["training"]["average_gpu_kw"] * (idle + spread * training_use)
        + scale["inference"]["average_gpu_kw"] * (idle + spread * inference_use)
    )
    cooling_kwh = (
        actual_it_kw * row["liquid_share"] * settings["quarter_hours"]
        * (settings[f"{phase}_pue"] - 1.0)
    )

    return {
        "liquid_it_kw": liquid_it_kw,
        "coolant_inventory_kg": inventory_kg,
        "new_coolant_kg": new_coolant_kg,
        "cooling_electricity_kwh": cooling_kwh,
    }
