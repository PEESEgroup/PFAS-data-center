"""Two independent rack fleets with a fixed illustrative service life."""

from math import ceil


def project_scale(rows, settings):
    purchases = {workload: [] for workload in ("training", "inference")}
    stock = dict.fromkeys(purchases, 0)
    lifetime = settings["rack_lifetime_quarters"]
    results = []
    for quarter, row in enumerate(rows):
        result = {"period": row["period"]}
        for workload, history in purchases.items():
            opening = stock[workload]
            retired = history[quarter - lifetime] if quarter >= lifetime else 0
            capacity = settings[f"{workload}_pflops_per_rack"]
            required = ceil(row[f"{workload}_demand_pflops"] / capacity)
            added = max(0, required - (opening - retired))
            stock[workload] = opening - retired + added
            history.append(added)
            result[workload] = {
                "new_racks": added,
                "retired_racks": retired,
                "rack_stock": stock[workload],
                "average_racks": (opening + stock[workload]) / 2,
            }
        results.append(result)
    return results
