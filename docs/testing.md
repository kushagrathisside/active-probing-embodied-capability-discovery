# Testing

The suite has 66 tests in 10 files. It runs in 16 to 27 seconds on the development machine, including one scripted table build and one short training run. Run it from the repository root:

```bash
.venv/bin/python -m pytest              # all 66 tests
.venv/bin/python -m pytest -q tests/test_physics.py   # one file
.venv/bin/python -m pytest -k weak      # tests whose names contain "weak"
```

Three session-scoped fixtures in `tests/conftest.py` are shared across the suite:

| Fixture | What it builds | Cost |
|---|---|---|
| `arm` | The arm6 platform, the tiers, the damage model and the scripted table | Built once, about 4 s |
| `fast_settings` | Training settings with 16 candidates, 2 instances, 12 generations, 40 gate runs, 10 table rollouts | Instant |
| `shoulder_store` | Shoulder policies for T1 to T3, trained with `fast_settings` into a temporary folder | About 2 s |

## 1. What each file guards

| File | Tests | What it guards |
|---|---|---|
| `test_tiers.py` | 8 | Pass and fail at and around each threshold, for both directions (min and max). NaN readings always fail. Tier passes only if every check does. Noisy pass probability is 0.5 at the threshold and 0 or 1 without noise. Vector and scalar versions agree. Tier order is T0 to T3. |
| `test_physics.py` | 4 | A batch of one matches a batch of three, element by element. A locked joint in a batch does not change its neighbours. An aborted joint stops updating. The controller is called with an error array and a speed array, each the size of the batch, and nothing else. |
| `test_probes.py` | 11 | The scripted reference keeps its known answers: healthy joints reach the top tier; locked fails T0; missing sensor is never moved; the weak shoulder overloads on its hold; the weak motor on the base passes everything; the broken link fails T2 on every joint; healthy hold sag is g/kp; the table is deterministic; moves spend energy; the prior sums to 1. |
| `test_policies.py` | 4 | Zero error and zero speed give zero torque (no hidden gravity term). Gain multipliers scale the nominal gains exactly. A stored policy loads back equal. A missing policy fails with a message naming the training command. |
| `test_training.py` | 6 | The Wilson lower bound matches its formula. Centred ranks are symmetric and order-preserving. Training is deterministic for a seed. Learned gains stay inside their clamps. The stiffness multiplier never exceeds nominal. The gate's trust decision uses the Wilson bound. The real settings load. |
| `test_assessors.py` | 6 | Scripted and learned assessors return the same prediction shape. A trained healthy shoulder passes the move with probability above 0.8. A missing sensor is never run by a learned policy, and produces zero energy. A weak shoulder hold is predicted to overload with probability above 0.5. An execution reports the violations it hit. A locked base fails T0 on the scripted reference. |
| `test_belief.py` | 7 | Consistent evidence moves belief towards the hypothesis that predicts it. The probability floor stops a hypothesis being ruled out for good. Expected information is zero when all hypotheses predict the same outcome, and one bit when the outcome reveals the level exactly. Information is bounded by the outcome's entropy. Binary entropy values. Level probability sums correctly. |
| `test_gating.py` | 8 | A failed proximal joint blocks the joints below it at the same tier. The other chain is unaffected. A tier waits for its own lower tier. An undecided proximal joint makes the one below wait. A belief alone does not pass a tier: a probe is needed. The repeat limit gives `unknown`, which spreads down the chain. Whole-robot gating blocks joints in other chains; chain gating does not. An untrusted skill is `unknown` and its dependants inherit that. |
| `test_planner.py` | 7 | No candidates means stop. Passive never probes. The safety veto blocks a probe whose violation probability exceeds the cap, for the planner and for random. The planner still runs a zero-information probe if it is the only one left. It prefers the probe that separates hypotheses. A high risk weight makes it avoid a risky probe. The fixed battery runs in tier order, then joint order. |
| `test_episode.py` | 5 | A healthy arm reaches level 3 on every joint. A locked base blocks every joint above it at T0, and nothing above it is probed. Every method stays within the budget and produces a serialisable report. Passive runs no probes. The same seed and method give identical reports. |

## 2. Test categories

- **Unit tests of pure functions** (`tiers`, `belief`, `policies` control law, `training` helpers): exact values, edge cases, invariants.
- **Physics checks** (`physics`, `probes`): behaviour that follows from the equations, with the numbers taken from the parameters.
- **Interface checks** (`assessors`, `gating`, `planner`): the shapes and rules that the layers rely on.
- **End-to-end checks** (`episode`): a full run from table to report, on the real platform.

## 3. What is not tested

These are known gaps. Each is either listed in the stage-1 plan as acceptance, or covered by an experiment instead of a test.

| Gap | Why it is not a unit test | Where it is checked instead |
|---|---|---|
| The learned table on all 18 skills | Training all 18 takes 19 s, which is too slow for every test run. | `experiments/assess_policies.py` (signature and agreement). |
| Evolution strategies matches a grid search on the two-gain problem | Planned in `stage1-plan.md` section 3.11 item 5. **Not implemented.** | Not checked. The determinism test (`test_training_is_deterministic_for_a_seed`) is in place. |
| The gate's trust decisions on the real settings | Results depend on 18 full training runs. | `results/policies/arm6/*.json` (all 18 trusted). |
| The whole-robot gating comparison with learned policies | Requires a full learned table and a long run. | Only the scripted comparison was run (`results/comparison_robot.csv`). |
| Numerical accuracy of the physics against a reference integrator | No independent reference is available in the repository. | Checked by hand for the healthy shoulder sag (g/kp). |
| Hardware behaviour | Stage 1 is simulation only. | See [robotics-limitations.md](robotics-limitations.md). |

## 4. When a test fails

- **A physics test fails** after a change to `physics.py` or `tasks.py`. The scripted numbers in `test_probes.py` are the first thing to check, because they encode the design. If the numbers change on purpose, update the test and the table in [model.md](model.md) together.
- **A training determinism test fails**. The usual cause is a new random draw that is not seeded, or a change in draw order. The seeds are in `configs/training.yaml`.
- **A gating test fails**. Check the status rules in [architecture.md](architecture.md), section 5, step 7, and the gating module's docstring. The chain and robot modes differ only in `_prerequisites`.
- **A planner test fails** after a change to the score. The utility is `information − risk_weight · risk − energy_weight · energy / energy_scale`, and the risk is the weighted violation probability.

## 5. Static checks

The code is checked with `pyflakes` for unused names and imports. It is not run in the test suite. To check:

```bash
python3 -m pip install pyflakes
python3 -m pyflakes src experiments tests
```

The current code passes with no output.
