"""Compare a physical state report with the hidden truth.

Evaluation only. The planner and the report never see the true damage.
The truth is the joint's own capability: the level it would reach if probed alone, noise-free.
"""


def score_episode(report, episode):
    rows = []
    for part in report["parts"]:
        truth = episode.state.levels[part["joint"]][episode.true_states[part["joint"]]]
        rows.append((part["level"], part["determined"], truth))
    n = len(rows)
    return {
        # Share of joints whose level was actually determined by probing.
        "coverage": sum(det for _, det, _ in rows) / n,
        # Share of joints with the right level and a determined level.
        "accuracy": sum(det and lvl == truth for lvl, det, truth in rows) / n,
        # Share of joints reported above their true level: claiming capability that is not there.
        "overclaim": sum(lvl > truth for lvl, _, truth in rows) / n,
        "probes": report["probes_used"],
        "aborts": report["aborted_probes"],
        "energy_j": report["energy_j"],
    }
