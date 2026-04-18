#!/usr/bin/env python3
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFINED_MANIFEST = ROOT / 'general_motion_retargeting' / 'ik_configs_refined' / 'manifest.json'
SELECTED_DIR = ROOT / 'general_motion_retargeting' / 'ik_configs_selected'
VALIDATION_SUMMARY = ROOT / 'logs' / 'lafan1_config_refresh_validation' / 'summary.json'
FINAL_SELECTION_MD = ROOT / 'logs' / 'lafan1_config_refresh_validation' / 'final_selection.md'

SELECTED_DIR.mkdir(parents=True, exist_ok=True)
refined_manifest = json.load(open(REFINED_MANIFEST))
summary_rows = {row['robot']: row for row in json.load(open(VALIDATION_SUMMARY))['rows']}


def resolve_manifest_path(path_str: str) -> Path:
    path = Path(path_str)
    return path if path.is_absolute() else ROOT / path


def portable_path(path: Path | None) -> str | None:
    if path is None:
        return None
    path = path.resolve()
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)

selected = {}
for robot, info in sorted(refined_manifest.items()):
    decision = 'baseline'
    reason = 'no validated improvement from template search yet'
    source_path = resolve_manifest_path(info['source'])

    if robot == 'agibot_a2':
        decision = 'blocked'
        reason = 'asset mesh missing in current environment'
    elif robot == 'unitree_g1_23dof':
        decision = 'refined'
        reason = 'special robot-specific tuned balance config validated'
        source_path = ROOT / 'general_motion_retargeting' / 'ik_configs_refined_seeds' / 'unitree_g1_23dof.elbow30_wrist20.json'
    elif robot == 'unitree_g1_29dof':
        decision = 'refined'
        reason = 'special conservative g1_29 config validated with positive score reduction'
        source_path = ROOT / 'general_motion_retargeting' / 'ik_configs_refined' / 'bvh_lafan1_to_unitree_g1_29dof.refined.json'
    elif robot in ['berkeley_humanoid_lite', 'openloong', 'pnd_adam_lite']:
        decision = 'refined'
        reason = 'single-stage mid template improved representative validation'
        source_path = ROOT / 'logs' / 'profile_tuning_v2' / 'configs' / f'{robot}.single_stage.mid.json'
    else:
        row = summary_rows.get(robot)
        if row and row.get('recommended'):
            decision = 'refined'
            reason = 'first-pass refined config improved validation'
            source_path = Path(info['refined'])

    if decision != 'blocked':
        target = SELECTED_DIR / f'bvh_lafan1_to_{robot}.selected.json'
        shutil.copyfile(source_path, target)
        selected_path = portable_path(target)
    else:
        selected_path = None

    selected[robot] = {
        'decision': decision,
        'reason': reason,
        'source_config': portable_path(source_path),
        'selected_config': selected_path,
    }

(SELECTED_DIR / 'manifest.json').write_text(json.dumps(selected, indent=2))

lines = ['# Final selected LAFAN1 config manifest', '', '| robot | decision | source config | selected config | reason |', '|---|---|---|---|---|']
for robot, info in selected.items():
    lines.append(f"| {robot} | {info['decision']} | `{info['source_config']}` | `{info['selected_config']}` | {info['reason']} |")
FINAL_SELECTION_MD.write_text('\n'.join(lines) + '\n')
print(json.dumps({'selected_manifest': portable_path(SELECTED_DIR / 'manifest.json'), 'final_selection_md': portable_path(FINAL_SELECTION_MD)}, indent=2))
