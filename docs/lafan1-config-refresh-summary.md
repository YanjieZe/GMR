# LAFAN1 Config Refresh — Summary

## Scope

This branch refreshes `bvh_lafan1` IK configs for all currently involved robots on the common validation motion:

- `dance1_subject1`

Workflow executed:

1. Generate refined configs under `general_motion_retargeting/ik_configs_refined/`
2. Run baseline vs refined validation on all available robots
3. Tune representative robot profiles for single-stage / two-stage groups
4. Select only the configs that demonstrated improvement or were explicitly validated as better (`fail-closed`)
5. Materialize the final chosen configs under `general_motion_retargeting/ik_configs_selected/`

## Key branch outputs

### Config folders

- `general_motion_retargeting/ik_configs_refined/`
- `general_motion_retargeting/ik_configs_selected/`

### Scripts

- `scripts/run_headless_retarget_with_config.py`
- `scripts/generate_refined_lafan1_configs.py`
- `scripts/validate_lafan1_refined_configs.py`
- `scripts/generate_selected_lafan1_configs.py`
- `scripts/generate_profile_tuning_v2.py`
- `scripts/generate_profile_tuning_v3.py`

### Main reports

- `logs/lafan1_config_refresh_validation/summary.md`
- `logs/lafan1_config_refresh_validation/final_selection.md`
- `logs/profile_tuning_v2/representative_summary.md`
- `logs/profile_tuning_v3/representative_summary.md`

## Final selection result

### Selected refined configs

- `berkeley_humanoid_lite`
- `openloong`
- `pnd_adam_lite`
- `unitree_g1_23dof`
- `unitree_g1_29dof`

### Kept baseline configs

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

### Blocked in current environment

- `agibot_a2`
  - missing mesh asset in current environment

## Config philosophy conclusions

### Single-stage robots

A balanced single-stage refresh template can improve some robots.
It notably helped:

- `berkeley_humanoid_lite`
- `openloong`
- `pnd_adam_lite`

The `single_stage.mid` profile was chosen as the best representative level.

### Two-stage robots

Broadly applying the new two-stage philosophy as a generic template did **not** generalize well.
Even after making the templates more conservative, representative validation still showed strong regressions.
Therefore, the branch uses a fail-closed policy:

- do not switch two-stage robots to new generic templates unless they were specifically validated

### Special robots

- `unitree_g1_23dof` uses the explicitly validated tuned config based on the `elbow30_wrist20` result
- `unitree_g1_29dof` uses the conservative refined config that showed positive validation

## How to use

This branch patches `general_motion_retargeting/params.py` so that two optional sources become available when the generated folders exist:

- `bvh_lafan1_refined`
- `bvh_lafan1_selected`

Example:

```python
GMR(src_human="bvh_lafan1_selected", tgt_robot="unitree_g1_23dof", ...)
```

This allows batch pipelines to target the final chosen configs directly.

## Important safety rule

The selected config set is **not** “the most aggressive” set.
It is the set that survived validation.
Whenever a new config did not prove improvement, baseline was retained.

That makes this branch suitable as a safer base for later large-scale processing.
