# Design decisions

Each choice below has a default that the code uses now. Items marked **Confirm** are open:
change the default if the team or the TA decides otherwise. Thresholds live in `configs/`, so
changing one does not need a code change.

## Platform and simulator

- **Platform: simulated 6-DOF arm on a fixed base, one kinematic chain.** Parts are joints.
  Quadruped and humanoid adapters come later, to show the tier logic transfers. **Confirm** the
  order of platforms.
- **Simulator: our own single-joint model in pure Python** (`src/sim.py`), with no MuJoCo or
  PyBullet dependency. Why: it is short enough to read, needs nothing to install, and runs
  fast enough to simulate every probe under every hypothesis. What it leaves out: joints do not
  interact, there is no contact, and gravity acts on a joint only through its own load value.
  A physics engine can replace `run_probe` behind the same interface.
- **Probes are simulated one joint at a time.** Gating means a joint is probed only after the
  joints below it pass, so the others can be treated as healthy during the probe.

## Tiers

- **T0 to T3 for the arm. T4 is not implemented.** Whole-body posture needs legs, so it has no
  meaning for an arm. It belongs with the quadruped or humanoid.
- **Load bearing is expressed through `gravity_nm`.** Only the T3 hold applies gravity. T0 to
  T2 run unloaded, as the brief says ("without bearing weight"). The base has zero gravity, so
  its T3 test passes trivially. It still runs, so the base's level is always tested to the top.
- **Thresholds are hand-picked starting values, not measured** (`configs/tiers.yaml`):

  | Tier | Check | Pass when |
  |---|---|---|
  | T0 | sensor valid, response to a 0.5 deg step, peak current | valid; response ratio ≥ 0.5; current ≤ 6 A |
  | T1 | final error after a 5 deg move | ≤ 1.0 deg |
  | T2 | RMS error on a 20 deg out-and-back path | ≤ 2.0 deg |
  | T3 | sag under gravity, peak torque / torque limit | sag ≤ 1.5 deg; torque ≤ 0.8 |

  **Confirm** these numbers with the TA. They are the pass threshold decision the team has to make.

## Probes

- **Probes are gentle by design.** Sizes: 0.5 deg step (T0), 5 deg move over 1 s (T1), 20 deg
  out and back over 4 s (T2), 3 s hold (T3). A probe aborts if the controller asks for more
  than 50% of the joint's torque limit (overload), or if the joint leaves its range.
- **An aborted probe is a fail** for that tier. The abort is also counted as a real violation
  in the report.

## Gating

- **"Below" means closer to the base in the same chain** (`configs/platform_arm6.yaml`). The
  rule is that a tier of a joint is tested only when the same tier of each joint below it has
  passed. **Confirm** this reading against the brief. The alternative (any tier) would allow
  more probes.
- **Consequence for one chain.** A failed shoulder blocks the elbow and wrists, even though
  their own probes are not affected by the shoulder's fault. With one chain, chain gating has
  the same effect as a barrier on everything above the failure. This is the case the brief
  describes, and it is the reason multi-chain platforms are needed to test RQ3.
- **Whole-robot baseline** (`gating: robot`): a tier is tested on any joint only after every
  other joint has passed the tier below. Used for RQ3.

## Damage hypotheses and belief

- **Hypotheses** (`configs/damage.yaml`): healthy; locked (the motor cannot move the joint); weak
  motor (40% of torque); missing sensor (no encoder reading, so the joint is never moved);
  broken link (position stiffness at 10%).
- **Prior**: 0.8 healthy, 0.05 for each fault. It is both the starting belief and the way the
  simulated ground truth is drawn. **Confirm** the fault rate.
- **Belief is per joint, independent.** A shared-damage belief (RQ3, second half) is not
  implemented yet.
- **Likelihood.** Each reading has Gaussian sensor noise. A tier passes when every check
  passes, so its pass probability is the product of the per-check probabilities. Every
  pass/fail probability is floored at 0.01, so a single wrong prediction cannot rule a
  hypothesis out for good.
- **Limitation: locked and missing sensor look the same** (both fail T0, both are level -1). The
  report shows the split, for example 0.48 / 0.48 on the shoulder, but probing cannot separate
  them yet. A check that reads the sensor without moving the joint would separate them.
- **Limitation: weak motor on lightly loaded joints is not detectable.** The elbow's 12 N*m
  load is below its 16 N*m reduced torque, so a weak elbow reaches level 3. This is correct
  physics, not a bug. It means the weak-motor hypothesis only shows up under load.

## Evidence and conclusions

- **A tier is concluded only by a probe of that tier.** The belief can make a tier
  "ready" or "unknown", but it cannot mark it passed or failed on its own. Without this rule the
  simulator showed a false pass: after a T0 pass, the shoulder's belief reached 0.96 for T2 with
  no T2 probe, while the true state was a broken link that T2 would catch.
- **Pass** when the belief that the joint reaches the tier is ≥ 0.95. **Fail** when it is ≤ 0.05.
  After 2 probes of one tier with no conclusion, the tier is **unknown**.
- **Level** is the highest tier passed, -1 if none. A level is **determined** when the top tier
  passed, or the next tier failed. A "blocked" next tier means it was never tested, so the level
  is a lower bound.
- **Passive observation** is a baseline with zero probes. It is a floor, not a real observer.
  **Confirm**: what free telemetry (normal motion, current, sensor validity) the arm produces.
  A passive baseline built on that telemetry would be a fairer comparison.

## Planner

- **Information gain** is the mutual information, in bits, between the capability level and the
  pass/fail outcome of a probe. The level is what the report shows. The cause is not targeted.
- **Risk** is the expected weighted violation score under the belief. Weights: fall 1.0,
  overload 0.5, joint limit 0.5 (`configs/planner.yaml`). **Confirm** the weights (the risk
  measure is an open choice in the brief).
- **Safety veto (all methods).** A probe is never run if its chance of causing any violation,
  under the current belief, exceeds 0.2.
- **Energy** is a proxy: the integral of |torque x velocity| plus 0.002 x torque squared, in J.
  It is not a measured quantity.
- **Utility** = information gain - risk weight x risk - energy weight x energy / 10 J. It sets
  the order of probes. It never skips an allowed probe, because a tier cannot be concluded
  without one. The planner stops when no allowed, safe probe is left, or when the budget
  (40 probes) runs out.
- **Baselines** share the gating, the budget, the veto and the belief update. They differ only
  in which allowed probe they run next: random (uniform), or fixed (tier order, then joints
  from the base outwards).

## Evaluation

- **Truth** is each joint's own capability: the level it reaches when probed alone with no
  sensor noise. It does not depend on gating.
- **Accuracy** = share of joints whose level is determined and correct. **Coverage** = share of
  joints whose level is determined. **Overclaim** = share of joints reported above their true
  level, which is the dangerous error.
