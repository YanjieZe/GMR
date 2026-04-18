#!/usr/bin/env python3
import importlib.util, json, pickle, sys
from pathlib import Path
import numpy as np
import general_motion_retargeting.motion_retarget as mr
from general_motion_retargeting.params import IK_CONFIG_DICT
ROOT=Path('/home/xsuper/GMR-worktrees/lafan1_config_refresh')
SRC=Path('/home/xsuper/GMR/dataset/lafan1/BVH/dance1_subject1.bvh')
ANOM=Path('/home/xsuper/GMR-worktrees/s1/scripts/analyze_motion_anomalies.py')
spec=importlib.util.spec_from_file_location('anom_rep_eval', str(ANOM)); anom=importlib.util.module_from_spec(spec); sys.modules['anom_rep_eval']=anom; spec.loader.exec_module(anom)
MAN=json.load(open(ROOT/'logs/profile_tuning_v2/configs/manifest.json'))
BASE_OUT=ROOT/'logs/lafan1_config_refresh_validation'
RES_A=ROOT/'logs/profile_tuning_v2/results_a'
RES_B=ROOT/'logs/profile_tuning_v2/results_b'
for robot in ['openloong','agibot_a2']:
    if robot in MAN.values():
        pass

def load_motion(path):
    with open(path,'rb') as f: return pickle.load(f)
def qpos(m): return np.concatenate([m['root_pos'],m['root_rot'][:,[3,0,1,2]],m['dof_pos']],axis=1)
def stats(a): return {'max':float(np.max(a)),'mean':float(np.mean(a)),'p95':float(np.quantile(a,0.95)),'p99':float(np.quantile(a,0.99))}
def evaluate_motion(motion_path, robot, detector_cfg=None, cfg_path=None):
    if cfg_path is not None:
        IK_CONFIG_DICT['bvh_lafan1'][robot] = Path(cfg_path)
        mr.IK_CONFIG_DICT['bvh_lafan1'][robot] = Path(cfg_path)
    motion=load_motion(motion_path)
    _cfg, metrics, segments, baseline_windows, top_frames, frame_scores = anom.compute_scores(motion, SRC, robot, 'lafan1', detector_cfg)
    residual, worst = anom.tracking_residuals(qpos(motion), SRC, robot, 'lafan1')
    normal_mask=np.ones_like(residual, dtype=bool)
    if baseline_windows:
        for w in baseline_windows:
            s=max(0,int(w['expanded_start'])-1); e=min(len(residual)-1, int(w['expanded_end']))
            normal_mask[s:e+1]=False
    normal=residual[normal_mask] if np.any(normal_mask) else residual
    return {'metrics':metrics,'segment_count':len(segments),'whole_residual':stats(residual),'normal_residual':stats(normal)}, _cfg

rows=[]
for cfg_name, info in sorted(MAN.items()):
    robot=info['robot']
    group=info['group']; level=info['level']
    results_root = RES_A if (RES_A/cfg_name.replace('.json','')).exists() else RES_B
    outdir=results_root/cfg_name.replace('.json','')
    if not (outdir/'output.pkl').exists():
        continue
    baseline_out=BASE_OUT/robot/'baseline'/'output.pkl'
    if not baseline_out.exists():
        continue
    base_eval, det = evaluate_motion(baseline_out, robot, None, info['source'])
    cand_eval, _ = evaluate_motion(outdir/'output.pkl', robot, det, ROOT/'logs/profile_tuning_v2/configs'/cfg_name)
    improvement=(base_eval['metrics']['adjusted_score']-cand_eval['metrics']['adjusted_score'])/base_eval['metrics']['adjusted_score']
    rows.append({'robot':robot,'group':group,'level':level,'cfg_name':cfg_name,'baseline_score':base_eval['metrics']['adjusted_score'],'candidate_score':cand_eval['metrics']['adjusted_score'],'improvement':improvement,'baseline_normal_p95':base_eval['normal_residual']['p95'],'candidate_normal_p95':cand_eval['normal_residual']['p95']})
summary={'rows':rows}
profile={}
for r in rows:
    key=(r['group'], r['level'])
    profile.setdefault(key, []).append(r)
profile_rows=[]
for key, vals in sorted(profile.items()):
    imp=np.mean([v['improvement'] for v in vals])
    n95=np.mean([v['candidate_normal_p95'] for v in vals])
    b95=np.mean([v['baseline_normal_p95'] for v in vals])
    profile_rows.append({'group':key[0],'level':key[1],'avg_improvement':float(imp),'avg_candidate_normal_p95':float(n95),'avg_baseline_normal_p95':float(b95),'count':len(vals)})
summary['profiles']=profile_rows
out=ROOT/'logs/profile_tuning_v2/representative_summary.json'
out.write_text(json.dumps(summary,indent=2))
lines=['# Representative profile tuning summary','','## Per config','| robot | group | level | improvement | baseline score | candidate score | baseline normal p95 | candidate normal p95 |','|---|---|---|---:|---:|---:|---:|---:|']
for r in rows:
    lines.append(f"| {r['robot']} | {r['group']} | {r['level']} | {r['improvement']:.2%} | {r['baseline_score']:.4f} | {r['candidate_score']:.4f} | {r['baseline_normal_p95']:.4f} | {r['candidate_normal_p95']:.4f} |")
lines += ['', '## Profile averages','| group | level | avg improvement | avg baseline normal p95 | avg candidate normal p95 | count |','|---|---|---:|---:|---:|---:|']
for r in profile_rows:
    lines.append(f"| {r['group']} | {r['level']} | {r['avg_improvement']:.2%} | {r['avg_baseline_normal_p95']:.4f} | {r['avg_candidate_normal_p95']:.4f} | {r['count']} |")
(ROOT/'logs/profile_tuning_v2/representative_summary.md').write_text('\n'.join(lines)+'\n')
print('\n'.join(lines))
