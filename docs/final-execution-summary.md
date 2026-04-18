# Final Execution Summary — LAFAN1 Config Refresh

## What was completed

This branch finished the planned LAFAN1 config-refresh workflow on a clean worktree from `master`.

Completed work:

1. Built `ik_configs_refined/` as the first-pass refreshed config set
2. Added `ik_configs_selected/` as the final fail-closed selected set
3. Implemented reproducible generation / validation scripts
4. Ran baseline vs refined validation across the current robot set for `dance1_subject1`
5. Ran representative profile tuning for single-stage and two-stage robots
6. Chose final selected configs conservatively: only proven improvements switched
7. Added `params.py` support for `bvh_lafan1_refined` and `bvh_lafan1_selected`
8. Verified that `bvh_lafan1_selected` can instantiate GMR successfully for both:
   - a robot that truly uses a refined config (`unitree_g1_23dof`)
   - a robot whose selected config intentionally falls back to baseline (`booster_k1`)
9. Removed stale worktree-bound absolute paths from the generated manifests and vendored the `unitree_g1_23dof` special seed so the selected/refined manifests remain portable inside the repository
10. Ran final release-readiness audits:
   - `logs/lafan1_config_refresh_validation/selected_integrity_audit.json`
   - `logs/lafan1_config_refresh_validation/selected_smoke_all.json`

## Final decision summary

### Selected/refined
- `berkeley_humanoid_lite`
- `openloong`
- `pnd_adam_lite`
- `unitree_g1_23dof`
- `unitree_g1_29dof`

### Baseline retained
- `booster_k1`
- `booster_t1`
- `booster_t1_29dof`
- `engineai_pm01`
- `fourier_gr3`
- `fourier_n1`
- `hightorque_hi`
- `kuavo_s45`
- `pal_talos`
- `stanford_toddy`
- `tienkung`
- `unitree_h1`
- `unitree_h1_2`

### Blocked
- `agibot_a2` — missing mesh asset in current environment

## Canonical outputs

- `general_motion_retargeting/ik_configs_refined/manifest.json`
- `general_motion_retargeting/ik_configs_selected/manifest.json`
- `logs/lafan1_config_refresh_validation/summary.md`
- `logs/lafan1_config_refresh_validation/final_selection.md`
- `docs/lafan1-config-refresh.md`
- `docs/lafan1-config-refresh-summary.md`

## Notes

- This branch is intentionally fail-closed. It does **not** force a broad template across all robots.
- Two-stage generic template transfer did not generalize well; only robot-specific or proven-safe cases were promoted.
- The selected config set is the intended surface for later large-scale processing.
