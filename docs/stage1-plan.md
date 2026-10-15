# Stage 1 plan: learned skills on one joint at a time

Status: **implemented and run.** Results: `results/assessment_arm6.md`, `results/comparison_learned.csv`.

## 1. Goal, in plain words

1. Simulate a damaged joint.
2. Train a small policy with reinforcement learning (RL) for each skill (T1 move, T2 path, T3 hold) on a healthy joint.
3. Run that policy on the damaged joint and watch how it does.
4. From the pattern of successes and failures, infer which damage is present, and how close each skill is to failing.

T0 (sensor and response check) stays scripted. It is a diagnostic, not a skill. It also gates everything else: a joint that fails T0 is never run on a learned skill.

Honesty note for students: a stage-1 policy is two gains per joint and skill, found by RL. That is deliberately small. It keeps the policy from compensating for the damage we want to see. Richer policies are stage 2.

## 2. What stays the same

Tier thresholds (`configs/tiers.yaml`), the Bayesian belief, chain gating, the planner and the report keep their meaning. The new layer only changes where the evidence comes from: a policy rollout instead of a scripted probe.

A policy and a scripted probe run the same skill and are judged by the same tier checks on the same metric names.

## 3. Design

### 3.1 One physics model, batched

`src/physics.py` is the only joint model. It runs a batch of joints as numpy arrays. One joint is a batch of size 1. Training scores a whole population of candidate policies in one pass.

Control rate: the servo runs at 500 Hz (2 ms). That is plausible for a joint servo loop. It is not plausible for a high-level policy. This is a stated limit (section 6).

### 3.2 Control law: pure feedback, no feedforward

The demanded torque is:

    torque = kp_mult * kp * (ref - q)  -  kd_mult * kd * qd

- `kp`, `kd` are the joint's nominal PD gains from the platform config.
- The learned parameters are the two multipliers `kp_mult`, `kd_mult`, clamped to [0.25, 4].
- There is **no** reference-velocity term, **no** gravity bias and **no** fault input.

The scripted PD controller is this same law with both multipliers equal to 1. So the scripted reference and the policy share one code path.

Why no feedforward: a feedforward term hides damage. A reference-velocity term or a gravity bias carries the load, so a loss of stiffness no longer shows.

### 3.3 Stiffness fault

A stiffness fault scales only the position-feedback term: `demand = s * stiffness_term + damping_term`. That matches a weaker position loop.

### 3.4 Training (RL by evolution strategies)

`src/training.py`, evolution strategies (ES) over the two multipliers:
- Antithetic sampling, population 32, 4 randomised instances per candidate, 40 generations.
- Randomisation: tau_max, inertia, gravity and stiffness, each within ±10%. The policy is trained on a range of healthy joints, not one.
- Input noise on the policy's own sensing: 0.05 deg on angle, 0.5 deg/s on speed.
- Reward per run: minus (primary metric / threshold)², where the primary metric is the tier's first check (final error, RMS error or sag). The reward is in units of the tier's own pass limit. Minus an effort term (mean of (demand / budget)²). Minus a large penalty if the run aborts.
- Rank-based fitness, as in standard ES.

Why ES: no heavy dependency, the update is a few lines of numpy, and each line can be explained to students. Two parameters are a small problem, so ES converges reliably. A test compares ES with a grid search on the same problem.

### 3.5 Quality gate on each trained policy

Each policy is run on 100 held-out randomised healthy joints.
- Gate: the Wilson 95% lower bound on the success rate must be at least 0.85. With 100 episodes, a policy needs about 91% observed success to pass. A policy that is truly at 0.9 passes only about half the time, so the lower bound is used, not the raw rate.
- Trusted: passes the gate. Untrusted skills give `unknown` in the report. No damage conclusion is drawn from them.

### 3.6 Assessment

Two assessors return the same `Prediction` and `Execution` shapes:
- `ScriptedAssessor`: T0 and the reference probes. Deterministic. Its noise-free readings are the reference.
- `LearnedAssessor`: T1 to T3 policies.

For each (joint, skill, damage hypothesis):
- **Model table**: 50 rollouts. Each rollout draws a randomised healthy-or-damaged plant, with input noise and reading noise. Pass probability is (passes + 1) / (50 + 2). Violation probability is the rate of each violation type.
- **Truth execution**: one rollout under the true damage, with a fresh seed. This is the robot's probe result.

Two noise sources, kept separate:
- *Input noise* sits inside the control loop (what the policy sees).
- *Reading noise* sits on the metrics (what the tier check sees), as in `configs/tiers.yaml`.
Pass probabilities from learned rollouts include both. The Gaussian likelihood in the scripted assessor uses reading noise only.

Seeds come from `numpy.random.SeedSequence` with a key per (joint, tier, hypothesis), so every stream is independent and reproducible. Training, gate, table and truth use separate base seeds.

Each assessment gives, per skill and hypothesis: success rate, the mean margin to the pass threshold (positive is inside the limit), and violation rates. The margin is the "direction" the team asked for: how far a skill is from failing.

### 3.7 Level: model, reference and truth

Three things are kept apart:
- **Model level**: highest tier in a contiguous ladder whose predicted pass probability is at least 0.5. The belief uses this.
- **Reference level**: the scripted controller's level, noise-free. It is the capability label for the hypothesis.
- **Damage truth**: the true hypothesis, from the simulator.

Evaluation reports:
1. Hypothesis identification: is the most likely hypothesis the true one? This is the damage question.
2. Level vs reference: is the robot's level right?
3. Policy gap: where the learned policy and the scripted controller disagree. That gap is the cost of learning.

### 3.8 Conclusions come from probes only

A tier is passed or failed only after a probe of that tier. Without this rule the belief produced a false pass in an earlier test. This rule still holds.

### 3.9 Scalability

- **Horizontal**: each (joint, skill) is one independent job. Training and table building run in parallel with `--workers`. More joints, robots or seeds just add jobs.
- **Vertical**: each layer has one interface.
  - Physics: a chain or whole-arm model replaces `physics.py`, behind the same `simulate` call.
  - Policy: `LinearFeedback` now. An MLP with the same `torques` method later.
  - Assessor: scripted or learned, chosen per tier in `platform_arm6.yaml`.
  - Platform: a new robot is a new YAML file.
- **No hard-coded numbers**: thresholds, gains, seeds and counts are in YAML.
- **Reproducibility**: each policy is saved as JSON with its settings, seed, gate result and training curve.

### 3.10 Layering

    physics  ->  tasks  ->  runner  ->  assessors  ->  training  ->  pipeline / outcomes  ->  planner / episode / evaluate

Lower layers never import higher ones.

### 3.11 Tests

1. Batched physics: a batch of one and a batch of several give the same trajectories.
2. Scripted probes keep their known numbers: healthy sag is gravity / kp; weak shoulder aborts on overload; locked fails T0; missing sensor never moves.
3. Zero error and zero speed give zero torque, so the policy has no gravity bias (the "cannot compensate" test).
4. Policy save and load round trip.
5. ES is deterministic for a seed and matches a grid search to within a stated tolerance on the two-gain problem.
6. The healthy gate computes the Wilson lower bound correctly.
7. A learned policy passes the healthy gate on one joint and tier.
8. Learned assessment on a missing sensor never moves the joint.
9. An untrusted skill gives `unknown` in gating, not `pass` or `fail`.
10. Planner and episode tests still pass, with the new prediction format.

### 3.12 Acceptance for the experiment

- Each trained skill is trusted, or is reported as untrusted.
- Signature table: one row per (joint, skill), one column per hypothesis, showing success rate and margin.
- Agreement: model level vs reference level, per joint and hypothesis. Reported, not forced.
- Identifiability: for each joint, the hypothesis pairs whose signatures never differ by 0.5 or more on any skill. Those pairs are listed as not separable with these skills.
- Identifiability is checked first on the scripted controller, before any learned policy is used.

## 4. What changes in the code

| Area | Change |
|---|---|
| `src/sim.py` | Removed. Replaced by `physics.py` (batched), `tasks.py` (skills), `runner.py` (run one skill), `policies.py` (control law and storage). |
| `src/assessors.py` (new) | `ScriptedAssessor`, `LearnedAssessor`, shared `Prediction` and `Execution`. |
| `src/training.py` (new) | ES trainer, healthy gate, Wilson bound. |
| `src/pipeline.py` (new) | Wires assessors from the platform config and the policy store. |
| `src/outcomes.py` | Builds model table from assessors, reference levels from the scripted controller, and trust flags. |
| `src/planner.py` | `Prediction` has violation probabilities. Risk uses them. |
| `src/gating.py` | Untrusted skills give `unknown`. |
| `src/episode.py` | Truth is an assessor's execution under the true damage. |
| `src/evaluate.py` | Hypothesis identification, level vs reference, policy gap. |
| `src/tiers.py` | Vector pass and margin functions. |
| `configs/training.yaml` (new) | ES, randomisation, noise, gate, table size, seeds, identifiability gap. |
| `configs/platform_arm6.yaml` | `assessment:` section, which assessor each tier uses. |
| `experiments/train_policies.py` (new) | Trains every learned (joint, skill) in parallel and gates it. |
| `experiments/assess_policies.py` (new) | Signature table, agreement, identifiability. |
| `experiments/run_episode.py`, `compare_methods.py` | Use the pipeline. |
| `requirements.txt` | Adds numpy. |

## 5. Plain-language steps for students

1. `train_policies`: teach each skill to a healthy joint, by trial and error.
2. Check the healthy gate: a policy has to work on a healthy joint before it is trusted.
3. `assess_policies`: run each trusted policy on each damage case.
4. Read the signature table: which skill fails under which damage, and how close the others are to failing.
5. Compare with the reference controller: where does the learned policy fall short?

## 6. Robotics review: decisions

A robotics review (a Haiku subagent acting as a hardware researcher) was run on the first draft. Each point was checked against the code before deciding.

| Point | Decision |
|---|---|
| Locked joint "gets an overload abort on T3" | **Corrected.** At home a locked joint has zero demand, so it holds with no sag and passes T3 if run. It never reaches T3, because T0 fails and gates it. The ladder gives level -1. |
| Policy "no feedforward" but had a reference-velocity term | **Accepted.** Policy is pure feedback on error and speed. Scripted PD is now the same law, so the PD-equivalence test is exact. |
| Reward units | **Accepted.** Reward is (metric / threshold)². |
| Truth = PD level is controller performance, not damage | **Accepted.** Damage truth is the true hypothesis. Reference level is kept separately, as the capability label. |
| Budget vs clip (weak motors saturate between 0.4 and 0.5 tau_max) | **Kept by design.** A weak motor saturates before the overload limit. Documented. |
| T3 measures kp × gravity; gravity compensation would hide stiffness loss | **Accepted as a stated limit.** These tests assume an uncompensated joint, which is the stage-1 controller. A compensated robot needs a stiffness probe at several poses. Listed as a hardware item. |
| gravity_nm is one number at one hold pose | **Accepted as a stated limit.** Multi-pose is stage 2. |
| Friction is missing | **Accepted.** Robustness run in stage 1b. Not in the first physics. |
| No latency; velocity from a differenced encoder | **Accepted as a limit.** Stage 1 adds simulated noise to speed. A filtered velocity estimate is a hardware requirement. |
| Weak motor is a hard clip; a demagnetised motor has lower Kt and more current per Nm | **Accepted as a limit.** The current check understates a weak motor. Recorded as a future hypothesis. |
| Abort must mean drive disable and brake, not a torque cut (a shoulder drops under gravity) | **Accepted as a hardware precondition.** Stage 1 is simulation only. |
| Sign-flipped or offset encoder can turn the loop into positive feedback | **Accepted as a hardware precondition.** A low-torque direction check comes before any learned run on hardware. Not modelled in stage 1. |
| "Penalised" over-budget requests are not a limit | **Accepted.** Gains are clamped to [0.25, 4]. Torque is capped by the plant. Overload is a hard abort, not a penalty. |
| Weak elbow and wrists are not separable | **Accepted as a finding.** The identifiability check will list them. |
| Locked vs a sluggish policy (both fail T1 or T2) | **Accepted as a known confusion.** The healthy gate and margins reduce it. |
| Noise counted twice | **Clarified.** Reading noise and input noise are separate sources (section 3.6). |
| ES is overkill for two parameters; use a grid | **Partly rejected.** ES stays, because RL is the goal. A grid search is a test of whether ES finds the optimum. |
| No test that the policy cannot see the fault | **Accepted.** Test 3 in 3.11. |
| No test for locked on learned gains | **Accepted.** Locked is gated by T0. A test checks that no learned run happens on a locked joint. |
| Gate of 20 rollouts is too noisy | **Accepted.** 100 gate episodes, Wilson lower bound. |
| Model table randomised or not? | **Decided:** randomised, so each pass probability is a distribution over plants, not one number. |
| Identifiability threshold so "not forced" can fail | **Accepted.** A pair is separable if some skill differs by at least 0.5. |

## 7. Out of stage 1

- A whole-arm environment (the joints do not interact yet).
- An MLP policy and PPO.
- Friction, backlash, latency, Kt-based weak motors (stage 1b or stage 2).
- Multi-pose gravity and a compensated-joint stiffness probe.
- Shared-damage belief (RQ3, second half).
- Quadruped and humanoid platforms.

## 8. Open questions for the TA

1. Keep the policy linear for the whole project, or move to an MLP after stage 1?
2. Is the scripted PD the right reference, or should a stronger search give the best achievable performance?
3. Is a Wilson lower bound of 0.85 the right gate?
4. Should T0 also be learned, or stay scripted?
5. For a real robot with gravity compensation, which probe replaces T3?
