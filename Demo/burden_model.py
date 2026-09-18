"""Illustrative climate-change factors for the two operating inputs."""


def climate_change(cooling, phase, settings):
    coolant = cooling["new_coolant_kg"] * settings[f"{phase}_coolant_kg_co2e_per_kg"]
    electricity = cooling["cooling_electricity_kwh"] * settings["electricity_kg_co2e_per_kwh"]
    return {
        "coolant_kg_co2e": coolant,
        "electricity_kg_co2e": electricity,
        "total_kg_co2e": coolant + electricity,
    }
