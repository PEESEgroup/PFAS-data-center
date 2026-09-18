"""Quarterly AI demand and purchase-cohort rack projection."""

from math import ceil


def advance_fleet(cohorts, quarter, demand, new_rack_capacity, board_kw, retirement, gpu_per_rack):
    surviving_racks = surviving_capacity = surviving_power = 0.0
    opening_power = retired_racks = 0.0

    for purchase_quarter, racks, capacity, purchase_board_kw in cohorts:
        age = quarter - purchase_quarter
        opening_share = max(0.0, 1.0 - sum(retirement[: age - 1]))
        closing_share = max(0.0, 1.0 - sum(retirement[:age]))
        retired_share = retirement[age - 1] if age <= len(retirement) else 0.0

        opening_power += racks * gpu_per_rack * purchase_board_kw * opening_share
        surviving_power += racks * gpu_per_rack * purchase_board_kw * closing_share
        surviving_racks += racks * closing_share
        surviving_capacity += racks * capacity * closing_share
        retired_racks += racks * retired_share

    shortfall = max(0.0, demand - surviving_capacity)
    new_racks = max(0, ceil(shortfall / new_rack_capacity - 1e-12))
    cohorts.append((quarter, new_racks, new_rack_capacity, board_kw))
    closing_power = surviving_power + new_racks * gpu_per_rack * board_kw

    return {
        "new_racks": new_racks,
        "retired_racks": retired_racks,
        "rack_stock": surviving_racks + new_racks,
        "closing_gpu_kw": closing_power,
        "average_gpu_kw": (opening_power + closing_power) / 2.0,
    }


def project_scale(rows, retirement, settings):
    fleets = {"training": [], "inference": []}
    output = []
    gpu_per_rack = settings["gpu_per_rack"]

    for quarter, row in enumerate(rows):
        training_demand = (
            row["architectures"]
            * settings["training_runs_per_architecture_per_year"]
            / 4.0
            * row["training_flop_per_run"]
            / (settings["quarter_hours"] * 3600.0 * 1e15)
        )
        inference_demand = (
            2.0
            * row["np_billion"]
            * row["dau_million"]
            * settings["tokens_per_dau_per_day"]
            / 86400.0
        )
        training = advance_fleet(
            fleets["training"], quarter, training_demand,
            row["bf16_pflops_per_gpu"] * settings["training_efficiency"] * gpu_per_rack,
            row["gpu_board_kw"], retirement, gpu_per_rack,
        )
        inference = advance_fleet(
            fleets["inference"], quarter, inference_demand,
            row["bf16_pflops_per_gpu"] * settings["inference_efficiency"] * gpu_per_rack,
            row["gpu_board_kw"], retirement, gpu_per_rack,
        )
        output.append({"period": row["period"], "training": training, "inference": inference})

    return output
