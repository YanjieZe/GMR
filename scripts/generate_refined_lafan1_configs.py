#!/usr/bin/env python3
import json
from pathlib import Path
from general_motion_retargeting.params import IK_CONFIG_DICT, IK_CONFIG_ROOT

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'general_motion_retargeting' / 'ik_configs_refined'
SEED_DIR = ROOT / 'general_motion_retargeting' / 'ik_configs_refined_seeds'
OUT.mkdir(parents=True, exist_ok=True)


def portable_path(path: Path) -> str:
    path = path.resolve()
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)

# explicit extras not currently wired in params for bvh_lafan1 mapping
EXTRA = {
    'agibot_a2': IK_CONFIG_ROOT / 'bvh_lafan1_to_a2.json',
    'openloong': IK_CONFIG_ROOT / 'bvh_lafan1_to_openloong.json',
}

mapping = dict(IK_CONFIG_DICT['bvh_lafan1'])
mapping.update(EXTRA)

full_arm_conservative = {
    's1': {
        'Hips': (10, None),
        'LeftUpLeg': (3, None), 'RightUpLeg': (3, None), 'LeftLeg': (3, None), 'RightLeg': (3, None),
        'Spine2': (4, 70),
        'LeftArm': (6, 50), 'RightArm': (6, 50),
        'LeftForeArm': (5, 10), 'RightForeArm': (5, 10),
        'LeftHand': (5, 10), 'RightHand': (5, 10),
    },
    's2': {
        'Spine2': (8, 15),
        'LeftArm': (20, 60), 'RightArm': (20, 60),
        'LeftForeArm': (15, 5), 'RightForeArm': (15, 5),
        'LeftHand': (12, 5), 'RightHand': (12, 5),
    }
}

medium_arm_conservative = {
    's1': {
        'Hips': (10, None),
        'LeftUpLeg': (3, None), 'RightUpLeg': (3, None), 'LeftLeg': (3, None), 'RightLeg': (3, None),
        'Spine2': (4, 70),
        'LeftArm': (5, 50), 'RightArm': (5, 50),
        'LeftForeArm': (4, 10), 'RightForeArm': (4, 10),
        'LeftHand': (4, 10), 'RightHand': (4, 10),
    },
    's2': {
        'Spine2': (8, 15),
        'LeftArm': (18, 55), 'RightArm': (18, 55),
        'LeftForeArm': (12, 5), 'RightForeArm': (12, 5),
        'LeftHand': (10, 5), 'RightHand': (10, 5),
    }
}

single_stage_balanced = {
    's1': {
        'Hips': (10, None),
        'LeftUpLeg': (3, None), 'RightUpLeg': (3, None), 'LeftLeg': (3, None), 'RightLeg': (3, None),
        'Spine2': (3, 70),
        'LeftArm': (5, 60), 'RightArm': (5, 60),
        'LeftForeArm': (3, 10), 'RightForeArm': (3, 10),
        'LeftHand': (3, 10), 'RightHand': (3, 10),
    }
}

# best-balance config discovered for g1_23dof
def load_json(path):
    with open(path) as f:
        return json.load(f)

G1_23_BEST = load_json(SEED_DIR / 'unitree_g1_23dof.elbow30_wrist20.json')
G1_29_CONSERVATIVE = load_json(ROOT / 'general_motion_retargeting' / 'ik_configs' / 'bvh_lafan1_to_g1.json')
# conservative 29dof refresh philosophy: light stage1 position, stage2 torso support and moderate shoulder conflict reduction
for table in ['ik_match_table1','ik_match_table2']:
    pass
# stage1
for key,human,pos,rot in []:
    pass
G1_29_CONSERVATIVE['ik_match_table1']['pelvis'][1] = 10
for k in ['left_hip_yaw_link','right_hip_yaw_link','left_knee_link','right_knee_link']:
    G1_29_CONSERVATIVE['ik_match_table1'][k][1] = 3
G1_29_CONSERVATIVE['ik_match_table1']['torso_link'][1] = 3; G1_29_CONSERVATIVE['ik_match_table1']['torso_link'][2] = 80
for k in ['left_shoulder_yaw_link','right_shoulder_yaw_link']:
    G1_29_CONSERVATIVE['ik_match_table1'][k][1] = 5; G1_29_CONSERVATIVE['ik_match_table1'][k][2] = 70
for k in ['left_elbow_link','right_elbow_link','left_wrist_yaw_link','right_wrist_yaw_link']:
    G1_29_CONSERVATIVE['ik_match_table1'][k][1] = 3; G1_29_CONSERVATIVE['ik_match_table1'][k][2] = 10
# stage2
G1_29_CONSERVATIVE['ik_match_table2']['torso_link'][1] = 5; G1_29_CONSERVATIVE['ik_match_table2']['torso_link'][2] = 15
for k in ['left_shoulder_yaw_link','right_shoulder_yaw_link']:
    G1_29_CONSERVATIVE['ik_match_table2'][k][1] = 15; G1_29_CONSERVATIVE['ik_match_table2'][k][2] = 60
for k in ['left_elbow_link','right_elbow_link','left_wrist_yaw_link','right_wrist_yaw_link']:
    if 'elbow' in k:
        G1_29_CONSERVATIVE['ik_match_table2'][k][1] = 12
    else:
        G1_29_CONSERVATIVE['ik_match_table2'][k][1] = 10
    G1_29_CONSERVATIVE['ik_match_table2'][k][2] = 5

SPECIAL = {
    'unitree_g1_23dof': G1_23_BEST,
    'unitree_g1_29dof': G1_29_CONSERVATIVE,
}

# optional special handling for small second stage like talos
TALOS_SPECIAL = load_json(mapping['pal_talos'])
for human, entry in TALOS_SPECIAL['ik_match_table1'].items() if False else []:
    pass


def apply_profile(cfg, profile, stage2_enabled=True):
    for table_name, edits in [('ik_match_table1', profile.get('s1', {})), ('ik_match_table2', profile.get('s2', {}))]:
        table = cfg.get(table_name, {})
        if table_name == 'ik_match_table2' and not stage2_enabled:
            continue
        for body_key, entry in table.items():
            human = entry[0]
            if human in edits:
                pos, rot = edits[human]
                if pos is not None:
                    entry[1] = max(entry[1], pos)
                if rot is not None:
                    entry[2] = rot
    return cfg

manifest = {}
for robot, path in mapping.items():
    cfg = load_json(path)
    if robot in SPECIAL:
        new_cfg = SPECIAL[robot]
        profile = 'special'
    else:
        if not cfg.get('use_ik_match_table2', False):
            new_cfg = apply_profile(cfg, single_stage_balanced, stage2_enabled=False)
            profile = 'single_stage_balanced'
        elif len(cfg.get('ik_match_table2', {})) < 8:
            new_cfg = apply_profile(cfg, medium_arm_conservative, stage2_enabled=True)
            profile = 'two_stage_partial_stage2'
        elif len(cfg.get('ik_match_table2', {})) >= 13:
            new_cfg = apply_profile(cfg, full_arm_conservative, stage2_enabled=True)
            profile = 'two_stage_full_arm_conservative'
        else:
            new_cfg = apply_profile(cfg, medium_arm_conservative, stage2_enabled=True)
            profile = 'two_stage_medium_arm_conservative'
    out_path = OUT / f'bvh_lafan1_to_{robot}.refined.json'
    out_path.write_text(json.dumps(new_cfg, indent=2))
    manifest[robot] = {
        'source': portable_path(path),
        'refined': portable_path(out_path),
        'profile': profile,
        'use_stage2': bool(new_cfg.get('use_ik_match_table2', False)),
    }

(OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2))
print(json.dumps({'count': len(manifest), 'out_dir': portable_path(OUT), 'manifest': portable_path(OUT/'manifest.json')}, indent=2))
