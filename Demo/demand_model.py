"""Quarterly training and inference compute requirements."""


def calculate_demand(rows, settings, growth):
    demand = []
    seconds = settings["quarter_hours"] * 3600
    for row in rows:
        training = (row["architectures"] * growth["architecture_factor"]
                    * settings["training_runs_per_year"] * growth["training_frequency_factor"]
                    * row["training_flop_per_run"] / 4 / seconds / 1e15)
        inference = (2 * row["parameters_billion"] * row["users_million"]
                     * growth["user_factor"] * settings["tokens_per_user_day"] / 86400)
        demand.append({**row, "training_demand_pflops": training,
                       "inference_demand_pflops": inference})
    return demand
