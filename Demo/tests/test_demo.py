"""Physical balances and regression checks for the public model."""

from collections import defaultdict
from copy import deepcopy
import csv
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis import monte_carlo, quantile, sensitivity
from burden_model import prepare_factors
from cooling_model import CoolingFleet
from demand_model import calculate_demand
from material_flow_model import coolant_flows
from model_inputs import load_inputs, read_csv
from run_demo import HERE
from scale_model import project_scale
from simulation import IMPACTS, prepare_scale, run_case, run_model


class ModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load_inputs(HERE / "input")
        cls.tables = run_model(cls.data)

    def close(self, actual, expected):
        self.assertAlmostEqual(actual, expected, delta=max(1e-8, abs(expected) * 1e-10))

    def test_demand_units(self):
        settings = dict(self.data["settings"], quarter_hours=2160,
                        training_runs_per_year=4, tokens_per_user_day=86400)
        row = dict(self.data["rows"][0], architectures=2, training_flop_per_run=7.776e21,
                   parameters_billion=3, users_million=5)
        result = calculate_demand([row], settings, settings["growth"]["central"])[0]
        self.close(result["training_demand_pflops"], 2)
        self.close(result["inference_demand_pflops"], 30)

    def test_vintage_power_and_retirement(self):
        settings = dict(self.data["settings"], gpus_per_rack=1,
                        training_efficiency=1, inference_efficiency=1)
        rows = []
        for q, power in enumerate((1, 10, 100)):
            rows.append({"period": f"Q{q + 1:02}", "gpu_pflops": 1, "gpu_board_kw": power,
                         "training_demand_pflops": 1, "inference_demand_pflops": 0})
        result = project_scale(rows, settings, [0, 1])
        self.close(result[1]["training"]["closing_gpu_kw"], 1)
        self.close(result[2]["training"]["retired_gpu_kw"], 1)
        self.close(result[2]["training"]["closing_gpu_kw"], 100)
        self.close(result[2]["training"]["average_gpu_kw"], 50.5)

    def test_stock_power_balance_and_capacity(self):
        previous = defaultdict(lambda: (0, 0))
        for row in self.tables["scale_results"]:
            key = row["growth"], row["workload"]
            stock, power = previous[key]
            self.close(row["rack_stock"], stock + row["new_racks"] - row["retired_racks"])
            self.close(row["closing_gpu_kw"], power + row["new_gpu_kw"] - row["retired_gpu_kw"])
            self.assertGreaterEqual(row["capacity_pflops"] + 1e-8, row["demand_pflops"])
            self.close(row["e_waste_kg"], row["retired_racks"] * self.data["settings"]["rack_mass_kg"])
            previous[key] = row["rack_stock"], row["closing_gpu_kw"]

    def test_retrofit_keeps_age_and_filling_intensity(self):
        settings = dict(self.data["settings"], gpus_per_rack=1,
                        training_efficiency=1, inference_efficiency=1)
        rows = [{"period": f"Q{q + 1:02}", "gpu_pflops": 1, "gpu_board_kw": 1,
                 "training_demand_pflops": 10, "inference_demand_pflops": 0} for q in range(3)]
        scale = project_scale(rows, settings, [0, 1])
        fleet = CoolingFleet()
        phase = {"litres_per_kw": 2, "density_kg_per_litre": 1}
        first = fleet.step(scale[0], 0.2, 1, phase)
        second = fleet.step(scale[1], 0.6, 1, dict(phase, litres_per_kw=1))
        third = fleet.step(scale[2], 0.6, 1, dict(phase, litres_per_kw=1))
        self.close(first["installed_coolant_kg"], 4)
        self.close(second["retrofit_fill_kg"], 4)
        self.close(second["installed_coolant_kg"], 8)
        self.close(third["retired_coolant_kg"], 8)
        self.close(third["installed_coolant_kg"], 6)
        with self.assertRaises(ValueError):
            fleet.step(scale[2], 0.1, 1, phase)

    def test_material_balance_all_cases(self):
        retrofits = 0
        for row in self.tables["material_flows"]:
            self.close(row["installed_coolant_kg"], row["opening_inventory_kg"]
                       + row["virgin_coolant_kg"] + row["reused_coolant_kg"]
                       - row["retired_coolant_kg"] - row["makeup_kg"])
            self.close(row["recovery_bank_kg"], row["opening_bank_kg"]
                       + row["recovered_coolant_kg"] - row["reused_coolant_kg"])
            self.close(row["retired_coolant_kg"], row["recovered_coolant_kg"] + row["treated_coolant_kg"])
            self.close(row["makeup_kg"], row["evaporation_kg"] + row["maintenance_loss_kg"])
            self.assertTrue(all(v >= -1e-8 for v in row.values() if isinstance(v, (int, float))))
            retrofits += row["retrofit_it_kw"]
        self.assertGreater(retrofits, 0)

    def test_recovery_processing_and_carryover(self):
        phase = {"annual_loss_fraction": 0, "evaporation_share": 0}
        cooling = {"installed_coolant_kg": 12, "initial_fill_kg": 2,
                   "retrofit_fill_kg": 0, "retired_coolant_kg": 10}
        first = coolant_flows(cooling, 0, phase, 0.8, 0.75)
        self.close(first["processed_coolant_kg"], 8)
        self.close(first["recovered_coolant_kg"], 6)
        self.close(first["treated_coolant_kg"], 4)
        self.close(first["recovery_bank_kg"], 4)
        second = coolant_flows(dict(cooling, initial_fill_kg=5, retired_coolant_kg=0), 4, phase, 0.8, 0.75)
        self.close(second["virgin_coolant_kg"], 1)
        self.close(second["recovery_bank_kg"], 0)

    def test_energy_boundaries(self):
        scale = {(r["growth"], r["period"], r["workload"]): r for r in self.tables["scale_results"]}
        settings = self.data["settings"]
        for row in self.tables["energy_results"]:
            self.close(row["total_it_kwh"], row["training_it_kwh"] + row["inference_it_kwh"])
            self.assertLessEqual(row["liquid_it_kwh"], row["total_it_kwh"] + 1e-8)
            self.close(row["cooling_kwh"], row["liquid_it_kwh"] * (row["pue"] - 1))
            q = int(row["period"][1:]) - 1
            for workload in ("training", "inference"):
                power = scale[row["growth"], row["period"], workload]["average_gpu_kw"]
                load = settings["idle_power_fraction"] + (settings["max_power_fraction"] - settings["idle_power_fraction"]) * self.data["rows"][q][f"{workload}_utilization"]
                self.close(row[f"{workload}_it_kwh"], power * settings["gpu_to_it_factor"] * load * settings["quarter_hours"])

    def test_factor_units_coverage_and_aggregation(self):
        totals = defaultdict(float)
        keys = ("growth", "cooling", "strategy", "phase", "background")
        for row in self.tables["burden_results"]:
            self.close(row["value"], row["quantity"] * row["factor"])
            if row["period"] >= self.data["settings"]["cumulative_start"]:
                totals[tuple(row[k] for k in keys), row["indicator"]] += row["value"]
        for row in self.tables["scenario_summary"]:
            for indicator, metric in IMPACTS.items():
                self.close(row[metric], totals[tuple(row[k] for k in keys), indicator])
        for row in self.tables["cumulative_results"]:
            if row["period"] < self.data["settings"]["cumulative_start"]:
                self.assertEqual(row["cooling_kwh"], 0)
        factors = read_csv(HERE / "input/illustrative_impact_factors.csv")
        for bad in (factors[:-1], factors + factors[:1]):
            with self.assertRaises(ValueError):
                prepare_factors(bad, self.data["settings"]["phases"])
        factors[0]["activity_unit"] = "kWh"
        with self.assertRaises(ValueError):
            prepare_factors(factors, self.data["settings"]["phases"])

    def test_strategy_effects_and_background(self):
        cases = {(r["growth"], r["cooling"], r["strategy"], r["phase"], r["background"]): r
                 for r in self.tables["scenario_summary"]}
        self.assertEqual(len(cases), 180)
        for phase in self.data["settings"]["phases"]:
            base = cases["central", "central", "baseline", phase, "steady"]
            pue = cases["central", "central", "improved_pue", phase, "steady"]
            fluid = cases["central", "central", "advanced_coolant", phase, "steady"]
            recovery = cases["central", "central", "coolant_recovery", phase, "steady"]
            grid = cases["central", "central", "baseline", phase, "transition"]
            self.assertLess(pue["cooling_kwh"], base["cooling_kwh"])
            self.close(pue["virgin_coolant_kg"], base["virgin_coolant_kg"])
            self.assertLess(fluid["virgin_coolant_kg"], base["virgin_coolant_kg"])
            self.close(fluid["cooling_kwh"], base["cooling_kwh"])
            self.assertLess(recovery["virgin_coolant_kg"], base["virgin_coolant_kg"])
            self.assertLess(recovery["treated_coolant_kg"], base["treated_coolant_kg"])
            self.close(grid["cooling_kwh"], base["cooling_kwh"])
            self.assertLess(grid["CC_kg_co2e"], base["CC_kg_co2e"])

    def test_zero_demand(self):
        data = deepcopy(self.data)
        for row in data["rows"]:
            row["architectures"] = row["users_million"] = 0
        tables, result = run_case(data, "central", "central", "combined_strategy", "single", "steady")
        self.assertEqual(result["CC_kg_co2e"], 0)
        self.assertTrue(all(r["installed_coolant_kg"] == 0 for r in tables["material_flows"]))

    def test_analysis_reproducibility_and_isolation(self):
        original = deepcopy(self.data)
        first = monte_carlo(self.data, 8)
        self.assertEqual(first, monte_carlo(self.data, 8))
        self.assertEqual(self.data, original)
        for row in first["uncertainty_summary"]:
            self.assertLessEqual(row["p05"], row["p50"])
            self.assertLessEqual(row["p50"], row["p95"])
        self.assertTrue(any(r["p95"] > r["p05"] for r in first["uncertainty_summary"]))
        self.close(quantile([0, 10], 0.05), 0.5)
        output = sensitivity(self.data)
        self.assertEqual(len(output), 140)
        self.assertEqual(self.data, original)
        for row in output:
            if row["parameter"] == "pue_overhead" and row["metric"] == "cooling_kwh":
                self.close(row["value"], row["baseline"] * row["multiplier"])

    def test_standalone_run_and_repeat(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "Demo"
            shutil.copytree(HERE, target, ignore=shutil.ignore_patterns("output", "__pycache__"))
            command = [sys.executable, "-B", str(target / "run_demo.py"), "--runs", "4"]
            result = subprocess.run(command, cwd=temp, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            manifest = json.loads((target / "output/run_manifest.json").read_text())
            self.assertEqual(manifest["rows"]["scenario_summary"], 180)
            self.assertEqual(manifest["rows"]["burden_results"], 51840)
            self.assertEqual(manifest["rows"]["uncertainty_runs"], 8)
            self.assertEqual(len(manifest["input_sha256"]), 6)
            before = {p.name: p.read_bytes() for p in (target / "output").iterdir()}
            subprocess.run(command, cwd=temp, check=True, capture_output=True)
            self.assertEqual(before, {p.name: p.read_bytes() for p in (target / "output").iterdir()})
            inputs = {p.name: p.read_bytes() for p in (target / "input").iterdir()}
            subprocess.run([sys.executable, "-B", str(target / "generate_inputs.py")],
                           cwd=temp, check=True, capture_output=True)
            self.assertEqual(inputs, {p.name: p.read_bytes() for p in (target / "input").iterdir()})

    def test_input_time_alignment(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / "input"
            shutil.copytree(HERE / "input", folder)
            path = folder / "illustrative_electricity.csv"
            lines = path.read_text().splitlines()
            path.write_text("\n".join(lines[:-1]) + "\n")
            with self.assertRaises(ValueError):
                load_inputs(folder)


if __name__ == "__main__":
    unittest.main()
