"""Convert rack flows to coolant mass using a constant cooling share."""


def size_cooling(scale, settings, phase):
    share = settings["liquid_share"]
    rack_it_kw = settings["rack_gpu_kw"] * settings["gpu_to_it_factor"]
    kg_per_rack = rack_it_kw * share * phase["litres_per_kw"] * phase["density_kg_per_litre"]
    fleets = (scale["training"], scale["inference"])
    return {
        "liquid_it_kw": sum(f["rack_stock"] for f in fleets) * rack_it_kw * share,
        "installed_coolant_kg": sum(f["rack_stock"] for f in fleets) * kg_per_rack,
        "initial_fill_kg": sum(f["new_racks"] for f in fleets) * kg_per_rack,
        "retired_coolant_kg": sum(f["retired_racks"] for f in fleets) * kg_per_rack,
    }
