# Active Probing for Embodied Capability Discovery

## Overview

This project investigates how a robot can actively discover its remaining capabilities after experiencing damage, degradation, or changes in its physical condition.

Instead of assuming that the robot's original capabilities remain unchanged, the system allows the robot to perform carefully selected probing actions and use the resulting observations to update its understanding of what it can and cannot do.

The project focuses on capability discovery as an active decision-making problem, where the robot must balance the expected information gained from an experiment against factors such as physical risk, energy consumption, and execution time.

## Problem Statement

Robots operating in real-world environments may experience actuator failures, sensor degradation, mechanical damage, or other changes that alter their capabilities.

A robot that relies only on its original capability model may attempt actions that are no longer feasible or may fail to exploit capabilities that remain available after damage.

The goal of this project is to develop an approach that enables a robot to actively probe its environment and body to discover its remaining capabilities. The robot should select informative experiments, observe their outcomes, and update its capability representation based on the acquired evidence.

## Objectives

- Represent the capabilities available to a robotic system.
- Model uncertainty about capabilities after damage or degradation.
- Select probing actions that provide useful information about uncertain capabilities.
- Incorporate factors such as expected information gain, physical risk, energy consumption, and execution time.
- Update the robot's capability model using observations from executed probes.
- Evaluate whether active probing can improve capability identification compared with passive or fixed testing strategies.

## High-Level Approach

The planned workflow is:

1. Define a hierarchical representation of robot capabilities.
2. Introduce simulated damage or capability degradation.
3. Identify capabilities whose status is uncertain.
4. Generate candidate probing actions.
5. Estimate the expected utility of each probe.
6. Select and execute an informative probe.
7. Observe the outcome.
8. Update the capability model.
9. Repeat until sufficient information about the robot's capabilities has been obtained.
10. Evaluate the resulting capability-discovery performance.

## Current Implementation

The first version runs in simulation on a 6-DOF arm. Each part is a joint, and each joint is checked through the tiers T0 to T3.

- **Tier logic** (`src/tiers.py`): each tier is a set of checks with thresholds from `configs/tiers.yaml`.
- **Platform adapter** (`src/platform_adapter.py`, `configs/platform_arm6.yaml`): joints, chains, limits, probes and safety settings. A new robot is a new YAML file.
- **Simulator** (`src/sim.py`): a single-joint model. It runs every probe under every damage hypothesis to get the planner's predictions, and it serves as the ground truth.
- **Damage hypotheses** (`src/damage.py`, `configs/damage.yaml`): healthy, locked, weak motor, missing sensor, broken link.
- **Belief and planner** (`src/belief.py`, `src/planner.py`): a Bayesian belief per joint. Probes are chosen by expected information gain minus weighted risk and energy, with a safety veto.
- **Gating** (`src/gating.py`): a tier is tested only after the tiers below it pass, within the same chain. The whole-robot baseline is also available (`gating: robot`).
- **Report** (`src/report.py`): the physical state report, as Markdown and JSON. It is built only from probe results.
- **Evaluation** (`src/evaluate.py`): compares the report with the simulated truth. The planner never sees the truth.

Design choices and their defaults are in [`docs/design-decisions.md`](docs/design-decisions.md). Items marked **Confirm** are open.

### Running

Requires Python 3.11 or newer with `venv`. Install the dependencies in a virtual environment:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Run the tests:

```bash
.venv/bin/python -m pytest
```

Run one episode and write its report to `results/`:

```bash
.venv/bin/python -m experiments.run_episode --method planner --seed 1
```

Compare the methods over many seeds. `--risk-weights` is the RQ2 sweep, and `--gating robot` is the RQ3 baseline:

```bash
.venv/bin/python -m experiments.compare_methods --seeds 100 --budgets 6 12 24 40
```

Results go to `results/`, which is git-ignored except for `.gitkeep`.

### Not yet implemented

- T4 (whole-body posture) and any legged platform. These are the next step, to test that the tier logic transfers.
- A shared-damage belief (RQ3, second half).
- A probe that reads the sensor without moving the joint, which would separate a locked joint from a missing sensor.

## Project Structure

```text
g11-active-probing/
│
├── README.md
├── requirements.txt
├── pytest.ini
├── .gitignore
│
├── configs/                  tiers, platform adapter, damage hypotheses, planner settings
│   ├── tiers.yaml
│   ├── platform_arm6.yaml
│   ├── damage.yaml
│   └── planner.yaml
│
├── src/                      core implementation (module list in src/__init__.py)
│
├── experiments/
│   ├── run_episode.py        one episode and its physical state report
│   └── compare_methods.py    methods compared over seeds and budgets
│
├── tests/                    tiers, simulator, gating, belief, planner, episodes
│
├── results/                  experiment outputs (git-ignored)
│
└── docs/
    └── design-decisions.md   open choices and their defaults
```
