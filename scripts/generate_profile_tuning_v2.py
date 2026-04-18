#!/usr/bin/env python3
import json
from pathlib import Path
root=Path('/home/xsuper/GMR-worktrees/lafan1_config_refresh')
configs_root=root/'general_motion_retargeting/ik_configs'
out=root/'logs/profile_tuning_v2/configs'
out.mkdir(parents=True, exist_ok=True)

# rep robots by profile
reps={
    'single_stage': {
        'berkeley_humanoid_lite': configs_root/'bvh_lafan1_to_bhl.json',
        'pnd_adam_lite': configs_root/'bvh_lafan1_to_adam.json',
        'openloong': configs_root/'bvh_lafan1_to_openloong.json',
    },
    'two_stage_medium': {
        'booster_k1': configs_root/'bvh_lafan1_to_k1.json',
        'booster_t1': configs_root/'bvh_lafan1_to_t1.json',
        'unitree_h1': configs_root/'bvh_lafan1_to_h1.json',
    },
    'two_stage_full': {
        'engineai_pm01': configs_root/'bvh_lafan1_to_pm01.json',
        'stanford_toddy': configs_root/'bvh_lafan1_to_toddy.json',
        'unitree_h1_2': configs_root/'bvh_lafan1_to_h1_2.json',
    },
    'two_stage_partial': {
        'pal_talos': configs_root/'bvh_lafan1_to_talos.json',
    }
}

def jkeys(table, substr):
    return [k for k,v in table.items() if v[0] in substr]

def apply_single(cfg, level='light'):
    t1=cfg['ik_match_table1']
    pelvis_pos = 6 if level=='light' else 10
    leg_pos = 2 if level=='light' else 3
    torso_pos = 2 if level=='light' else 3
    torso_rot = 80 if level=='light' else 70
    sh_pos = 3 if level=='light' else 5
    sh_rot = 70 if level=='light' else 60
    ew_pos = 2 if level=='light' else 3
    ew_rot = 10
    if 'pelvis' in t1: t1['pelvis'][1]=max(t1['pelvis'][1],pelvis_pos)
    for k,v in t1.items():
        human=v[0]
        if human in ['LeftUpLeg','RightUpLeg','LeftLeg','RightLeg']:
            v[1]=max(v[1],leg_pos)
            v[2]=max(v[2],10)
        elif human=='Spine2':
            v[1]=max(v[1],torso_pos); v[2]=torso_rot
        elif human in ['LeftArm','RightArm']:
            v[1]=max(v[1],sh_pos); v[2]=sh_rot
        elif human in ['LeftForeArm','RightForeArm','LeftHand','RightHand']:
            v[1]=max(v[1],ew_pos); v[2]=ew_rot
    return cfg

def apply_two_stage(cfg, level='light', partial=False):
    t1=cfg['ik_match_table1']; t2=cfg['ik_match_table2']
    # stage1 gentle geometry support
    pelvis_pos = 6 if level=='light' else 10
    leg_pos = 2 if level=='light' else 3
    torso_pos = 2 if level=='light' else 3
    torso_rot = 85 if level=='light' else 75
    sh_pos = 3 if level=='light' else 5
    sh_rot = 75 if level=='light' else 65
    ew_pos = 2 if level=='light' else 3
    ew_rot = 10
    if 'pelvis' in t1: t1['pelvis'][1]=max(t1['pelvis'][1],pelvis_pos)
    for k,v in t1.items():
        human=v[0]
        if human in ['LeftUpLeg','RightUpLeg','LeftLeg','RightLeg']:
            v[1]=max(v[1],leg_pos)
        elif human=='Spine2':
            v[1]=max(v[1],torso_pos); v[2]=torso_rot
        elif human in ['LeftArm','RightArm']:
            v[1]=max(v[1],sh_pos); v[2]=sh_rot
        elif human in ['LeftForeArm','RightForeArm','LeftHand','RightHand']:
            v[1]=max(v[1],ew_pos); v[2]=ew_rot
    # stage2 modest support, not pos-heavy
    torso_pos2 = 2 if level=='light' else 4
    torso_rot2 = 15 if level=='light' else 20
    sh_pos2 = 8 if level=='light' else 12
    sh_rot2 = 70 if level=='light' else 60
    ew_pos2 = 8 if level=='light' else 10
    ew_rot2 = 5
    active_humans={v[0] for v in t2.values()}
    for k,v in t2.items():
        human=v[0]
        if human=='Spine2':
            v[1]=max(v[1],torso_pos2); v[2]=torso_rot2
        elif human in ['LeftArm','RightArm']:
            v[1]=max(v[1],sh_pos2); v[2]=sh_rot2
        elif human in ['LeftForeArm','RightForeArm','LeftHand','RightHand']:
            v[1]=max(v[1],ew_pos2); v[2]=ew_rot2
    return cfg

manifest={}
for group,robots in reps.items():
    for robot, src in robots.items():
        for level in ['light','mid']:
            cfg=json.load(open(src))
            if group=='single_stage':
                cfg=apply_single(cfg, level)
            elif group=='two_stage_partial':
                cfg=apply_two_stage(cfg, level, partial=True)
            else:
                cfg=apply_two_stage(cfg, level)
            name=f'{robot}.{group}.{level}.json'
            path=out/name
            path.write_text(json.dumps(cfg, indent=2))
            manifest[name]={'robot':robot,'group':group,'level':level,'source':str(src)}
(out/'manifest.json').write_text(json.dumps(manifest, indent=2))
print('wrote', len(manifest), 'configs')
