# PFAS-data-center

This repository introduces a modeling workflow for examining how growth in AI computing may affect data-center liquid cooling and its environmental burden. The model connects training and inference demand to server deployment, coolant requirements, cooling electricity use, and climate-change impacts.

## Project approach

The workflow is organized into four steps:

1. Estimate quarterly computing demand from AI model training and inference activity.
2. Translate that demand into new, operating, and retired GPU racks. Hardware performance and board power remain tied to the quarter in which each rack was purchased.
3. Estimate liquid-cooled IT capacity, coolant inventory, and cooling electricity for single-phase and two-phase systems.
4. Combine coolant supply and cooling electricity with impact factors to illustrate the environmental-burden calculation.

The broader research model also explores alternative AI growth and cooling scenarios, uncertainty, coolant recovery, and other environmental indicators. The files shared here provide an initial, compact demonstration of the core calculation chain.

## Demo

The [`Demo/`](Demo/) directory is a self-contained Python example. It uses a Moderate AI-growth and liquid-cooling path over 2020 Q1–2030 Q4. Quarterly inputs and the GPU retirement distribution are included in [`Demo/input/`](Demo/input/); no files from the larger research project are needed to run it.

Run it from the repository root with Python 3:

```bash
python3 Demo/run_demo.py
```

No third-party packages are required. The script writes [`Demo/output/demo_results.csv`](Demo/output/demo_results.csv), with one row per quarter and cooling phase. The output includes rack stock, liquid-cooled IT capacity, coolant inventory and supply, cooling electricity, and illustrative climate-change burdens.

## How to interpret the demo

This example shows the structure of the model rather than reproducing the study's results. It uses one deterministic scenario, a simplified coolant-supply calculation, and **illustrative impact factors** in [`Demo/input/settings.json`](Demo/input/settings.json). Those factors are placeholders, not values from the full life-cycle assessment. The resulting burden figures should therefore not be used as research estimates.

The demo keeps two distinctions central to the full workflow: coolant capacity is based on **quarter-end rated IT power**, while electricity is based on **quarter-average operating power**; training and inference are modeled as separate rack fleets.
