"""Connect the quarterly modules for a single case."""

from itertools import product

from burden_model import calculate_burden
from cooling_model import CoolingFleet
from demand_model import calculate_demand
from energy_model import calculate_energy
from material_flow_model import coolant_flows
from scale_model import project_scale
from scenario_model import cooling_share, phase_parameters

FLOW_TOTALS = ("virgin_coolant_kg", "treated_coolant_kg", "recovered_coolant_kg")
IMPACTS = {"CC": "CC_kg_co2e", "HTC": "HTC_ctuh", "CED": "CED_mj_eq"}


def prepare_scale(data, growth):
    settings = data["settings"]
    demand = calculate_demand(data["rows"], settings, settings["growth"][growth])
    return project_scale(demand, settings, data["pmf"])


def run_case(data, growth, cooling, strategy, phase_name, background, scale=None):
    settings = data["settings"]
    rows = data["rows"]
    strategy_settings = data["strategies"][strategy]
    if scale is None:
        scale = prepare_scale(data, growth)
    labels = {"growth": growth, "cooling": cooling, "strategy": strategy,
              "phase": phase_name, "background": background}
    tables = {"material_flows": [], "energy_results": [], "burden_results": [], "cumulative_results": []}
    totals = dict.fromkeys((*FLOW_TOTALS, "cooling_kwh", *IMPACTS.values()), 0.0)
    start = next(q for q, row in enumerate(rows) if row["period"] == settings["cumulative_start"])
    fleet = CoolingFleet()
    bank = 0.0
    for q, (row, quarter) in enumerate(zip(rows, scale)):
        phase = phase_parameters(settings["phases"][phase_name], strategy_settings, q / (len(rows) - 1))
        share = cooling_share(row, cooling, settings.get("share_multiplier", 1))
        capacity = fleet.step(quarter, share, settings["gpu_to_it_factor"], phase)
        flows = coolant_flows(capacity, bank, phase, strategy_settings.get("recovery_rate", 0),
                              settings["recovery_yield"])
        bank = flows["recovery_bank_kg"]
        energy = calculate_energy(quarter, capacity, row, settings, phase)
        factors = data["backgrounds"][background][row["period"]]
        burdens, impacts = calculate_burden(flows, energy, phase_name, data["factors"], factors)
        key = {**labels, "period": row["period"]}
        tables["material_flows"].append({**key, "liquid_share": share, **flows})
        tables["energy_results"].append({**key, **energy})
        tables["burden_results"].extend({**key, **burden} for burden in burdens)
        if q >= start:
            for field in FLOW_TOTALS:
                totals[field] += flows[field]
            totals["cooling_kwh"] += energy["cooling_kwh"]
            for indicator, field in IMPACTS.items():
                totals[field] += impacts[indicator]
        tables["cumulative_results"].append({**key, **totals})
    summary = {**labels, "cumulative_start": settings["cumulative_start"], **totals,
               "final_inventory_kg": flows["installed_coolant_kg"], "final_recovery_bank_kg": bank}
    return tables, summary


def run_model(data):
    tables = {name: [] for name in ("scale_results", "material_flows", "energy_results",
                                   "burden_results", "cumulative_results", "scenario_summary")}
    for growth in data["settings"]["growth"]:
        scale = prepare_scale(data, growth)
        for quarter in scale:
            for workload in ("training", "inference"):
                tables["scale_results"].append({"growth": growth, "period": quarter["period"],
                                               "workload": workload, **quarter[workload]})
        cases = product(
            ("low", "central", "high"), data["strategies"],
            data["settings"]["phases"], data["backgrounds"],
        )
        for cooling, strategy, phase, background in cases:
            case, summary = run_case(data, growth, cooling, strategy, phase, background, scale)
            for name, rows in case.items():
                tables[name].extend(rows)
            tables["scenario_summary"].append(summary)
    return tables
