# Initial demo: AI scale and liquid cooling

This is a small, standalone example of the Chapter 3 calculation chain:

`AI workload -> training/inference rack fleets -> liquid-cooling demand -> cooling electricity -> climate-change burden`

It runs the **Moderate** AI and liquid-cooling paths from 2020 Q1 through 2030 Q4. The demo is meant to show the code structure and data flow; its burden values are not manuscript results.

## Run

Python 3 is the only requirement. From this directory:

```bash
python3 run_demo.py
```

The script writes `output/demo_results.csv` (44 quarters × 2 cooling phases). It also works when invoked from another directory because paths are resolved from the script location.

## Files

| File | Purpose |
| --- | --- |
| `run_demo.py` | Read inputs, run the modules, write one CSV result. |
| `scale_model.py` | Calculate training/inference demand and separate purchase-cohort rack fleets. |
| `cooling_model.py` | Estimate liquid-cooled rated IT capacity, coolant and cooling electricity. |
| `burden_model.py` | Apply illustrative climate-change factors. |
| `input/quarterly.csv` | Moderate-case quarterly data from `input/Model_input.xlsx`: `Computation Data.` and `Cooling parameters`. |
| `input/retirement.csv` | 24-quarter retirement distribution from `Lifespan normal distribution`. |
| `input/settings.json` | A small set of operating assumptions and demo impact factors. |

The scale calculation keeps purchase-quarter GPU performance and board power with each cohort, and models training and inference racks separately. Cooling capacity uses **quarter-end rated power**. Electricity uses **quarter-average rated power**, utilization, liquid-cooling share and `PUE - 1`.

## Output columns

`training_racks` and `inference_racks` are expected rack stocks at quarter end. `liquid_it_kw` is liquid-cooled nameplate total IT load. `coolant_inventory_kg` is the estimated fluid installed at quarter end. `new_coolant_kg` is a simplified net-fill plus quarterly make-up flow. `cooling_electricity_kwh` is the quarterly cooling overhead. The three `kg_co2e` columns are illustrative climate-change outputs from coolant supply, electricity and their sum.

## Scope of the simplification

- One deterministic AI path and one liquid-cooling share path; no Monte Carlo or nine-scenario grid.
- Coolant supply is approximated as positive change in installed fluid plus make-up for annual losses. The full model has more detailed cohort cooling assignments, retirement, retrofit and recovery accounting.
- The three impact factors in `settings.json` are **illustrative placeholders** (2 and 5 kg CO2e/kg coolant, 0.5 kg CO2e/kWh electricity). They do not come from the LCA workbook. Replace them with factors you are licensed to share before using burden outputs for analysis.
- Advanced coolant, recycling, PUE variants, sensitivity analysis, other LCA indicators and manuscript figure generation are outside this demo.

The original project files are not imported or modified. The quarterly data and retirement probabilities are copied into the demo so it can run on its own.
