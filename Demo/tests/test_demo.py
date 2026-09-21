"""Conservation, strategy effects, and the standalone public example."""

import copy
import csv
from collections import defaultdict
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from burden_model import prepare_factors
from material_flow_model import coolant_flows
from run_demo import HERE, load_inputs, read_csv, run_model
from scenario_model import apply_scenario


class DemoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs = load_inputs(HERE / "input")
        cls.tables = run_model(*cls.inputs)

    def test_rack_balance_and_capacity(self):
        rows, settings, _, _ = self.inputs
        stock = defaultdict(float)
        purchases = defaultdict(list)
        for row in self.tables["scale_results"]:
            workload = row["workload"]
            self.assertEqual(row["rack_stock"], stock[workload] + row["new_racks"] - row["retired_racks"])
            q = len(purchases[workload])
            self.assertGreaterEqual(row["rack_stock"] * settings[f"{workload}_pflops_per_rack"],
                                    rows[q][f"{workload}_demand_pflops"])
            if q >= settings["rack_lifetime_quarters"]:
                self.assertEqual(row["retired_racks"], purchases[workload][q - settings["rack_lifetime_quarters"]])
            purchases[workload].append(row["new_racks"])
            stock[workload] = row["rack_stock"]

    def test_material_conservation(self):
        for row in self.tables["material_flows"]:
            self.assertAlmostEqual(row["installed_coolant_kg"], row["opening_inventory_kg"]
                                   + row["virgin_coolant_kg"] + row["reused_coolant_kg"]
                                   - row["retired_coolant_kg"] - row["leaked_coolant_kg"])
            self.assertAlmostEqual(row["recovery_bank_kg"], row["opening_bank_kg"]
                                   + row["recovered_coolant_kg"] - row["reused_coolant_kg"])
            self.assertAlmostEqual(row["retired_coolant_kg"], row["recovered_coolant_kg"]
                                   + row["treated_coolant_kg"])
            self.assertTrue(all(v >= -1e-9 for v in row.values() if isinstance(v, (int, float))))

    def test_recovery_bank_is_used_later(self):
        phase = {"annual_loss_fraction": 0}
        first = coolant_flows({"retired_coolant_kg": 10, "initial_fill_kg": 2,
                               "installed_coolant_kg": 12}, 20, 0, phase, 0.6)
        self.assertEqual(first["virgin_coolant_kg"], 0)
        self.assertEqual(first["recovery_bank_kg"], 4)
        second = coolant_flows({"retired_coolant_kg": 0, "initial_fill_kg": 5,
                                "installed_coolant_kg": 17}, 12, 4, phase, 0.6)
        self.assertEqual(second["virgin_coolant_kg"], 1)
        self.assertEqual(second["recovery_bank_kg"], 0)

    def test_burden_totals_and_units(self):
        totals = defaultdict(float)
        for row in self.tables["burden_results"]:
            self.assertAlmostEqual(row["value"], row["quantity"] * row["factor"])
            totals[row["scenario"], row["phase"], row["indicator"]] += row["value"]
        for row in self.tables["scenario_summary"]:
            for indicator, field in (("CC", "CC_kg_co2e"), ("HTC", "HTC_ctuh"), ("CED", "CED_mj_eq")):
                self.assertAlmostEqual(row[field], totals[row["scenario"], row["phase"], indicator], places=7)
        factors = read_csv(HERE / "input/illustrative_impact_factors.csv")
        for bad in (factors[:-1], factors + factors[:1]):
            with self.assertRaises(ValueError):
                prepare_factors(bad, self.inputs[1]["phases"])
        bad = copy.deepcopy(factors)
        bad[0]["activity_unit"] = "kWh"
        with self.assertRaises(ValueError):
            prepare_factors(bad, self.inputs[1]["phases"])

    def test_strategy_effects_and_isolation(self):
        settings = copy.deepcopy(self.inputs[1])
        changed = apply_scenario(settings, {"pue_overhead_factor": 0.8})
        self.assertEqual(settings, self.inputs[1])
        self.assertAlmostEqual(changed["phases"]["single"]["pue"], 1.16)
        summary = {(r["scenario"], r["phase"]): r for r in self.tables["scenario_summary"]}
        for phase in settings["phases"]:
            base = summary["baseline", phase]
            pue = summary["improved_pue", phase]
            reduced = summary["lower_coolant_intensity", phase]
            recovery = summary["coolant_recovery", phase]
            self.assertAlmostEqual(pue["cooling_kwh"], base["cooling_kwh"] * 0.8)
            self.assertEqual(pue["virgin_coolant_kg"], base["virgin_coolant_kg"])
            self.assertAlmostEqual(reduced["virgin_coolant_kg"], base["virgin_coolant_kg"] * 0.75)
            self.assertEqual(reduced["cooling_kwh"], base["cooling_kwh"])
            self.assertLess(recovery["virgin_coolant_kg"], base["virgin_coolant_kg"])
            self.assertLess(recovery["treated_coolant_kg"], base["treated_coolant_kg"])
            self.assertEqual(recovery["cooling_kwh"], base["cooling_kwh"])
        energy = {(r["scenario"], r["phase"], r["period"]): r for r in self.tables["energy_results"]}
        for r in energy.values():
            self.assertAlmostEqual(r["total_it_kwh"], r["training_it_kwh"] + r["inference_it_kwh"])
            self.assertEqual(r["total_it_kwh"], energy["baseline", r["phase"], r["period"]]["total_it_kwh"])

    def test_zero_demand(self):
        rows, settings, scenarios, factors = copy.deepcopy(self.inputs)
        for row in rows:
            row["training_demand_pflops"] = row["inference_demand_pflops"] = 0
        tables = run_model(rows, settings, scenarios, factors)
        self.assertTrue(all(r["value"] == 0 for r in tables["burden_results"]))
        self.assertTrue(all(r["virgin_coolant_kg"] == 0 for r in tables["material_flows"]))

    def test_standalone_execution(self):
        import shutil
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "Demo"
            shutil.copytree(HERE, target, ignore=shutil.ignore_patterns("output", "__pycache__"))
            result = subprocess.run([sys.executable, "-B", str(target / "run_demo.py")],
                                    cwd=temp, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            expected = {"scale_results": 24, "material_flows": 120, "energy_results": 120,
                        "burden_results": 1440, "scenario_summary": 10}
            for name, count in expected.items():
                with (target / "output" / f"{name}.csv").open() as handle:
                    self.assertEqual(len(list(csv.DictReader(handle))), count)


if __name__ == "__main__":
    unittest.main()
