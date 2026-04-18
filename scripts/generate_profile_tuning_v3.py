#!/usr/bin/env python3
import json
from pathlib import Path
root=Path('/home/xsuper/GMR-worktrees/lafan1_config_refresh')
configs_root=root/'general_motion_retargeting/ik_configs'
out=root/'logs/profile_tuning_v3/configs'
out.mkdir(parents=True, exist_ok=True)
reps={
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

def clone(p):
    return json.load(open(p))

def apply_v3(cfg, level='lite'):
    t1=cfg['ik_match_table1']; t2=cfg['ik_match_table2']
    # very light stage1 position support, keep rotation largely intact
    pelvis_pos = 3 if level=='lite' else 5
    leg_pos = 1 if level=='lite' else 2
    torso_pos = 1 if level=='lite' else 2
    sh_pos = 2 if level=='lite' else 3
    ew_pos = 1 if level=='lite' else 2
    if 'pelvis' in t1: t1['pelvis'][1]=max(t1['pelvis'][1], pelvis_pos)
    for k,v in t1.items():
        human=v[0]
        if human in ['LeftUpLeg','RightUpLeg','LeftLeg','RightLeg']:
            v[1]=max(v[1], leg_pos)
        elif human=='Spine2':
            v[1]=max(v[1], torso_pos)
            v[2]=max(v[2], 60 if level=='mid' else 80)
        elif human in ['LeftArm','RightArm']:
            v[1]=max(v[1], sh_pos)
            v[2]=max(v[2], 60 if level=='mid' else 80)
        elif human in ['LeftForeArm','RightForeArm','LeftHand','RightHand']:
            v[1]=max(v[1], ew_pos)
            v[2]=max(v[2], 10)
    # stage2: modest shoulder/torso support, avoid pos-heavy
    torso_pos2 = 1 if level=='lite' else 2
    torso_rot2 = 10 if level=='lite' else 15
    sh_pos2 = 5 if level=='lite' else 8
    sh_rot2 = 80 if level=='lite' else 70
    ew_pos2 = 4 if level=='lite' else 6
    ew_rot2 = 5
    for k,v in t2.items():
        human=v[0]
        if human=='Spine2':
            v[1]=max(v[1], torso_pos2)
            v[2]=max(v[2], torso_rot2)
        elif human in ['LeftArm','RightArm']:
            v[1]=max(v[1], sh_pos2)
            v[2]=max(v[2], sh_rot2)
        elif human in ['LeftForeArm','RightForeArm','LeftHand','RightHand']:
            v[1]=max(v[1], ew_pos2)
            v[2]=max(v[2], ew_rot2)
    return cfg

manifest={}
for group,robots in reps.items():
    for robot,src in robots.items():
        for level in ['lite','mid']:
            cfg=apply_v3(clone(src), level)
            name=f'{robot}.{group}.v3.{level}.json'
            path=out/name
            path.write_text(json.dumps(cfg, indent=2))
            manifest[name]={'robot':robot,'group':group,'level':level,'source':str(src)}
(out/'manifest.json').write_text(json.dumps(manifest, indent=2))
print('wrote', len(manifest), 'configs')
