"""Single-joint simulator.

It plays two roles. The planner uses it to predict what each probe does under each damage
hypothesis. The simulated robot uses it as ground truth, with sensor noise added on top
(see episode.py). Only one joint is simulated at a time. Gating means a joint is probed only
after the joints below it pass, so the others can be treated as healthy.

Control: torque = clip(kp * (ref - q) - kd * qd, +/- limit), acting on the joint inertia.
Gravity acts only in the hold probe (T3). T0-T2 run unloaded, as the tier definitions say.
"""
import math
from dataclasses import dataclass, field

DT = 0.002  # seconds per simulation step

# The readings each probe kind produces. sensor_valid is added to every probe.
METRIC_NAMES = {
    "small_step": ("response_ratio", "peak_current_a"),
    "smooth_move": ("final_error_deg",),
    "planned_path": ("rms_error_deg",),
    "hold_under_load": ("sag_deg", "peak_torque_fraction"),
}


@dataclass
class ProbeResult:
    metrics: dict                                   # readings; NaN where there is no reading
    violations: set = field(default_factory=set)    # any of: overload, joint_limit, fall
    energy_j: float = 0.0                           # energy proxy spent before the end or abort

    @property
    def aborted(self):
        return bool(self.violations)


def _min_jerk(s):
    """Smooth 0-to-1 profile with zero speed and acceleration at both ends."""
    s = min(max(s, 0.0), 1.0)
    return 10 * s**3 - 15 * s**4 + 6 * s**5


def _reference(probe):
    """Commanded angle in rad (relative to home) as a function of time, and the probe length."""
    kind = probe["kind"]
    if kind == "small_step":
        step = math.radians(probe["step_deg"])
        return (lambda t: step), probe["duration_s"]
    if kind == "smooth_move":
        move = math.radians(probe["move_deg"])
        ramp = probe["move_s"]
        return (lambda t: move * _min_jerk(t / ramp)), probe["duration_s"]
    if kind == "planned_path":
        # Out to the amplitude and back: a planned path, not a single move.
        amp = math.radians(probe["amplitude_deg"])
        length = probe["duration_s"]

        def out_and_back(t):
            u = t / length
            return amp * _min_jerk(2 * u) if u <= 0.5 else amp * _min_jerk(2 * (1 - u))

        return out_and_back, length
    if kind == "hold_under_load":
        return (lambda t: 0.0), probe["duration_s"]
    raise ValueError(f"unknown probe kind: {kind}")


def _nan_metrics(kind, sensor_valid):
    metrics = {name: math.nan for name in METRIC_NAMES[kind]}
    metrics["sensor_valid"] = 1.0 if sensor_valid else 0.0
    return metrics


def _simulate(joint, fault, platform, ref_fn, duration, gravity):
    """Step one joint forward in time. Returns (trace, violations, energy_j)."""
    kp = joint.kp * fault.stiffness_scale
    tau_cap = joint.tau_max_nm * fault.torque_scale
    # Overload: the controller asks for more than the probe is allowed to use.
    budget = platform.probe_torque_limit_fraction * joint.tau_max_nm
    low, high = (math.radians(x) for x in joint.limits_deg)

    q = qd = energy = 0.0
    trace = []  # (ref, q, tau) per step
    violations = set()
    for i in range(round(duration / DT)):
        ref = ref_fn(i * DT)
        demand = kp * (ref - q) - joint.kd * qd
        if abs(demand) > budget:
            violations.add("overload")
            break
        if fault.locked:
            # A locked joint cannot move. Its motor pushes at full torque while it is asked to move.
            qd = 0.0
            tau = joint.tau_max_nm if demand != 0.0 else 0.0
        else:
            tau = max(-tau_cap, min(tau_cap, demand))
            qd += (tau - gravity) / joint.inertia * DT
            q += qd * DT
        energy += (abs(tau * qd) + platform.heat_coeff * tau * tau) * DT
        trace.append((ref, q, tau))
        if not low <= q <= high:
            violations.add("joint_limit")
            break
    return trace, violations, energy


def _metrics(probe, trace, joint, platform):
    kind = probe["kind"]
    refs = [r for r, _, _ in trace]
    qs = [q for _, q, _ in trace]
    taus = [abs(t) for _, _, t in trace]
    if kind == "small_step":
        step = math.radians(probe["step_deg"])
        return {
            "response_ratio": qs[-1] / step,
            "peak_current_a": max(taus) / platform.torque_constant_nm_per_a,
        }
    if kind == "smooth_move":
        return {"final_error_deg": math.degrees(abs(refs[-1] - qs[-1]))}
    if kind == "planned_path":
        errors = [r - q for r, q in zip(refs, qs)]
        rms = math.sqrt(sum(e * e for e in errors) / len(errors))
        return {"rms_error_deg": math.degrees(rms)}
    if kind == "hold_under_load":
        # Sag is measured over the last window of the hold, once the joint has settled.
        window = round(probe["sag_window_s"] / DT)
        sag = max(abs(r - q) for r, q, _ in trace[-window:])
        return {
            "sag_deg": math.degrees(sag),
            "peak_torque_fraction": max(taus) / joint.tau_max_nm,
        }
    raise ValueError(f"unknown probe kind: {kind}")


def run_probe(joint, probe, fault, platform):
    """Run one probe on one joint with one fault. Deterministic: noise is added later."""
    kind = probe["kind"]
    if not fault.sensor_valid:
        # Without an encoder reading the controller cannot close the loop, so the joint is not moved.
        return ProbeResult(metrics=_nan_metrics(kind, sensor_valid=False))

    gravity = joint.gravity_nm if kind == "hold_under_load" else 0.0
    ref_fn, duration = _reference(probe)
    trace, violations, energy = _simulate(joint, fault, platform, ref_fn, duration, gravity)
    if violations:
        return ProbeResult(metrics=_nan_metrics(kind, sensor_valid=True),
                           violations=violations, energy_j=energy)
    metrics = _metrics(probe, trace, joint, platform)
    metrics["sensor_valid"] = 1.0
    return ProbeResult(metrics=metrics, energy_j=energy)
