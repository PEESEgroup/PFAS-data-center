"""Assign liquid cooling to new racks and retrofit surviving air-cooled racks."""


class CoolingFleet:
    def __init__(self):
        self.capacity = {}
        self.fluid = {}

    def step(self, scale, share, it_factor, phase):
        opening_fluid = sum(self.fluid.values())
        retired_fluid = new_fill = retrofit_fill = retired_kw = retrofit_kw = 0.0
        energy_power = {}
        for workload in ("training", "inference"):
            cohorts = [c for c in scale["cohorts"] if c["workload"] == workload]
            keys = [(workload, c["vintage"]) for c in cohorts]
            opening_kw = sum(self.capacity.get(key, 0.0) for key in keys)
            available = {}
            for key, cohort in zip(keys, cohorts):
                hazard = cohort["hazard"]
                previous_kw = self.capacity.get(key, 0.0)
                previous_fluid = self.fluid.get(key, 0.0)
                retired_kw += previous_kw * hazard
                retired_fluid += previous_fluid * hazard
                self.capacity[key] = previous_kw * (1 - hazard)
                self.fluid[key] = previous_fluid * (1 - hazard)
                available[key] = cohort["racks"] * cohort["gpu_kw_per_rack"] * it_factor
            target = sum(available.values()) * share
            deficit = target - sum(self.capacity[key] for key in keys)
            if deficit < -1e-7:
                raise ValueError("Cooling share would require liquid-to-air conversion")
            deficit = max(0.0, deficit)
            newest = keys[-1]
            new_kw = min(deficit, available[newest])
            additions = {newest: new_kw}
            deficit -= new_kw
            air = {key: max(0.0, available[key] - self.capacity[key]) for key in keys[:-1]}
            total_air = sum(air.values())
            if deficit > total_air + 1e-7:
                raise ValueError("Insufficient air-cooled capacity for retrofit")
            if total_air:
                additions.update({key: deficit * value / total_air for key, value in air.items()})
            for key, added_kw in additions.items():
                charge = added_kw * phase["litres_per_kw"] * phase["density_kg_per_litre"]
                self.capacity[key] += added_kw
                # Existing fluid keeps its filling-quarter intensity after later improvements.
                self.fluid[key] += charge
                if key == newest:
                    new_fill += charge
                else:
                    retrofit_fill += charge
                    retrofit_kw += added_kw
            closing_kw = sum(self.capacity[key] for key in keys)
            energy_power[f"{workload}_liquid_average_kw"] = (opening_kw + closing_kw) / 2
        return {
            "opening_inventory_kg": opening_fluid,
            "installed_coolant_kg": sum(self.fluid.values()),
            "initial_fill_kg": new_fill,
            "retrofit_fill_kg": retrofit_fill,
            "retired_coolant_kg": retired_fluid,
            "liquid_it_kw": sum(self.capacity.values()),
            "retired_liquid_it_kw": retired_kw,
            "retrofit_it_kw": retrofit_kw,
            **energy_power,
        }
