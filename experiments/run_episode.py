"""Run one probing episode and write its physical state report.

    python -m experiments.run_episode --method planner --seed 1

Writes results/episode_<method>_seed<seed>/report.md and report.json, and prints the report.
The evaluation line at the end uses the hidden truth. The report itself does not.
"""
import argparse
import dataclasses
import os

from src.config import REPO_ROOT
from src.damage import load_damage
from src.episode import run_episode
from src.evaluate import score_episode
from src.outcomes import build_table
from src.planner import METHODS, load_planner_config
from src.platform_adapter import load_platform
from src.report import build_report, to_markdown, write_report
from src.tiers import load_tiers


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--method", choices=METHODS, default="planner")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--budget", type=int, default=None, help="overrides configs/planner.yaml")
    parser.add_argument("--out", default=None, help="output directory (default: results/episode_...)")
    args = parser.parse_args()

    platform = load_platform()
    tiers = load_tiers()
    damage = load_damage()
    cfg = load_planner_config()
    if args.budget is not None:
        cfg = dataclasses.replace(cfg, budget=args.budget)

    table = build_table(platform, tiers, damage)
    episode = run_episode(platform, tiers, damage, table, args.method, cfg, args.seed)
    report = build_report(platform, episode)

    out_dir = args.out or os.path.join(REPO_ROOT, "results", f"episode_{args.method}_seed{args.seed}")
    write_report(report, out_dir)
    print(to_markdown(report))

    score = score_episode(report, episode)
    print("Evaluation against hidden truth (not part of the report):")
    print(f"  coverage {score['coverage']:.2f}  accuracy {score['accuracy']:.2f}  "
          f"overclaim {score['overclaim']:.2f}  probes {score['probes']}  aborts {score['aborts']}")
    print("  true states:", ", ".join(f"{j}={h}" for j, h in episode.true_states.items()))
    print(f"Wrote {os.path.relpath(out_dir, REPO_ROOT)}/report.md and report.json")


if __name__ == "__main__":
    main()
