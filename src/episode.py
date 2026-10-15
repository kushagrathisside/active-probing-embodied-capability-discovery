"""One probing episode: a simulated robot with hidden damage, probed by one method.

Random streams are kept separate, so every method sees the same damage for the same seed:
  seed       -> the true damage (python random)
  seed + 1   -> the robot's own rollouts: plant randomisation and noise (numpy)
  seed + 2   -> the random baseline's choices (python random)
"""
import random
from dataclasses import dataclass

import numpy as np

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
    true_states: dict         # joint -> hypothesis actually present. For evaluation only.
    reference_levels: dict    # joint -> {hypothesis: reference level}. For evaluation only.
    method: str
    seed: int
    budget: int


class SimulatedRobot:
    """Hidden damage, run through the assessors. The planner only sees the results of its probes."""

    def __init__(self, platform, tiers, assessors, damage, damage_rng, rollout_rng, joint_names):
        self.platform = platform
        self.tiers = tiers
        self.assessors = assessors
        self.rollout_rng = rollout_rng
        self.true_states = {name: sample_fault_name(damage, damage_rng) for name in joint_names}
        self.faults = damage.faults

    def run(self, joint_name, ti):
        tier = self.tiers[ti]
        fault = self.faults[self.true_states[joint_name]]
        assessor = self.assessors[tier.name]
        return assessor.execute(self.platform.joint(joint_name), tier, fault, self.rollout_rng)


def run_episode(platform, tiers, damage, table, method, cfg, seed):
    usable = usable_tiers(platform, tiers)
    names = tuple(j.name for j in platform.joints)
    tier_index = {t.name: i for i, t in enumerate(usable)}
    untrusted = frozenset(
        (joint, tier_index[tier])
        for (joint, tier), trusted in table.trusted.items()
        if not trusted and tier in tier_index
    )
    robot = SimulatedRobot(platform, usable, table.assessors, damage,
                           damage_rng=random.Random(seed),
                           rollout_rng=np.random.default_rng(seed + 1),
                           joint_names=names)
    policy_rng = random.Random(seed + 2)

    state = State(
        joint_names=names,
        proximal={n: platform.proximal(n) for n in names},
        tiers=usable,
        levels={n: table.levels[n] for n in names},
        beliefs={n: dict(damage.prior) for n in names},
        gating=cfg.gating,
        confidence=cfg.pass_confidence,
        max_repeats=cfg.max_repeats,
        untrusted=untrusted,
    )

    log = []
    for step in range(cfg.budget):
        candidates = [(n, ti) for n in names for ti in range(len(usable))
                      if state.status(n, ti) == "ready"]
        choice = choose(method, state, candidates, table, cfg, policy_rng)
        if choice is None:
            break
        joint, ti = choice
        execution = robot.run(joint, ti)
        state.probe_counts[(joint, ti)] = state.probe_counts.get((joint, ti), 0) + 1

        tier = usable[ti]
        pass_prob = {h: table.get(joint, tier.name, h).pass_prob for h in state.beliefs[joint]}
        state.beliefs[joint] = update(state.beliefs[joint], pass_prob, execution.passed, cfg.likelihood_floor)
        log.append(ProbeRecord(
            step=step, joint=joint, tier=tier.name, passed=execution.passed,
            aborted=bool(execution.violations), violations=tuple(sorted(execution.violations)),
            energy_j=execution.energy_j,
        ))

    return Episode(state=state, log=log, true_states=robot.true_states,
                   reference_levels=table.reference_levels,
                   method=method, seed=seed, budget=cfg.budget)
