#!/usr/bin/env python3
import importlib.util, json, subprocess, sys
from pathlib import Path
import pickle
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC_BVH = ROOT / 'dataset/lafan1/BVH/dance1_subject1.bvh'
if not SRC_BVH.exists():
    SRC_BVH = Path('/home/xsuper/GMR/dataset/lafan1/BVH/dance1_subject1.bvh')
REFINED_DIR = ROOT / 'general_motion_retargeting/ik_configs_refined'
OUT = ROOT / 'logs/lafan1_config_refresh_validation'
OUT.mkdir(parents=True, exist_ok=True)
ANOM_PATH = Path('/home/xsuper/GMR-worktrees/s1/scripts/analyze_motion_anomalies.py')
spec = importlib.util.spec_from_file_location('anom_validate_all', str(ANOM_PATH))
anom = importlib.util.module_from_spec(spec)
sys.modules['anom_validate_all'] = anom
assert spec.loader is not None
spec.loader.exec_module(anom)

MANIFEST = json.load(open(REFINED_DIR / 'manifest.json'))
RUNNER = ROOT / 'scripts/run_headless_retarget_with_config.py'


def load_motion(path: Path):
    with open(path, 'rb') as f:
        return pickle.load(f)


def qpos(motion):
    return np.concatenate([motion['root_pos'], motion['root_rot'][:, [3,0,1,2]], motion['dof_pos']], axis=1)


def stats(arr):
    return {'max': float(np.max(arr)), 'mean': float(np.mean(arr)), 'p95': float(np.quantile(arr, 0.95)), 'p99': float(np.quantile(arr, 0.99))}


def evaluate_motion(motion_path: Path, robot: str, detector_cfg=None):
    motion = load_motion(motion_path)
    _cfg, metrics, segments, baseline_windows, top_frames, frame_scores = anom.compute_scores(motion, SRC_BVH, robot, 'lafan1', detector_cfg)
    residual, worst = anom.tracking_residuals(qpos(motion), SRC_BVH, robot, 'lafan1')
    normal_mask = np.ones_like(residual, dtype=bool)
    if baseline_windows:
        for w in baseline_windows:
            s = max(0, int(w['expanded_start']) - 1)
            e = min(len(residual) - 1, int(w['expanded_end']))
            normal_mask[s:e+1] = False
    normal = residual[normal_mask] if np.any(normal_mask) else residual
    return {
        'metrics': metrics,
        'segment_count': len(segments),
        'top_frames': top_frames[:10],
        'normal_residual': stats(normal),
        'whole_residual': stats(residual),
    }, _cfg

rows = []
for robot, info in MANIFEST.items():
    robot_dir = OUT / robot
    base_dir = robot_dir / 'baseline'
    refined_dir = robot_dir / 'refined'
    base_dir.mkdir(parents=True, exist_ok=True)
    refined_dir.mkdir(parents=True, exist_ok=True)

    baseline_output = base_dir / 'output.pkl'
    refined_output = refined_dir / 'output.pkl'
    baseline_eval = None
    refined_eval = None
    improvement = None
    blocked_reason = None
    try:
        if not baseline_output.exists():
            subprocess.run([
                sys.executable, str(RUNNER), '--bvh_file', str(SRC_BVH), '--robot', robot,
                '--config_path', info['source'], '--output_dir', str(base_dir), '--scheme_name', 'baseline_cfg'
            ], check=True)
        baseline_eval, detector_cfg = evaluate_motion(baseline_output, robot, None)
        (base_dir / 'evaluation.json').write_text(json.dumps(baseline_eval, indent=2))

        if baseline_eval['segment_count'] > 0:
            if not refined_output.exists():
                subprocess.run([
                    sys.executable, str(RUNNER), '--bvh_file', str(SRC_BVH), '--robot', robot,
                    '--config_path', info['refined'], '--output_dir', str(refined_dir), '--scheme_name', 'refined_cfg'
                ], check=True)
            refined_eval, _ = evaluate_motion(refined_output, robot, detector_cfg)
            (refined_dir / 'evaluation.json').write_text(json.dumps(refined_eval, indent=2))
            improvement = (baseline_eval['metrics']['adjusted_score'] - refined_eval['metrics']['adjusted_score']) / baseline_eval['metrics']['adjusted_score']
    except Exception as e:
        blocked_reason = str(e)
        (robot_dir / 'blocked.txt').write_text(blocked_reason + '\n')

    rows.append({
        'robot': robot,
        'profile': info['profile'],
        'baseline_adjusted_score': None if baseline_eval is None else baseline_eval['metrics']['adjusted_score'],
        'baseline_segments': None if baseline_eval is None else baseline_eval['segment_count'],
        'refined_adjusted_score': None if refined_eval is None else refined_eval['metrics']['adjusted_score'],
        'refined_segments': None if refined_eval is None else refined_eval['segment_count'],
        'improvement': improvement,
        'baseline_normal_p95': None if baseline_eval is None else baseline_eval['normal_residual']['p95'],
        'refined_normal_p95': None if refined_eval is None else refined_eval['normal_residual']['p95'],
        'recommended': bool(improvement is not None and improvement > 0),
        'blocked_reason': blocked_reason,
    })

summary = {'rows': rows}
(OUT / 'summary.json').write_text(json.dumps(summary, indent=2))
lines = ['# LAFAN1 refined config validation summary', '', '| robot | profile | baseline score | refined score | improvement | baseline segments | refined segments | baseline normal p95 | refined normal p95 | recommended |', '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|']
for row in rows:
    imp = 'n/a' if row['improvement'] is None else f"{row['improvement']:.2%}"
    bs = 'n/a' if row['baseline_adjusted_score'] is None else f"{row['baseline_adjusted_score']:.4f}"
    rs = 'n/a' if row['refined_adjusted_score'] is None else f"{row['refined_adjusted_score']:.4f}"
    bseg = 'n/a' if row['baseline_segments'] is None else str(row['baseline_segments'])
    rseg = 'n/a' if row['refined_segments'] is None else str(row['refined_segments'])
    bnp = 'n/a' if row['baseline_normal_p95'] is None else f"{row['baseline_normal_p95']:.4f}"
    rnp = 'n/a' if row['refined_normal_p95'] is None else f"{row['refined_normal_p95']:.4f}"
    lines.append(f"| {row['robot']} | {row['profile']} | {bs} | {rs} | {imp} | {bseg} | {rseg} | {bnp} | {rnp} | {row['recommended']} |")
(OUT / 'summary.md').write_text('\n'.join(lines) + '\n')
print(json.dumps({'summary': str(OUT / 'summary.md'), 'robots': len(rows)}, indent=2))
