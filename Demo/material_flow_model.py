"""Retire first, replace operating losses, then fill newly installed capacity."""


def coolant_flows(cooling, opening_inventory, opening_bank, phase, recovery_rate):
    retired = cooling["retired_coolant_kg"]
    if retired > opening_inventory + 1e-9:
        raise ValueError("Retired coolant exceeds the opening inventory")
    surviving = max(0.0, opening_inventory - retired)
    loss_fraction = 1 - (1 - phase["annual_loss_fraction"]) ** 0.25
    leaked = surviving * loss_fraction
    demand = cooling["initial_fill_kg"] + leaked
    recovered = retired * recovery_rate
    reused = min(demand, opening_bank + recovered)
    return {
        "opening_inventory_kg": opening_inventory,
        "installed_coolant_kg": cooling["installed_coolant_kg"],
        "initial_fill_kg": cooling["initial_fill_kg"],
        "makeup_kg": leaked,
        "leaked_coolant_kg": leaked,
        "retired_coolant_kg": retired,
        "recovered_coolant_kg": recovered,
        "reused_coolant_kg": reused,
        "virgin_coolant_kg": demand - reused,
        "treated_coolant_kg": retired - recovered,
        "opening_bank_kg": opening_bank,
        "recovery_bank_kg": opening_bank + recovered - reused,
    }
