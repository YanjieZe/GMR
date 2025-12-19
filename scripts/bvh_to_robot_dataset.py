import argparse
import pathlib
import os
import time
import pickle

import mujoco as mj
import numpy as np
import torch
from tqdm import tqdm
from rich import print

from general_motion_retargeting.utils.lafan1 import load_bvh_file as load_lafan1_file
from general_motion_retargeting.kinematics_model import KinematicsModel
from general_motion_retargeting import GeneralMotionRetargeting as GMR


def collect_bvh_files(src_folder: str):
    bvh_files = []
    for dirpath, _, filenames in os.walk(src_folder):
        for fn in filenames:
            if fn.endswith(".bvh"):
                bvh_files.append(os.path.join(dirpath, fn))
    bvh_files.sort()
    return bvh_files


if __name__ == "__main__":
    HERE = pathlib.Path(__file__).parent

    parser = argparse.ArgumentParser()
    parser.add_argument("--src_folder", required=True, type=str,
                        help="Folder containing BVH motion files to load.")
    parser.add_argument("--tgt_folder", type=str, default="../../motion_data/LAFAN1_g1_gmr",
                        help="Folder to save the retargeted motion files.")
    parser.add_argument("--robot", default="unitree_g1", type=str)
    parser.add_argument("--override", default=False, action="store_true")
    parser.add_argument("--target_fps", default=30, type=int)

    # 진행상황/테스트용 옵션 (필요 없으면 안 써도 됨)
    parser.add_argument("--max_files", default=0, type=int,
                        help="Process only first N files (0 = all).")
    parser.add_argument("--max_frames", default=0, type=int,
                        help="Process only first N frames per file (0 = all).")
    parser.add_argument("--frame_stride", default=1, type=int,
                        help="Use every N-th frame (1 = use all).")

    args = parser.parse_args()

    src_folder = args.src_folder
    tgt_folder = args.tgt_folder

    bvh_files = collect_bvh_files(src_folder)
    if args.max_files and args.max_files > 0:
        bvh_files = bvh_files[:args.max_files]

    if len(bvh_files) == 0:
        raise RuntimeError(f"No .bvh files found under: {src_folder}")

    print(f"[bold]Found {len(bvh_files)} BVH files[/bold]")

    # 전체 파일 진행률
    for bvh_file_path in tqdm(bvh_files, desc="Files", unit="file"):
        rel_path = os.path.relpath(bvh_file_path, src_folder)
        tgt_file_path = os.path.join(
            tgt_folder,
            os.path.splitext(rel_path)[0] + ".pkl"
        )

        if os.path.exists(tgt_file_path) and not args.override:
            tqdm.write(f"Skipping (exists): {tgt_file_path}")
            continue

        # Load BVH -> frames
        try:
            lafan1_data_frames, actual_human_height = load_lafan1_file(bvh_file_path)
            src_fps = 30  # LAFAN1 BVH is typically 30 FPS
        except Exception as e:
            tqdm.write(f"[LOAD ERROR] {bvh_file_path}: {e}")
            continue

        # 프레임 stride / max_frames 적용
        if args.frame_stride and args.frame_stride > 1:
            lafan1_data_frames = lafan1_data_frames[::args.frame_stride]
            src_fps = int(round(src_fps / args.frame_stride))

        if args.max_frames and args.max_frames > 0:
            lafan1_data_frames = lafan1_data_frames[:args.max_frames]

        num_frames = len(lafan1_data_frames)
        if num_frames == 0:
            tqdm.write(f"[WARN] No frames after slicing: {bvh_file_path}")
            continue

        tqdm.write(f"\n=== Processing: {rel_path} | frames={num_frames} | fps={src_fps} ===")

        # Initialize retargeting (per-file; human height can differ)
        retarget = GMR(
            src_human="bvh_lafan1",
            tgt_robot=args.robot,
            actual_human_height=actual_human_height,
        )

        # (이 두 줄은 지금 코드에서 실제로 사용하지 않으니, 유지하되 의미는 없음)
        _model = mj.MjModel.from_xml_path(retarget.xml_file)
        _data = mj.MjData(_model)

        # Retarget per frame with progress + speed/ETA
        qpos_list = []
        t0 = time.time()

        frame_pbar = tqdm(
            enumerate(lafan1_data_frames),
            total=num_frames,
            desc=f"Frames ({os.path.basename(bvh_file_path)})",
            unit="frame",
            leave=False,
            mininterval=0.2,
        )

        for i, smplx_data in frame_pbar:
            qpos = retarget.retarget(smplx_data)
            qpos_list.append(qpos.copy())

            # 속도/ETA 표시(너무 자주 업데이트하면 오히려 느려질 수 있어서 mininterval로 제한)
            elapsed = time.time() - t0
            fps_eff = (i + 1) / max(elapsed, 1e-9)
            eta_sec = (num_frames - (i + 1)) / max(fps_eff, 1e-9)
            frame_pbar.set_postfix_str(f"{fps_eff:.2f} it/s, ETA {eta_sec/60:.1f}m")

        qpos_list = np.asarray(qpos_list)

        # Forward kinematics (한 번에)
        device = "cuda:0"
        kinematics_model = KinematicsModel(retarget.xml_file, device=device)

        root_pos = qpos_list[:, :3]
        root_rot = qpos_list[:, 3:7]
        # (x,y,z,w) -> (w,x,y,z) 같은 변환이면 여기 순서 확인 필요하지만,
        # 기존 코드 유지
        root_rot[:, [0, 1, 2, 3]] = root_rot[:, [1, 2, 3, 0]]
        dof_pos = qpos_list[:, 7:]

        identity_root_pos = torch.zeros((num_frames, 3), device=device)
        identity_root_rot = torch.zeros((num_frames, 4), device=device)
        identity_root_rot[:, -1] = 1.0

        local_body_pos, _ = kinematics_model.forward_kinematics(
            identity_root_pos,
            identity_root_rot,
            torch.from_numpy(dof_pos).to(device=device, dtype=torch.float),
        )
        body_names = kinematics_model.body_names

        motion_data = {
            "root_pos": root_pos,
            "root_rot": root_rot,
            "dof_pos": dof_pos,
            "local_body_pos": local_body_pos.detach().cpu().numpy(),
            "fps": src_fps,
            "link_body_list": body_names,
        }

        os.makedirs(os.path.dirname(tgt_file_path), exist_ok=True)
        with open(tgt_file_path, "wb") as f:
            pickle.dump(motion_data, f)

        total_elapsed = time.time() - t0
        tqdm.write(f"Saved: {tgt_file_path} | time={total_elapsed:.1f}s | avg={total_elapsed/num_frames:.4f}s/frame")

    print("Done. saved to ", tgt_folder)
