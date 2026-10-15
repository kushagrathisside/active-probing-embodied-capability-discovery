"""Compare a physical state report with the hidden truth. Evaluation only.

The planner and the report never see the true damage. Three checks, kept separate:
  hypothesis_accuracy  is the most likely damage state the true one? (the damage question)
  accuracy / overclaim the reported level against the reference level (the scripted controller's)
  coverage             how many joints got a determined level at all
"""


def score_episode(report, episode):
    rows = []
    hypothesis_hits = 0
    for part in report["parts"]:
        joint = part["joint"]
        truth = episode.true_states[joint]
        reference = episode.reference_levels[joint][truth]
        rows.append((part["level"], part["determined"], reference))
        hypothesis_hits += part["most_likely_state"] == truth
    n = len(rows)
    return {
        "coverage": sum(det for _, det, _ in rows) / n,
        "accuracy": sum(det and lvl == ref for lvl, det, ref in rows) / n,
        "overclaim": sum(lvl > ref for lvl, _, ref in rows) / n,
        "hypothesis_accuracy": hypothesis_hits / n,
        "probes": report["probes_used"],
        "aborts": report["aborted_probes"],
        "energy_j": report["energy_j"],
    }
