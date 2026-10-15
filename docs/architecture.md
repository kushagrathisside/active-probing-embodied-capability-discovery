# Architecture

This document describes how the code is organised, what each module owns, the data passed between them, and how a run is seeded, timed and extended. The physics and skills are in [model.md](model.md), the learning in [learning.md](learning.md), and the results in [assessment.md](assessment.md).

## 1. Scope

The code assesses one simulated 6-DOF arm on a fixed base, one joint at a time. It answers two questions for each joint:

1. Which damage state (healthy, locked, weak motor, missing sensor, broken link) is most likely present?
2. What is the highest tier (T0 to T3) the joint can still do?

Two sources of evidence are supported:

- **Scripted probes**: the PD reference controller runs a fixed motion. Used for T0 and as the reference for evaluation.
- **Learned skills**: a trained two-gain controller runs the same motion. Used for T1 to T3 in the stage-1 configuration.

## 2. Layers

Modules depend only on the layers below them. There are no cycles.

```
Layer 5   pipeline ──────────────┬── episode
          (assessors, outcomes,  │   (belief, gating, planner, damage, platform_adapter)
           platform_adapter)     │
Layer 4   outcomes ── gating ── planner ── belief
          (platform_adapter)    (belief)  (config)
Layer 3   assessors ──── training
          (runner, tasks)  (config, damage, policies, runner)
Layer 2   runner
          (physics, policies, tasks)
Layer 1   tasks ── physics
          (physics)  (none)
Layer 0   config, tiers, damage, platform_adapter, policies, physics, belief,
          report, evaluate                       (no internal dependencies, or config only)
```

`report` and `evaluate` have no internal dependencies. `report` reads only the episode's final state. `evaluate` reads the report and the episode's hidden truth, and nothing in the planning path imports it.

## 3. Modules

| Module | Layer | Lines | Responsibility |
|---|---|---|---|
| `config.py` | 0 | 16 | Locates `configs/` and reads YAML. |
| `tiers.py` | 0 | 83 | Tier checks, thresholds, noise. Scalar and vector pass and margin functions. |
| `damage.py` | 0 | 45 | Damage hypotheses (`Fault`), prior, sampling of the true state. |
| `platform_adapter.py` | 0 | 81 | Loads a robot: joints, chains, probes, which assessor judges each tier. |
| `physics.py` | 0 | 141 | Batched single-joint dynamics. Plant parameters, `simulate`, `make_plant`. |
| `policies.py` | 0 | 78 | `LinearFeedback` control law, `controller_for`, `PolicyRecord`, `PolicyStore`. |
| `belief.py` | 0 | 56 | Bayes update, `prob_level_at_least`, expected information gain. |
| `report.py` | 0 | 91 | Physical state report, Markdown and JSON. |
| `evaluate.py` | 0 | 28 | Scores a report against the hidden truth. |
| `tasks.py` | 1 | 98 | Skills: reference trajectories and the readings for each tier. |
| `runner.py` | 2 | 39 | Runs a skill on a batch of joints. Adds reading noise. |
| `assessors.py` | 3 | 146 | `ScriptedAssessor`, `LearnedAssessor`, `Prediction`, `Execution`. |
| `training.py` | 3 | 156 | Evolution strategies, the healthy gate, Wilson bound, settings loader. |
| `outcomes.py` | 4 | 66 | Builds the table of predictions. Keeps model, reference and truth apart. |
| `gating.py` | 4 | 65 | Per-joint, per-tier status (`ready`, `wait`, `blocked`, `unknown`, `pass`, `fail`). |
| `planner.py` | 4 | 95 | Scores allowed probes (information, risk, energy). Four selection methods. |
| `pipeline.py` | 5 | 37 | Chooses each tier's assessor from the platform config and builds the table. |
| `episode.py` | 5 | 109 | One probing run: hidden damage, the robot's own runs, the belief update, the log. |
| `__init__.py` | — | 22 | Module list. |

Total: 1,452 lines in `src/`. Experiments add 4 scripts and the tests add 10 files (2,537 lines in all).

## 4. Interfaces

The data passed between layers is held in a small set of frozen dataclasses. Their fields are below.

| Type | Module | Fields | Meaning |
|---|---|---|---|
| `Plant` | physics | `tau_max, inertia, gravity, low, high, torque_scale, stiffness_scale, locked` | One array entry per joint in a batch. |
| `Rollout` | physics | `ref, q, tau, demand` (T×n), `alive` (T×n bool), `violations` (dict), `energy_j` (n) | The full history of a batch run. |
| `Skill` | tasks | `tier, kind, duration_s, params, budget_fraction` | The task a tier asks for. |
| `LinearFeedback` | policies | `kp, kd` (n) | The control law. `torques(err, qd)` returns `(stiffness, damping)`. |
| `PolicyRecord` | policies | `joint, tier, kp_multiplier, kd_multiplier, trusted, gate, training, history` | A trained policy and its evidence. JSON on disk. |
| `Prediction` | assessors | `pass_prob, violation_prob, p_any_violation, energy_j, metrics, margin, trusted` | What the planner expects under one hypothesis. |
| `Execution` | assessors | `passed, violations, energy_j` | What happens on the robot when a skill runs. |
| `Table` | outcomes | `predictions, levels, reference_levels, trusted, assessors` | The planner's model, built once per run. |
| `State` | gating | `joint_names, proximal, tiers, levels, beliefs, gating, confidence, max_repeats, probe_counts, untrusted` | Everything the planner knows at one step. |
| `Episode` | episode | `state, log, true_states, reference_levels, method, seed, budget` | The result of one run. `true_states` is for evaluation only. |
| `ProbeRecord` | episode | `step, joint, tier, passed, aborted, violations, energy_j` | One line of the probe log. |

## 5. One episode, step by step

1. **Build the table** (`pipeline.build_model`). For each joint, each tier and each hypothesis, the assessor predicts the pass probability, violation probabilities, energy and margin. The scripted reference is computed alongside, for evaluation.
2. **Draw the truth** (`episode.SimulatedRobot`). The true damage of each joint is sampled from the prior, using `random.Random(seed)`.
3. **Mark untrusted skills.** Any learned tier whose policy failed the healthy gate is passed to `State.untrusted`. Its status is `unknown` from the start.
4. **Choose** (`planner.choose`). The allowed tiers (`status == ready`) are scored: expected information gain in bits, minus the risk weight times expected risk, minus the energy weight times expected energy over the energy scale. Probes whose chance of violating a limit exceeds `risk_cap` are vetoed. The best remaining probe is taken. The planner never skips an allowed probe, because a tier can only be concluded by running it.
5. **Run the robot's own skill** (`SimulatedRobot.run`). The true assessor runs the true hypothesis, with randomised parameters and noise drawn from `numpy.random.default_rng(seed + 1)`. It returns an `Execution`.
6. **Update the belief** (`belief.update`). Bayes' rule with the pass probability from the table, floored at 0.01 per hypothesis.
7. **Conclude** (`gating.State.status`). A tier passes when the belief that the joint reaches it is at least 0.95, and fails when that belief is at most 0.05. This needs at least one probe of that tier. After two probes without a conclusion, the tier is `unknown`.
8. **Repeat** until the budget (40 probes) is spent or no allowed, safe probe is left.
9. **Report** (`report.build_report`). For each joint: the level (highest tier passed, with no gap below it), whether that level is determined, each tier's status, the most likely hypothesis and its probability, and the probe count.
10. **Evaluate** (`evaluate.score_episode`), only for experiments. Compares the report with `true_states` and `reference_levels`.

## 6. Seeds and reproducibility

Every random stream is derived from a fixed seed. No code uses the global random state.

| Stream | Seed source | Used for |
|---|---|---|
| Training, per job | `seeds.training` (1000) + job index | Candidate perturbations, training rollouts |
| Gate, per job | `seeds.gate` (2000) + job index | Healthy gate rollouts |
| Table, per prediction | `numpy.random.SeedSequence([seeds.table, joint, tier, hypothesis])` | Model table rollouts |
| Truth, per episode | `seed + 1` (numpy) | The robot's own runs |
| Damage, per episode | `seed` (Python `random`) | Sampling the true hypothesis |
| Policy choices, per episode | `seed + 2` (Python `random`) | The `random` baseline |

The job index for training counts every (joint, tier) slot in order, including the scripted T0 slots. So no two training jobs share a seed, and a gate seed is never a training seed. This was checked after a bug in which the gate reused the next job's training seed (commit `70ab4e4`).

## 7. Performance

Measured on the development machine (WSL2, Python 3.11):

| Operation | Measured | Notes |
|---|---|---|
| One skill, batch of 128 candidates, one generation | about 0.1 s | Dominated by per-step numpy overhead. |
| Train all 18 learned skills | 19 s wall, 69 s CPU | `--workers 4`. Each job is independent. |
| Scripted table (6 joints × 4 tiers × 5 hypotheses) | 3.9 s | Reference computed once per entry. |
| Learned table (same size, 50 rollouts per entry) | 6.5 s | |
| One planner episode (6 probes) | 0.20 s | |
| Assessment script | 13 s | Builds the scripted and learned tables. |
| Comparison, 100 seeds, 3 budgets, 6 methods | 20 min 49 s | Serial. Heavy: run it on a faster machine or with fewer seeds. |
| Test suite (66 tests) | 16 to 27 s | Includes one scripted table build and one short training run. |

Per-step cost is the limit. The physics runs a Python loop over time steps, with numpy operations on arrays the length of the batch. Each step has a fixed overhead, so batching many candidates into one run is the cheap way to score a population. That is why training batches its candidates together.

## 8. Extension points

Each extension point is one interface. Adding a robot, an assessor or a policy class does not change the tier logic.

| To add | Change | Does not change |
|---|---|---|
| A robot | A new `configs/platform_<name>.yaml`. | Tiers, belief, gating, planner, report. |
| A new skill task | A new `kind` in `tasks.py` and a row in the platform's `probes`. | Physics, planner. |
| A richer policy (e.g. an MLP) | A class with `torques(err, qd)`, a new `PolicyRecord` field, and a branch in `runner.run_gains`. | Assessors, planner, table. |
| A learned or scripted assessor per tier | An entry under `assessment:` in the platform config. | Everything else. |
| A physics model (chain, whole arm) | A new simulate function with the same `Plant` and `Rollout` shapes. | Assessors and above. |
| A new damage hypothesis | A row in `configs/damage.yaml` and a field on `Fault` if it needs a new physical effect. | Planner, report. |
| A new selection method | A branch in `planner.choose`. | Everything else. Baselines already share this function. |
| Whole-robot gating (the RQ3 baseline) | `gating: robot` in `configs/planner.yaml`. | Everything else. |

## 9. Known structural limits

- **One joint at a time.** The physics simulates a single joint, so the joints do not interact. Chain gating is only a rule about which joint is tested, not a physical coupling.
- **The belief is per joint.** A shared-damage belief (RQ3, second half) is not implemented.
- **Learned skills are gain-only.** A two-parameter policy cannot express a richer strategy. It is a deliberate stage-1 limit, documented in [learning.md](learning.md).
