"""Balance coolant replenishment, retirement, processing and recovered stock."""


def coolant_flows(cooling, opening_bank, phase, recovery_rate, recovery_yield):
    inventory = cooling["installed_coolant_kg"]
    loss = inventory * (1 - (1 - phase["annual_loss_fraction"]) ** 0.25)
    evaporation = loss * phase["evaporation_share"]
    maintenance = loss - evaporation
    retired = cooling["retired_coolant_kg"]
    processed = retired * recovery_rate
    recovered = processed * recovery_yield
    demand = cooling["initial_fill_kg"] + cooling["retrofit_fill_kg"] + loss
    reused = min(demand, opening_bank + recovered)
    return {
        **cooling,
        "evaporation_kg": evaporation,
        "maintenance_loss_kg": maintenance,
        "makeup_kg": loss,
        "processed_coolant_kg": processed,
        "recovered_coolant_kg": recovered,
        "recovery_residue_kg": processed - recovered,
        "reused_coolant_kg": reused,
        "virgin_coolant_kg": demand - reused,
        "treated_coolant_kg": retired - recovered,
        "opening_bank_kg": opening_bank,
        "recovery_bank_kg": opening_bank + recovered - reused,
    }
