"""Tier definitions: the metrics each tier checks and what counts as a pass.

The numbers live in configs/tiers.yaml. This module only applies them.
"""
import math
from dataclasses import dataclass

from .config import config_path, read_yaml


def normal_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


@dataclass(frozen=True)
class Check:
    metric: str
    direction: str       # "min": reading must be >= threshold. "max": reading must be <= threshold.
    threshold: float
    noise_sigma: float   # sensor noise on this reading

    def passes(self, reading):
        # NaN means the probe gave no usable reading (e.g. missing sensor). That is a fail.
        if math.isnan(reading):
            return False
        if self.direction == "min":
            return reading >= self.threshold
        return reading <= self.threshold

    def pass_probability(self, predicted):
        """Chance the noisy reading passes, if the noise-free reading would be `predicted`."""
        if math.isnan(predicted):
            return 0.0
        if self.direction == "min":
            margin = predicted - self.threshold
        else:
            margin = self.threshold - predicted
        if self.noise_sigma == 0.0:
            return 1.0 if margin >= 0.0 else 0.0
        return normal_cdf(margin / self.noise_sigma)


@dataclass(frozen=True)
class Tier:
    name: str    # "T0" ...
    label: str   # "Alive" ...
    checks: tuple

    def passes(self, metrics):
        # A tier passes only if every check passes.
        return all(c.passes(metrics[c.metric]) for c in self.checks)

    def pass_probability(self, metrics):
        # Checks use independent noise, so their pass chances multiply.
        p = 1.0
        for c in self.checks:
            p *= c.pass_probability(metrics[c.metric])
        return p


def load_tiers(path=None):
    raw = read_yaml(path or config_path("tiers.yaml"))["tiers"]
    return [
        Tier(name=name, label=spec["name"], checks=tuple(Check(**c) for c in spec["checks"]))
        for name, spec in raw.items()
    ]
