# PFAS-data-center

This project examines how AI computing demand connects to server deployment, liquid cooling, and environmental burdens. The public demo provides a small working example of that calculation chain, including coolant recovery and comparisons between cooling strategies.

**Every input and impact factor supplied with this demo is synthetic.** The example does not contain the manuscript's calibrated demand paths, retirement distribution, LCA database, or research results.

## Workflow

The example runs 12 illustrative quarters, labeled Q01–Q12. Training and inference demand are supplied directly. Separate rack fleets meet those demands, with constant rack performance and a fixed service life. The fleet calculation supplies new, operating, and retired rack counts to the cooling modules.

Cooling capacity is calculated from quarter-end rated IT power. Electricity uses average opening/closing rack stocks and workload utilization. A constant liquid-cooling share is used throughout each run. Single-phase and two-phase cooling are evaluated as separate alternatives.

The coolant model tracks initial filling, operating losses and make-up, retirement, recovery, reuse, treatment, and stored recovered fluid. Recovery is represented by one usable recovery fraction. Recovered fluid can be reused in the same quarter; surplus is stored for later demand. Reuse reduces virgin coolant purchases, so the burden calculation adds no separate avoided-production credit.

Environmental burdens are calculated for four activities: virgin coolant supply, retired coolant treatment, coolant recovery processing, and cooling electricity. The synthetic factor table covers climate change (CC), human toxicity—cancer (HTC), and cumulative energy demand (CED). Activity quantities and factor units are included in the outputs for inspection.

## Run

Python 3.8 or later is sufficient; no third-party packages are required. From the repository root:

```bash
python3 Demo/run_demo.py
```

The script uses files inside `Demo/` and writes five CSV files to `Demo/output/`. Running it again replaces these generated files.

## Code and inputs

| File | Role |
| --- | --- |
| `Demo/run_demo.py` | Load inputs, connect the modules, and write results. |
| `Demo/scale_model.py` | Convert supplied computing demand into rack flows. |
| `Demo/cooling_model.py` | Convert rack flows into liquid-cooled capacity and coolant mass. |
| `Demo/energy_model.py` | Calculate IT electricity and liquid-cooling overhead. |
| `Demo/material_flow_model.py` | Track coolant losses, purchases, recovery, reuse, treatment, and storage. |
| `Demo/burden_model.py` | Validate factor coverage and calculate burdens by activity and indicator. |
| `Demo/scenario_model.py` | Apply strategy parameters to independent copies of the baseline settings. |

The `Demo/input/` directory contains four illustrative files: quarterly computing demand, operating settings, scenario settings, and an impact-factor table. No original project workbooks are needed.

Five strategies share the same computing demand: baseline, improved PUE, lower coolant intensity, coolant recovery, and a combined strategy. PUE improvements reduce the overhead term `PUE - 1`. Lower coolant intensity changes litres per kW; the recovery strategy changes the fraction of retired fluid that becomes usable recovered fluid. These are independent demonstration assumptions, not optimized or calibrated technology pathways.

## Outputs

| File in `Demo/output/` | Contents |
| --- | --- |
| `scale_results.csv` | Rack additions, stock, retirement, and average stock for each workload. Shared by all cooling strategies. |
| `material_flows.csv` | Quarterly coolant mass balance and recovery storage. |
| `energy_results.csv` | Training/inference IT electricity, liquid-cooled IT electricity, and cooling overhead. |
| `burden_results.csv` | Quarterly impacts by scenario, phase, source, and indicator, with quantities and factors. |
| `scenario_summary.csv` | Summed flows and burdens over all 12 quarters, plus final coolant inventories. |

Each cooling result covers five strategies and two cooling phases. Impacts are added only within the same indicator. End-of-quarter stocks are not summed as cumulative consumption.

## Interpretation

The demo illustrates module interfaces and conservation of mass. Fixed rack performance, fixed service life, constant cooling shares, and simple usable-recovery fractions replace the detailed assumptions in the research model. Uncertainty analysis, detailed retrofits, electricity-background scenarios, and manuscript figures are outside this initial release.

The burden boundary includes coolant supply, retirement treatment, recovery processing, and **cooling electricity only**. IT electricity is reported separately and is not included in burden totals. Air-cooling overhead, hardware production/disposal impacts, and direct characterization of coolant losses are omitted. Losses are recorded as mass leaving the system; the synthetic HTC factors are not a model of PFAS exposure or fate. Fluid remaining in equipment or recovery storage at the final quarter is retained as inventory, with no terminal disposal assumption.

All reported impacts are illustrative and should not be interpreted as research estimates or technology rankings.

## Checks

```bash
python3 -B -m unittest discover -s Demo/tests -v
```

The checks cover rack capacity and stock balance, coolant conservation, recovery storage, burden aggregation, strategy effects, zero demand, and execution from a standalone copy of `Demo/`.
