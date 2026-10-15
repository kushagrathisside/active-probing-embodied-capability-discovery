"""One probing episode: a simulated robot with hidden damage, probed by one method.

Random streams are kept separate, so every method sees the same damage for the same seed:
  seed       -> the true damage
  seed + 1   -> sensor noise
  seed + 2   -> the random baseline's choices
"""
import math
import random
from dataclasses import dataclass, field

from .belief import update
from .damage import sample_fault_name
from .gating import State
from .planner import choose
from .platform_adapter import usable_tiers


@dataclass
class ProbeRecord:
    step: int
    joint: str
    tier: str
    passed: bool
    aborted: bool
    violations: tuple
    energy_j: float


@dataclass
class Episode:
    state: State
    log: list
    true_states: dict     # joint -> hypothesis actually present. For evaluation only.
    method: str
    seed: int
    budget: int


class SimulatedRobot:
    """Hidden damage plus sensor noise. The planner only sees the results of its probes."""

    def __init__(self, tiers, damage, table, damage_rng, noise_rng, joint_names):
        self.tiers = tiers
        self.table = table
        self.noise_rng = noise_rng
        self.true_states = {name: sample_fault_name(damage, damage_rng) for name in joint_names}

    def run(self, joint, ti):
        tier = self.tiers[ti]
        pred = self.table.get(joint, tier.name, self.true_states[joint])
        if pred.violations:
            # The probe was stopped by a safety limit. That is a fail.
            return False, pred
        readings = dict(pred.metrics)
        for c in tier.checks:
            if c.noise_sigma > 0.0 and not math.isnan(readings[c.metric]):
                readings[c.metric] += self.noise_rng.gauss(0.0, c.noise_sigma)
        return tier.passes(readings), pred


def run_episode(platform, tiers, damage, table, method, cfg, seed):
    usable = usable_tiers(platform, tiers)
    names = tuple(j.name for j in platform.joints)
    damage_rng = random.Random(seed)
    policy_rng = random.Random(seed + 2)
    robot = SimulatedRobot(usable, damage, table, damage_rng, random.Random(seed + 1), names)

    state = State(
        joint_names=names,
        proximal={n: platform.proximal(n) for n in names},
        tiers=usable,
        levels={n: table.levels[n] for n in names},
        beliefs={n: dict(damage.prior) for n in names},
        gating=cfg.gating,
        confidence=cfg.pass_confidence,
        max_repeats=cfg.max_repeats,
    )

    log = []
    for step in range(cfg.budget):
        candidates = [(n, ti) for n in names for ti in range(len(usable))
                      if state.status(n, ti) == "ready"]
        choice = choose(method, state, candidates, table, cfg, policy_rng)
        if choice is None:
            break
        joint, ti = choice
        passed, pred = robot.run(joint, ti)
        state.probe_counts[(joint, ti)] = state.probe_counts.get((joint, ti), 0) + 1

        tier = usable[ti]
        pass_prob = {h: table.get(joint, tier.name, h).pass_prob for h in state.beliefs[joint]}
        state.beliefs[joint] = update(state.beliefs[joint], pass_prob, passed, cfg.likelihood_floor)
        log.append(ProbeRecord(
            step=step, joint=joint, tier=tier.name, passed=passed,
            aborted=bool(pred.violations), violations=tuple(sorted(pred.violations)),
            energy_j=pred.energy_j,
        ))

    return Episode(state=state, log=log, true_states=robot.true_states,
                   method=method, seed=seed, budget=cfg.budget)
