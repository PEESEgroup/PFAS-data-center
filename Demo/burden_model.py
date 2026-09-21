"""Multiply activity quantities by synthetic impact factors."""

from collections import defaultdict
from math import isfinite

ACTIVITY_UNITS = {"coolant_supply": "kg", "coolant_treatment": "kg", "coolant_recovery": "kg", "cooling_electricity": "kWh"}
INDICATOR_UNITS = {"CC": "kg CO2-eq", "HTC": "CTUh", "CED": "MJ-eq"}


def prepare_factors(rows, phases):
    factors = {}
    for row in rows:
        key = (row["phase"], row["activity"], row["indicator"])
        value = float(row["factor"])
        if key in factors or not isfinite(value) or value < 0:
            raise ValueError(f"Duplicate or invalid factor: {key}")
        if row["activity_unit"] != ACTIVITY_UNITS[row["activity"]]:
            raise ValueError(f"Wrong activity unit: {key}")
        if row["impact_unit"] != INDICATOR_UNITS[row["indicator"]]:
            raise ValueError(f"Wrong impact unit: {key}")
        factors[key] = value
    expected = {(p, a, i) for p in phases for a in ACTIVITY_UNITS for i in INDICATOR_UNITS}
    if set(factors) != expected:
        raise ValueError("Impact factors must cover every phase, activity and indicator exactly once")
    return factors


def calculate_burden(flows, energy, phase, factors):
    activities = {
        "coolant_supply": flows["virgin_coolant_kg"],
        "coolant_treatment": flows["treated_coolant_kg"],
        "coolant_recovery": flows["recovered_coolant_kg"],
        "cooling_electricity": energy["cooling_kwh"],
    }
    rows = []
    totals = defaultdict(float)
    for activity, quantity in activities.items():
        for indicator, unit in INDICATOR_UNITS.items():
            factor = factors[phase, activity, indicator]
            value = quantity * factor
            rows.append({"source": activity, "indicator": indicator, "quantity": quantity,
                         "activity_unit": ACTIVITY_UNITS[activity], "factor": factor,
                         "value": value, "unit": unit})
            totals[indicator] += value
    return rows, dict(totals)
