"""Simulate every probe on every joint under every damage hypothesis, once per run.

This table is the planner's model of the robot. For each probe it gives the predicted readings,
violations and energy under each hypothesis. The planner uses these for the Bayesian update
(pass probability) and for choosing probes (risk and energy).
"""
from dataclasses import dataclass

from .platform_adapter import usable_tiers
from .sim import run_probe


@dataclass(frozen=True)
class Prediction:
    metrics: dict         # noise-free readings
    violations: frozenset
    energy_j: float
    pass_prob: float      # chance the tier passes, noise included. 0 if the probe aborts.


@dataclass
class Table:
    predictions: dict     # (joint, tier, hypothesis) -> Prediction
    levels: dict          # joint -> {hypothesis: level}; highest tier passed noise-free, -1 = none

    def get(self, joint, tier, hypothesis):
        return self.predictions[(joint, tier, hypothesis)]


def build_table(platform, tiers, damage):
    usable = usable_tiers(platform, tiers)
    predictions = {}
    levels = {}
    for joint in platform.joints:
        levels[joint.name] = {}
        for h in damage.names:
            level = -1
            ladder_open = True  # stays True while every tier so far has passed
            for index, tier in enumerate(usable):
                result = run_probe(joint, platform.probes[tier.name], damage.faults[h], platform)
                passed = not result.aborted and tier.passes(result.metrics)
                predictions[(joint.name, tier.name, h)] = Prediction(
                    metrics=result.metrics,
                    violations=frozenset(result.violations),
                    energy_j=result.energy_j,
                    pass_prob=0.0 if result.aborted else tier.pass_probability(result.metrics),
                )
                # Every tier is simulated (the planner needs all of them). The level only counts
                # tiers reached without a break in the ladder.
                if ladder_open and passed:
                    level = index
                else:
                    ladder_open = False
            levels[joint.name][h] = level
    return Table(predictions=predictions, levels=levels)
