# LAFAN1 Config Refresh — Release Readiness

## Final local state

- Final local commit: `a00fe43`
- Primary local integration worktree: `/home/xsuper/GMR-worktrees/master_lafan1_integration`
- Parallel experiment worktree: `/home/xsuper/GMR-worktrees/lafan1_config_refresh`
- Recommended runtime source: `bvh_lafan1_selected`

## What is guaranteed at this point

1. `ik_configs_refined/` and `ik_configs_selected/` are materialized in-repo.
2. `general_motion_retargeting/params.py` exposes `bvh_lafan1_refined` and `bvh_lafan1_selected`.
3. Generated manifests are portable across worktrees and do not rely on stale absolute worktree paths.
4. The special G1 23DOF tuned seed is vendored in-repo under:
   - `general_motion_retargeting/ik_configs_refined_seeds/unitree_g1_23dof.elbow30_wrist20.json`
5. Generation scripts force-import the active worktree package first, preventing cross-worktree drift.
6. Selected-config integrity audit passes with zero issues.
7. Selected-config all-robot 5-frame smoke passes for every non-blocked robot.

## Final selection summary

### Refined / selected
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

### Blocked externally
- `agibot_a2`
  - reason: mesh asset missing in current environment

## Canonical evidence files

- Final execution summary:
  - `docs/final-execution-summary.md`
- Config refresh overview:
  - `docs/lafan1-config-refresh.md`
  - `docs/lafan1-config-refresh-summary.md`
- Final selection table:
  - `logs/lafan1_config_refresh_validation/final_selection.md`
- Integrity audit:
  - `logs/lafan1_config_refresh_validation/selected_integrity_audit.json`
- Single-frame all-robot smoke:
  - `logs/lafan1_config_refresh_validation/selected_smoke_all.json`
- Five-frame all-robot smoke:
  - `logs/lafan1_config_refresh_validation/selected_smoke_all_5frames.json`

## Minimal rerun commands

All commands assume current directory is the repo root.

### Rebuild refined + selected manifests

```bash
python scripts/generate_refined_lafan1_configs.py
python scripts/generate_selected_lafan1_configs.py
```

Expected outcome:
- no path drift back to another worktree
- no unexpected diff when rerun on final state

### Re-run integrity audit

```bash
python - <<'PY'
import json
from pathlib import Path
from general_motion_retargeting.params import IK_CONFIG_DICT
root = Path('.').resolve()
manifest = json.loads((root/'general_motion_retargeting/ik_configs_selected/manifest.json').read_text())
params_map = IK_CONFIG_DICT['bvh_lafan1_selected']
issues = []
for robot, info in manifest.items():
    if info['decision'] == 'blocked':
        continue
    selected = root / info['selected_config']
    source = root / info['source_config']
    if robot not in params_map:
        issues.append(f'missing params mapping: {robot}')
    if not selected.exists():
        issues.append(f'missing selected file: {robot}')
    if not source.exists():
        issues.append(f'missing source file: {robot}')
print(json.dumps({'issue_count': len(issues), 'issues': issues}, indent=2))
PY
```

Expected outcome:
- `issue_count = 0`

### Re-run all-robot 5-frame smoke

```bash
python - <<'PY'
import json
from pathlib import Path
from general_motion_retargeting import GeneralMotionRetargeting as GMR
from general_motion_retargeting.utils.lafan1 import load_bvh_file
root = Path('.').resolve()
manifest = json.loads((root/'general_motion_retargeting/ik_configs_selected/manifest.json').read_text())
frames, actual_human_height = load_bvh_file('/home/xsuper/GMR/dataset/lafan1/BVH/dance1_subject1.bvh', format='lafan1')
results = []
for robot, info in manifest.items():
    if info['decision'] == 'blocked':
        continue
    retargeter = GMR(src_human='bvh_lafan1_selected', tgt_robot=robot, actual_human_height=actual_human_height, solver='daqp', damping=0.5)
    for i in range(5):
        retargeter.retarget(frames[i])
    results.append(robot)
print(json.dumps({'ok_count': len(results), 'robots': results}, indent=2))
PY
```

Expected outcome:
- all 18 non-blocked robots instantiate and retarget the first 5 frames without failure

## Remaining work that is intentionally outside this local task

1. Push / rebase / reconcile with `origin/master`
2. Any PR creation or remote merge workflow
3. Supplying missing mesh assets for `agibot_a2`
4. Full-dataset production rollout across all target motions

## Operational recommendation

For subsequent large-scale LAFAN1 processing, use:

```python
GMR(src_human="bvh_lafan1_selected", tgt_robot="...", ...)
```

Do not use `ik_configs_refined/` directly as a blanket production surface unless you are intentionally re-running the selection workflow.
