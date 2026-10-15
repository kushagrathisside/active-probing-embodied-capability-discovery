"""Checks that the simulator produces the fault signatures the design expects.

The expected level map (see docs/design-decisions.md):
  healthy -> 3 on every joint, locked -> -1, missing_sensor -> -1,
  weak_motor -> 2 on the shoulder only (the only joint whose load exceeds its reduced torque),
  broken_link -> 1 on every joint.
"""
import math

from src.damage import load_damage
from src.sim import run_probe


def test_healthy_arm_reaches_top_tier_on_every_joint(arm):
    _, _, damage, table = arm
    assert all(table.levels[j]["healthy"] == 3 for j in table.levels)


def test_locked_joint_fails_T0(arm):
    platform, tiers, _, table = arm
    assert table.levels["shoulder"]["locked"] == -1
    pred = table.get("shoulder", "T0", "locked")
    assert pred.pass_prob == 0.0


def test_missing_sensor_is_never_moved_and_fails_T0(arm):
    platform, _, damage, table = arm
    result = run_probe(platform.joint("elbow"), platform.probes["T0"],
                       damage.faults["missing_sensor"], platform)
    assert result.metrics["sensor_valid"] == 0.0
    assert result.energy_j == 0.0          # no motion, so no energy
    assert not result.violations
    assert table.levels["elbow"]["missing_sensor"] == -1


def test_weak_shoulder_is_overloaded_while_holding_its_load(arm):
    # 40% torque cannot hold the shoulder's 25 N*m load. The controller asks for more than the probe
    # allows, so the probe aborts. That abort is the overload risk, and it counts as a fail.
    _, _, _, table = arm
    pred = table.get("shoulder", "T3", "weak_motor")
    assert pred.violations == frozenset({"overload"})
    assert pred.pass_prob == 0.0
    assert table.levels["shoulder"]["weak_motor"] == 2


def test_weak_motor_on_unloaded_base_passes_everything(arm):
    _, _, _, table = arm
    assert table.levels["base"]["weak_motor"] == 3


def test_broken_link_fails_path_tracking_on_every_joint(arm):
    _, _, _, table = arm
    assert all(table.levels[j]["broken_link"] == 1 for j in table.levels)
    assert all(table.get(j, "T2", "broken_link").pass_prob == 0.0 for j in table.levels)


def test_hold_under_load_sags_by_gravity_over_stiffness(arm):
    # Healthy shoulder: sag = gravity / kp = 25 / 1500 rad, which is about 0.955 degrees.
    _, _, _, table = arm
    sag = table.get("shoulder", "T3", "healthy").metrics["sag_deg"]
    assert math.isclose(sag, math.degrees(25.0 / 1500.0), rel_tol=0.05)


def test_probes_are_deterministic(arm):
    platform, _, damage, _ = arm
    probe = platform.probes["T2"]
    a = run_probe(platform.joint("wrist_2"), probe, damage.faults["broken_link"], platform)
    b = run_probe(platform.joint("wrist_2"), probe, damage.faults["broken_link"], platform)
    assert a.metrics == b.metrics and a.energy_j == b.energy_j


def test_moves_spend_energy(arm):
    platform, _, damage, _ = arm
    result = run_probe(platform.joint("shoulder"), platform.probes["T1"],
                       damage.faults["healthy"], platform)
    assert result.energy_j > 0.0


def test_damage_model_prior_sums_to_one():
    damage = load_damage()
    assert math.isclose(sum(damage.prior.values()), 1.0)
