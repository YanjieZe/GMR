#!/usr/bin/env python3
import argparse, hashlib, json, pickle, subprocess, sys, time
from pathlib import Path
import numpy as np
from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import general_motion_retargeting.motion_retarget as mr
from general_motion_retargeting import GeneralMotionRetargeting as GMR
from general_motion_retargeting.params import ROBOT_XML_DICT, IK_CONFIG_DICT
from general_motion_retargeting.utils.lafan1 import load_bvh_file


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def git_value(args, default='unknown'):
    try:
        return subprocess.check_output(args, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return default


def save_motion(path, qpos_list, fps):
    root_pos = np.array([q[:3] for q in qpos_list])
    root_rot = np.array([q[3:7][[1,2,3,0]] for q in qpos_list])
    dof_pos = np.array([q[7:] for q in qpos_list])
    motion = {'fps': int(fps), 'root_pos': root_pos, 'root_rot': root_rot, 'dof_pos': dof_pos, 'local_body_pos': None, 'link_body_list': None}
    with open(path, 'wb') as f:
        pickle.dump(motion, f)
    return motion


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--bvh_file', required=True)
    ap.add_argument('--robot', required=True)
    ap.add_argument('--config_path', required=True)
    ap.add_argument('--output_dir', required=True)
    ap.add_argument('--motion_fps', type=int, default=30)
    ap.add_argument('--format', default='lafan1')
    ap.add_argument('--solver', default='daqp')
    ap.add_argument('--damping', type=float, default=0.5)
    ap.add_argument('--max_iter', type=int, default=10)
    ap.add_argument('--scheme_name', required=True)
    args = ap.parse_args()

    started = time.time()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / 'output.pkl'
    manifest_path = output_dir / 'manifest.json'
    telemetry_path = output_dir / 'telemetry.json'

    bvh_path = Path(args.bvh_file).resolve()
    cfg_path = Path(args.config_path).resolve()
    robot_xml = Path(ROBOT_XML_DICT[args.robot]).resolve()

    src_key = f'bvh_{args.format}'
    IK_CONFIG_DICT[src_key][args.robot] = cfg_path
    mr.IK_CONFIG_DICT[src_key][args.robot] = cfg_path

    frames, actual_human_height = load_bvh_file(str(bvh_path), format=args.format)
    retargeter = GMR(src_human=src_key, tgt_robot=args.robot, actual_human_height=actual_human_height, solver=args.solver, damping=args.damping)
    retargeter.max_iter = args.max_iter

    qpos_list = []
    frame_errors = []
    for idx, frame in enumerate(tqdm(frames, desc=f'retarget:{args.scheme_name}')):
        q = retargeter.retarget(frame)
        qpos_list.append(q)
        frame_errors.append({'frame': int(idx), 'error1': float(retargeter.error1()) if retargeter.use_ik_match_table1 else 0.0, 'error2': float(retargeter.error2()) if retargeter.use_ik_match_table2 else 0.0})

    motion = save_motion(output_path, qpos_list, args.motion_fps)
    with open(telemetry_path, 'w') as f:
        json.dump({'scheme_name': args.scheme_name, 'num_frames': len(qpos_list), 'fps': args.motion_fps, 'frame_errors': frame_errors}, f, indent=2)
    manifest = {
        'source_bvh_path': str(bvh_path), 'source_bvh_sha256': sha256_file(bvh_path),
        'robot_name': args.robot, 'robot_xml_path': str(robot_xml), 'robot_xml_sha256': sha256_file(robot_xml),
        'git_sha': git_value(['git','rev-parse','HEAD']), 'branch_name': git_value(['git','branch','--show-current']),
        'command': ' '.join([sys.executable] + sys.argv), 'fps': args.motion_fps, 'output_pickle_path': str(output_path.resolve()),
        'scheme_name': args.scheme_name, 'config_path': str(cfg_path), 'config_sha256': sha256_file(cfg_path),
        'scheme_parameters': {'solver': args.solver, 'damping': args.damping, 'max_iter': args.max_iter, 'format': args.format},
        'runtime_seconds': float(time.time() - started), 'num_frames': int(motion['dof_pos'].shape[0]), 'num_dofs': int(motion['dof_pos'].shape[1])
    }
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)
    print(json.dumps({'output': str(output_path), 'manifest': str(manifest_path)}, indent=2))

if __name__ == '__main__':
    main()
