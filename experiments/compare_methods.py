"""Compare the probing methods over many simulated damage cases.

    python -m experiments.compare_methods --seeds 200 --budgets 6 9 12 18 24 40
    python -m experiments.compare_methods --risk-weights 0 0.25 1 4        # RQ2 sweep
    python -m experiments.compare_methods --gating robot                   # RQ3 baseline

Each row is one method at one budget, averaged over the seeds. Writes results/comparison.csv (or --out).
The same seeds are used for every method, so each method faces the same damage.
"""
import argparse
import csv
import dataclasses
import os
import statistics

from src.config import REPO_ROOT
from src.damage import load_damage
from src.episode import run_episode
from src.evaluate import score_episode
from src.outcomes import build_table
from src.planner import load_planner_config
from src.platform_adapter import load_platform
from src.report import build_report
from src.tiers import load_tiers

METRICS = ("coverage", "accuracy", "overclaim", "probes", "aborts", "energy_j")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seeds", type=int, default=200)
    parser.add_argument("--budgets", type=int, nargs="+", default=[6, 9, 12, 18, 24, 40])
    parser.add_argument("--risk-weights", type=float, nargs="+", default=[1.0],
                        help="planner risk weights to run (RQ2)")
    parser.add_argument("--gating", choices=["chain", "robot"], default=None,
                        help="override configs/planner.yaml (RQ3)")
    parser.add_argument("--out", default=os.path.join(REPO_ROOT, "results", "comparison.csv"))
    args = parser.parse_args()

    platform = load_platform()
    tiers = load_tiers()
    damage = load_damage()
    base_cfg = load_planner_config()
    if args.gating:
        base_cfg = dataclasses.replace(base_cfg, gating=args.gating)
    table = build_table(platform, tiers, damage)

    methods = [(f"planner(risk={w:g})", "planner", dataclasses.replace(base_cfg, risk_weight=w))
               for w in args.risk_weights]
    methods += [(m, m, base_cfg) for m in ("random", "fixed", "passive")]

    rows = []
    for budget in args.budgets:
        for label, method, cfg in methods:
            cfg = dataclasses.replace(cfg, budget=budget)
            scores = []
            for seed in range(args.seeds):
                episode = run_episode(platform, tiers, damage, table, method, cfg, seed)
                scores.append(score_episode(build_report(platform, episode), episode))
            row = {"method": label, "gating": cfg.gating, "budget": budget}
            for metric in METRICS:
                row[metric] = statistics.fmean(s[metric] for s in scores)
            rows.append(row)

    print(f"{'method':22s} {'gating':6s} {'budget':>6s} {'coverage':>9s} {'accuracy':>9s} "
          f"{'overclaim':>9s} {'probes':>7s} {'aborts':>7s} {'energy_j':>9s}")
    for r in rows:
        print(f"{r['method']:22s} {r['gating']:6s} {r['budget']:6d} {r['coverage']:9.3f} "
              f"{r['accuracy']:9.3f} {r['overclaim']:9.3f} {r['probes']:7.2f} "
              f"{r['aborts']:7.3f} {r['energy_j']:9.2f}")

    out_path = args.out
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["method", "gating", "budget", *METRICS])
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nWrote {os.path.relpath(out_path, REPO_ROOT)} ({args.seeds} seeds per row)")


if __name__ == "__main__":
    main()
