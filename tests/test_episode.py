"""End-to-end episodes on the real arm6 platform."""
import dataclasses
import json
import random

from src.damage import sample_fault_name
from src.episode import run_episode
from src.planner import METHODS, load_planner_config
from src.report import build_report


def true_states(damage, seed, joint_names):
    # Same draw as SimulatedRobot, so these are the states an episode with this seed will use.
    rng = random.Random(seed)
    return {name: sample_fault_name(damage, rng) for name in joint_names}


def first_seed_where(damage, joint_names, predicate):
    return next(s for s in range(1000) if predicate(true_states(damage, s, joint_names)))


def test_healthy_arm_reaches_the_top_tier_on_every_joint(arm):
    platform, tiers, damage, table = arm
    names = [j.name for j in platform.joints]
    seed = first_seed_where(damage, names, lambda st: all(h == "healthy" for h in st.values()))
    episode = run_episode(platform, tiers, damage, table, "planner", load_planner_config(), seed)
    report = build_report(platform, episode)
    assert all(p["level"] == 3 and p["determined"] for p in report["parts"])
    assert report["aborted_probes"] == 0


def test_a_locked_base_blocks_every_joint_above_it(arm):
    platform, tiers, damage, table = arm
    names = [j.name for j in platform.joints]
    seed = first_seed_where(damage, names, lambda st: st["base"] == "locked")
    episode = run_episode(platform, tiers, damage, table, "planner", load_planner_config(), seed)
    report = build_report(platform, episode)

    base, rest = report["parts"][0], report["parts"][1:]
    assert base["joint"] == "base" and base["level"] == -1 and base["determined"]
    for part in rest:
        assert part["tiers"]["T0"] == "blocked"   # chain gating: the base failed T0
        assert part["probes"] == 0                # so nothing above it was probed


def test_every_method_stays_within_the_budget_and_gives_a_serialisable_report(arm):
    platform, tiers, damage, table = arm
    cfg = dataclasses.replace(load_planner_config(), budget=12)
    for method in METHODS:
        episode = run_episode(platform, tiers, damage, table, method, cfg, seed=3)
        assert len(episode.log) <= 12
        json.dumps(build_report(platform, episode))


def test_passive_observer_runs_no_probes(arm):
    platform, tiers, damage, table = arm
    episode = run_episode(platform, tiers, damage, table, "passive", load_planner_config(), seed=3)
    assert episode.log == []


def test_same_seed_and_method_give_the_same_report(arm):
    platform, tiers, damage, table = arm
    cfg = load_planner_config()
    a = build_report(platform, run_episode(platform, tiers, damage, table, "random", cfg, seed=7))
    b = build_report(platform, run_episode(platform, tiers, damage, table, "random", cfg, seed=7))
    assert a == b
