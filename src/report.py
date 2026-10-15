"""Physical state report: what each joint can do, and the evidence for it.

It is built only from the probe results and the beliefs. It never reads the true damage.
"""
import json
import os
from dataclasses import asdict


def _label(status):
    # Anything still open when the episode ends is reported as unknown.
    return status if status in ("pass", "fail", "blocked") else "unknown"


def build_report(platform, episode):
    state = episode.state
    top = len(state.tiers) - 1
    parts = []
    for name in state.joint_names:
        labels = [_label(state.status(name, ti)) for ti in range(len(state.tiers))]

        # Level = highest tier passed, with no gap below it. -1 means even T0 did not pass.
        level = -1
        for ti, label in enumerate(labels):
            if label != "pass":
                break
            level = ti
        # The level is determined when every tier passed, or when the next tier actually failed.
        # A "blocked" next tier means it was never tested, so the level is only a lower bound.
        determined = level == top or (level < top and labels[level + 1] == "fail")

        belief = state.beliefs[name]
        likely = max(belief, key=belief.get)
        parts.append({
            "joint": name,
            "chain": platform.joint(name).chain,
            "level": level,
            "determined": determined,
            "tiers": {tier.name: label for tier, label in zip(state.tiers, labels)},
            "most_likely_state": likely,
            "probability": round(belief[likely], 3),
            "probes": sum(n for (j, _), n in state.probe_counts.items() if j == name),
        })

    return {
        "platform": platform.name,
        "method": episode.method,
        "seed": episode.seed,
        "budget": episode.budget,
        "probes_used": len(episode.log),
        "aborted_probes": sum(r.aborted for r in episode.log),
        "energy_j": round(sum(r.energy_j for r in episode.log), 2),
        "parts": parts,
        "probe_log": [asdict(r) for r in episode.log],
    }


def to_markdown(report):
    tier_names = list(report["parts"][0]["tiers"])
    lines = [
        f"# Physical state report: {report['platform']}",
        "",
        f"Method: {report['method']}, seed {report['seed']}. "
        f"Probes used: {report['probes_used']} of {report['budget']}. "
        f"Aborted probes: {report['aborted_probes']}. Energy proxy: {report['energy_j']} J.",
        "",
        "Level is the highest tier passed (-1 = none). `(lower bound)` means the tier above was not "
        "tested, so the level may be higher. `not determined` means nothing is known about the joint yet.",
        "",
        "| Part | Chain | Level | " + " | ".join(tier_names) + " | Most likely state | Probes |",
        "|" + "---|" * (len(tier_names) + 5),
    ]
    for p in report["parts"]:
        if p["determined"]:
            level = str(p["level"])
        elif p["level"] >= 0:
            level = f"{p['level']} (lower bound)"
        else:
            level = "not determined"
        tiers = " | ".join(p["tiers"][t] for t in tier_names)
        likely = f"{p['most_likely_state']} ({p['probability']})"
        lines.append(f"| {p['joint']} | {p['chain']} | {level} | {tiers} | {likely} | {p['probes']} |")
    return "\n".join(lines) + "\n"


def write_report(report, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "report.md"), "w") as f:
        f.write(to_markdown(report))
    with open(os.path.join(out_dir, "report.json"), "w") as f:
        json.dump(report, f, indent=2)
