"""Rack purchases and retirements, retaining each vintage's capacity and power."""

from math import ceil


def retirement_hazard(pmf, age):
    if age == 0:
        return 0.0
    survival = max(0.0, 1 - sum(pmf[:age - 1]))
    if age > len(pmf) or survival < 1e-12:
        return 1.0
    return min(1.0, pmf[age - 1] / survival)


def project_scale(demand, settings, pmf):
    fleets = {"training": [], "inference": []}
    results = []
    for q, row in enumerate(demand):
        quarter = {"period": row["period"], "cohorts": []}
        for workload, cohorts in fleets.items():
            opening_power = sum(c["racks"] * c["gpu_kw_per_rack"] for c in cohorts)
            retired = retired_power = 0.0
            for cohort in cohorts:
                hazard = retirement_hazard(pmf, q - cohort["vintage"])
                leaving = cohort["racks"] * hazard
                retired += leaving
                retired_power += leaving * cohort["gpu_kw_per_rack"]
                cohort["racks"] -= leaving
                cohort["hazard"] = hazard
            capacity = sum(c["racks"] * c["capacity_pflops"] for c in cohorts)
            rack_capacity = (row["gpu_pflops"] * settings["gpus_per_rack"]
                             * settings[f"{workload}_efficiency"])
            shortfall = max(0.0, row[f"{workload}_demand_pflops"] - capacity)
            added = max(0, ceil(shortfall / rack_capacity - 1e-12))
            rack_power = row["gpu_board_kw"] * settings["gpus_per_rack"]
            cohorts.append({"workload": workload, "vintage": q, "racks": float(added),
                            "capacity_pflops": rack_capacity,
                            "gpu_kw_per_rack": rack_power, "hazard": 0.0})
            closing_power = sum(c["racks"] * c["gpu_kw_per_rack"] for c in cohorts)
            quarter[workload] = {
                "demand_pflops": row[f"{workload}_demand_pflops"],
                "capacity_pflops": capacity + added * rack_capacity,
                "new_racks": added,
                "retired_racks": retired,
                "rack_stock": sum(c["racks"] for c in cohorts),
                "new_gpu_kw": added * rack_power,
                "retired_gpu_kw": retired_power,
                "closing_gpu_kw": closing_power,
                "average_gpu_kw": (opening_power + closing_power) / 2,
                "e_waste_kg": retired * settings["rack_mass_kg"],
            }
            quarter["cohorts"].extend(dict(c) for c in cohorts)
        results.append(quarter)
    return results
