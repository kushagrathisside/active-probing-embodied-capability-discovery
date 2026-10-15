# Assessment: results and what they mean

This document reports the stage-1 results. Every number is taken from `results/assessment_arm6.md` and `results/comparison_*.csv`, which the code regenerates. Commands to reproduce each result are given at the end of each section.

## 1. What was measured

Three kinds of result:

1. **Performance signature.** For each joint and learned skill, the pass probability under each damage state, and the mean margin to the limit.
2. **Agreement.** For each joint and damage state, whether the model level (from the learned assessors) equals the reference level (from the scripted controller).
3. **Identifiability.** For each joint, which pairs of damage states no tier separates by at least 0.5 in pass probability.

Plus one benchmark: the four planning methods, compared over 100 seeds.

## 2. Performance signature (learned policies)

Pass probability is the Laplace-smoothed rate from 50 rollouts per cell. Healthy cells therefore read 0.98 rather than 1.00, because `(50+1)/(50+2) = 0.981`.

Margin is the mean signed distance to the tier's tightest check. For T1, T2 and T3's sag, that is in degrees. For T3 the torque check is a fraction of rated torque, so the margin is the smaller of the two. Positive is inside the limit. Negative values with a pass probability of 0.02 mean the skill fails almost always.

| Joint | Damage | T0 pass | T1 pass | T2 pass | T3 pass | T1 margin | T2 margin | T3 margin |
|---|---|---|---|---|---|---|---|---|
| base | healthy | 1.00 | 0.98 | 0.98 | 0.98 | +0.99 | +1.82 | +0.73 |
| base | locked | 0.00 | 0.02 | 0.02 | 0.02 | n/a | n/a | −0.20 |
| base | weak_motor | 1.00 | 0.98 | 0.98 | 0.98 | +0.99 | +1.83 | +0.73 |
| base | missing_sensor | 0.00 | 0.00 | 0.00 | 0.00 | n/a | n/a | n/a |
| base | broken_link | 1.00 | 0.79 | 0.73 | 0.98 | +0.09 | +0.09 | +0.75 |
| shoulder | healthy | 1.00 | 0.98 | 0.98 | 0.98 | +0.99 | +1.62 | +0.26 |
| shoulder | locked | 0.00 | 0.02 | 0.02 | 0.02 | n/a | n/a | −0.19 |
| shoulder | weak_motor | 1.00 | 0.98 | 0.98 | **0.27** | +0.99 | +1.62 | +0.37 |
| shoulder | missing_sensor | 0.00 | 0.00 | 0.00 | 0.00 | n/a | n/a | n/a |
| shoulder | broken_link | 0.69 | 0.60 | 0.02 | 0.02 | +0.02 | −1.59 | −7.38 |
| elbow | healthy | 1.00 | 0.98 | 0.98 | 0.98 | +0.99 | +1.67 | +0.40 |
| elbow | locked | 0.00 | 0.02 | 0.02 | 0.02 | n/a | n/a | −0.21 |
| elbow | weak_motor | 1.00 | 0.98 | 0.98 | 0.98 | +0.99 | +1.67 | +0.41 |
| elbow | missing_sensor | 0.00 | 0.00 | 0.00 | 0.00 | n/a | n/a | n/a |
| elbow | broken_link | 0.90 | **0.02** | 0.02 | 0.02 | −0.65 | −1.25 | −5.42 |
| wrist_1 | healthy | 1.00 | 0.98 | 0.98 | 0.98 | +0.99 | +1.82 | +0.61 |
| wrist_1 | locked | 0.00 | 0.02 | 0.02 | 0.02 | n/a | n/a | −0.21 |
| wrist_1 | weak_motor | 1.00 | 0.98 | 0.98 | 0.98 | +0.99 | +1.82 | +0.62 |
| wrist_1 | missing_sensor | 0.00 | 0.00 | 0.00 | 0.00 | n/a | n/a | n/a |
| wrist_1 | broken_link | 1.00 | **0.02** | 0.79 | 0.71 | −0.51 | +0.09 | +0.07 |
| wrist_2 | healthy | 1.00 | 0.98 | 0.98 | 0.98 | +1.00 | +1.84 | +0.65 |
| wrist_2 | locked | 0.00 | 0.02 | 0.02 | 0.02 | n/a | n/a | −0.20 |
| wrist_2 | weak_motor | 1.00 | 0.98 | 0.98 | 0.98 | +0.99 | +1.84 | +0.65 |
| wrist_2 | missing_sensor | 0.00 | 0.00 | 0.00 | 0.00 | n/a | n/a | n/a |
| wrist_2 | broken_link | 1.00 | 0.48 | 0.98 | 0.98 | +0.01 | +0.25 | +0.35 |
| wrist_3 | healthy | 1.00 | 0.98 | 0.98 | 0.98 | +0.99 | +1.86 | +0.62 |
| wrist_3 | locked | 0.00 | 0.02 | 0.02 | 0.02 | n/a | n/a | −0.19 |
| wrist_3 | weak_motor | 1.00 | 0.98 | 0.98 | 0.98 | +0.99 | +1.86 | +0.61 |
| wrist_3 | missing_sensor | 0.00 | 0.00 | 0.00 | 0.00 | n/a | n/a | n/a |
| wrist_3 | broken_link | 1.00 | 0.94 | 0.98 | 0.98 | +0.16 | +0.43 | +0.67 |

Reading the signature:

- **Locked and missing sensor are both 0.00 at T0.** They are indistinguishable on every tier. Both fail T0 and gate everything above it.
- **Weak motor shows only on the shoulder's T3** (0.27 pass, so detected in 73% of runs). The other joints pass every tier under a weak motor, as they must, since their loads are below the reduced torque.
- **Broken link is visible on T2 on the shoulder and elbow** (0.02 pass). It is visible on T1 on the elbow and wrist_1 (0.02 pass) and partly on wrist_2 (0.48), where the learned T1 is softer than the reference (section 3).
- **Base and wrist_3 broken link pass every tier** with pass probabilities of 0.73 to 0.98, so the learned policies miss this damage on those joints.

Reproduce: `python -m experiments.assess_policies`.

## 3. Agreement: model level against reference level

The model level is what the planner believes. The reference level is what the scripted controller reaches, noise-free. Agreement means the learned policies reach the same level as the simple controller.

| Joint | Damage | Reference | Model | Agree |
|---|---|---|---|---|
| base | healthy | 3 | 3 | yes |
| base | locked | −1 | −1 | yes |
| base | weak_motor | 3 | 3 | yes |
| base | missing_sensor | −1 | −1 | yes |
| base | broken_link | 1 | **3** | **no** |
| shoulder | healthy | 3 | 3 | yes |
| shoulder | locked | −1 | −1 | yes |
| shoulder | weak_motor | 2 | 2 | yes |
| shoulder | missing_sensor | −1 | −1 | yes |
| shoulder | broken_link | 1 | 1 | yes |
| elbow | healthy | 3 | 3 | yes |
| elbow | locked | −1 | −1 | yes |
| elbow | weak_motor | 3 | 3 | yes |
| elbow | missing_sensor | −1 | −1 | yes |
| elbow | broken_link | 1 | **0** | **no** |
| wrist_1 | healthy | 3 | 3 | yes |
| wrist_1 | locked | −1 | −1 | yes |
| wrist_1 | weak_motor | 3 | 3 | yes |
| wrist_1 | missing_sensor | −1 | −1 | yes |
| wrist_1 | broken_link | 1 | **0** | **no** |
| wrist_2 | healthy | 3 | 3 | yes |
| wrist_2 | locked | −1 | −1 | yes |
| wrist_2 | weak_motor | 3 | 3 | yes |
| wrist_2 | missing_sensor | −1 | −1 | yes |
| wrist_2 | broken_link | 1 | **0** | **no** |
| wrist_3 | healthy | 3 | 3 | yes |
| wrist_3 | locked | −1 | −1 | yes |
| wrist_3 | weak_motor | 3 | 3 | yes |
| wrist_3 | missing_sensor | −1 | −1 | yes |
| wrist_3 | broken_link | 1 | **3** | **no** |

**25 of 30 pairs agree.** All five disagreements are broken links, in two groups:

- **Missed damage (base, wrist_3): model 3, reference 1.** The learned policies pass a broken link on joints with little load. The signal is too weak for their T2 check to fail. This is the dangerous direction: it overclaims capability.
- **Policy gap (elbow, wrist_1, wrist_2): model 0, reference 1.** The learned T1 is softer than the nominal controller: its stiffness multiplier is about 0.51 on these three joints, half the reference's, so a broken link fails T1 where the reference passes. This direction underclaims capability, and it is a cost of learning rather than a hidden fault.

The shoulder agrees because its load makes the broken link fail T2 for both controllers.

Reproduce: `python -m experiments.assess_policies`.

## 4. Identifiability

Two damage states are **separable** if some tier's pass probability differs between them by at least 0.5. A pair that is not separable cannot be told apart by any tier with these skills, so the report cannot distinguish it.

Each joint has 10 pairs of damage states (5 choose 2), so 60 pairs in total.

**Scripted reference only** (the test that comes first, before any learned policy):

| Joint | Not separable |
|---|---|
| base | healthy / weak_motor |
| shoulder | none |
| elbow | healthy / weak_motor |
| wrist_1 | healthy / weak_motor |
| wrist_2 | healthy / weak_motor |
| wrist_3 | healthy / weak_motor |

5 of 60 pairs are not separable. The one shared pair is healthy against weak motor, which is expected: a weak motor only shows under load, and only the shoulder carries enough.

**Learned policies:**

| Joint | Not separable | Count |
|---|---|---|
| base | healthy / weak_motor, healthy / broken_link, locked / missing_sensor, weak_motor / broken_link | 4 |
| shoulder | locked / missing_sensor | 1 |
| elbow | healthy / weak_motor, locked / missing_sensor | 2 |
| wrist_1 | healthy / weak_motor, locked / missing_sensor | 2 |
| wrist_2 | healthy / weak_motor, healthy / broken_link, locked / missing_sensor, weak_motor / broken_link | 4 |
| wrist_3 | healthy / weak_motor, healthy / broken_link, locked / missing_sensor, weak_motor / broken_link | 4 |

17 of 60 pairs are not separable with the learned policies, against 5 with the scripted reference. The additional confusions come from the learned policies, not the physics:

- **healthy / broken_link** on base, wrist_2 and wrist_3 (the missed damage in section 3).
- **weak_motor / broken_link** on base, wrist_2 and wrist_3, for the same reason.

**Locked / missing sensor** is not separable on any joint, in either set. It is a real limit of the sensing model: both produce no usable motion, and no current tier differs between them. A check that reads the sensor without moving the joint would separate them. This is listed in [robotics-limitations.md](robotics-limitations.md).

## 5. Planning comparison

Four methods, same damage cases (seeds 0 to 99), same budget and gating:

- **planner**: expected information gain minus weighted risk and energy, with the safety veto. Three risk weights were run (0, 1, 4).
- **random**: an allowed probe chosen uniformly.
- **fixed**: the battery in tier order, joints from the base outwards.
- **passive**: no probes at all. A floor.

Metrics, averaged over 100 seeds:

- **Coverage**: share of joints whose level is determined.
- **Accuracy**: share of joints whose level is determined and equals the reference level.
- **Overclaim**: share of joints reported above the reference level.
- **Probes**: probes used. **Aborts**: probes that hit a safety limit. **Energy**: energy proxy in J per episode.

### 5.1 Learned pipeline (the stage-1 result)

| Budget | Method | Coverage | Accuracy | Overclaim | Probes | Aborts | Energy (J) |
|---|---|---|---|---|---|---|---|
| 12 | planner (risk 0, 1, 4) | 0.183 | 0.167 | 0.005 | 10.25 | 0.00 | 2.37 |
| 12 | random | 0.292 | 0.277 | 0.008 | 10.23 | 0.01 | 4.34 |
| 12 | fixed | 0.183 | 0.167 | 0.005 | 10.25 | 0.00 | 2.36 |
| 24 | planner (risk 0, 1, 4) | 0.673 | 0.640 | 0.020 | 15.76 | 0.03 | 7.08 |
| 24 | random | 0.683 | 0.647 | 0.020 | 15.73 | 0.02 | 7.18 |
| 24 | fixed | 0.682 | 0.645 | 0.022 | 15.81 | 0.02 | 7.17 |
| 40 | planner (risk 0, 1, 4) | 0.673 | 0.640 | 0.020 | 15.76 | 0.03 | 7.08 |
| 40 | random | 0.683 | 0.647 | 0.020 | 15.73 | 0.02 | 7.18 |
| 40 | fixed | 0.682 | 0.645 | 0.022 | 15.81 | 0.02 | 7.17 |
| any | passive | 0.000 | 0.000 | 0.000 | 0 | 0 | 0 |

The three planner rows are identical to the second decimal: the risk weight does not change the outcome here.

Reproduce: `python -m experiments.compare_methods --seeds 100 --budgets 12 24 40 --risk-weights 0 1 4` (about 21 minutes on the development machine).

### 5.2 Reference controller (scripted), for comparison

| Budget | Method | Coverage | Accuracy | Probes | Aborts | Energy (J) |
|---|---|---|---|---|---|---|
| 12 | planner | 0.183 | 0.183 | 10.28 | 0.00 | 1.95 |
| 12 | random | 0.283 | 0.280 | 10.16 | 0.01 | 3.04 |
| 12 | fixed | 0.173 | 0.173 | 10.28 | 0.00 | 1.63 |
| 24 | planner | 0.650 | 0.650 | 15.68 | 0.03 | 5.02 |
| 24 | random | 0.647 | 0.643 | 15.54 | 0.03 | 5.01 |
| 24 | fixed | 0.650 | 0.650 | 15.68 | 0.03 | 5.02 |

Scripted overclaim is 0.00 in every row, because the scripted model is the reference.

### 5.3 Whole-robot gating (RQ3 baseline), scripted

| Budget | Method | Coverage | Probes | Energy (J) |
|---|---|---|---|---|
| 12 | planner | 0.118 | 9.30 | 1.04 |
| 24 | planner | 0.443 | 13.84 | 2.91 |
| 40 | planner | 0.443 | 13.84 | 2.91 |

Chain gating reaches 0.65 coverage at budget 24, against 0.44 for whole-robot gating. That supports the first half of RQ3 for the scripted reference. The learned pipeline was not run with whole-robot gating.

## 6. Interpretation

**What the stage-1 pipeline establishes.**

- The learned skills are trustworthy on healthy joints: all 18 pass the gate, and healthy cells pass 98% of the time.
- The damage signatures are mostly where the reference puts them. The shoulder's weak motor and hold, and the shoulder's broken link, match exactly.
- The learned pipeline can be run end to end: train, gate, assess, plan, report and evaluate, with every step reproducible from a seed.

**What it does not establish.**

- **The planning method does not beat the fixed battery.** On a single chain, the set of allowed probes at any time is small. Usually one or two are allowed at once, so the order barely matters. The planner's advantage would need more choice, which means more chains (a quadruped) or more joints per chain.
- **The risk weight has no effect.** Aborts are rare (0.02 to 0.03 per episode), so the risk term never changes the order. A test at a higher abort rate would be needed for RQ2.
- **Overclaim is non-zero for the learned pipeline** (up to 0.022). It comes from the missed broken links on the base and wrist_3. The scripted reference never overclaims.

**Where the learned policies are weaker than the reference.** The policy gap has two sources:

1. The learned T1 gains are softer than the reference on the elbow and wrists (section 3, policy gap). A broken link fails them.
2. The learned T2 and T3 gains are at their clamps, so they cannot compensate for damage the reference would also fail. This is the intended effect of the clamp.

**What would change the conclusions.**

- A whole-arm model, so that joints interact and a shoulder fault changes the loads on the wrists.
- A stiffness probe at several poses, to find broken links on lightly loaded joints.
- A sensor-only check, to separate locked from missing sensor.
- A richer policy class, which could close the T1 gap without the stiffness clamp. The clamp is a stage-1 safety choice, and removing it would bring back the compensation effect.

## 7. How to reproduce everything

```bash
.venv/bin/python -m experiments.train_policies --workers 4     # 19 s: writes results/policies/arm6/
.venv/bin/python -m experiments.assess_policies                # 13 s: writes results/assessment_arm6.md
.venv/bin/python -m experiments.compare_methods --seeds 100 --budgets 12 24 40 --risk-weights 0 1 4 \
    --out results/comparison_learned.csv                       # ~21 min: writes the learned CSV
.venv/bin/python -m experiments.compare_methods --seeds 100 --budgets 12 24 40 --risk-weights 0 1 4 \
    --assessment scripted --out results/comparison_chain.csv   # scripted CSV
```

Results are in `results/`, which is git-ignored. The policy JSON files are regenerated by `train_policies`, so the repository does not carry them.
