# LAFAN1 Config Refresh — Usage Guide

This branch contains two generated config sets for `bvh_lafan1` retargeting:

- `general_motion_retargeting/ik_configs_refined/`
  - first-pass per-robot refreshed configs
- `general_motion_retargeting/ik_configs_selected/`
  - final chosen configs after validation

## Final selected configs

See:

- `logs/lafan1_config_refresh_validation/final_selection.md`
- `general_motion_retargeting/ik_configs_selected/manifest.json`

Current final decisions:

- **Use selected/refined** for:
  - `berkeley_humanoid_lite`
  - `openloong`
  - `pnd_adam_lite`
  - `unitree_g1_23dof`
  - `unitree_g1_29dof`
- **Fallback to baseline/original** for the rest
- **Blocked**:
  - `agibot_a2` (missing mesh asset in current environment)

## How to use selected configs directly

`general_motion_retargeting/params.py` in this branch exposes two optional sources when the generated folders exist:

- `bvh_lafan1_refined`
- `bvh_lafan1_selected`

That means code can instantiate GMR with:

```python
GMR(src_human="bvh_lafan1_selected", tgt_robot="unitree_g1_23dof", ...)
```

or

```python
GMR(src_human="bvh_lafan1_refined", tgt_robot="openloong", ...)
```

For robots whose selected config is effectively baseline, the selected file is a copied baseline config so batch jobs can still point to one unified directory.

## Validation artifacts

Main validation outputs:

- `logs/lafan1_config_refresh_validation/summary.md`
- `logs/lafan1_config_refresh_validation/final_selection.md`
- `logs/profile_tuning_v2/representative_summary.md`
- `logs/profile_tuning_v3/representative_summary.md`

## Notes on methodology

- First pass tested broad profile templates (`refined`)
- Second/third passes validated safer templates on representative robots
- Final selection is **fail-closed**:
  - if a new config did not prove improvement, baseline was retained

This keeps the generated set safe for large-scale dataset processing.
