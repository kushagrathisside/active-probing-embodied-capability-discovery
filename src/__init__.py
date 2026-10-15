"""Active probing for embodied capability discovery: core implementation.

Modules, in the order the pipeline uses them:
  config            locate and read the YAML files in configs/
  tiers             what each tier checks and what counts as a pass
  damage            damage hypotheses and their prior
  platform_adapter  joints, chains and probes of one robot
  sim               single-joint simulator (the planner's model and the ground truth)
  outcomes          every probe simulated under every hypothesis, once per run
  belief            Bayes update and expected information gain
  gating            which tier tests are allowed now, and each tier's status
  planner           probe selection: the proposed method and the baselines
  episode           one probing run on a simulated robot with hidden damage
  report            the physical state report (uses no hidden truth)
  evaluate          compares a report with the hidden truth (evaluation only)
"""
