import argparse
import pathlib
import os
import multiprocessing as mp
import mujoco as mj
import numpy as np
from tqdm import tqdm
import torch
import pickle

from general_motion_retargeting.utils.lafan1 import load_lafan1_file
from general_motion_retargeting.kinematics_model import KinematicsModel
from general_motion_retargeting import GeneralMotionRetargeting as GMR
from rich import print


def resolve_torch_device(requested_device: str) -> str:
    if requested_device == "auto":
        if torch.cuda.is_available():
            try:
                torch.zeros(1, device="cuda:0")
                return "cuda:0"
            except Exception as exc:
                print(f"[WARNING] CUDA probe failed, falling back to CPU: {exc}")
        return "cpu"
    if requested_device.startswith("cuda"):
        try:
            torch.zeros(1, device=requested_device)
        except Exception as exc:
            raise RuntimeError(f"Requested CUDA device '{requested_device}' is not usable: {exc}") from exc
    return requested_device


if __name__ == "__main__":
    HERE = pathlib.Path(__file__).parent

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--src_folder",
        help="Folder containing BVH motion files to load.",
        required=True,
        type=str,
    )
    
    parser.add_argument(
        "--tgt_folder",
        help="Folder to save the retargeted motion files.",
        default="../../motion_data/LAFAN1_g1_gmr"
    )
    
    parser.add_argument(
        "--robot",
        default="unitree_g1",
    )
    
    parser.add_argument(
        "--override",
        default=False,
        action="store_true",
    )
    
    parser.add_argument(
        "--target_fps",
        default=30,
        type=int,
    )
    parser.add_argument(
        "--device",
        default="auto",
        help="Forward-kinematics device: auto, cpu, cuda:0, ...",
    )

    args = parser.parse_args()
    
    src_folder = args.src_folder
    tgt_folder = args.tgt_folder
    fk_device = resolve_torch_device(args.device)
    print(f"Using FK device: {fk_device}")

   
   
        
    def process_file(bvh_file_path: str) -> None:
        tgt_file_path = bvh_file_path.replace(src_folder, tgt_folder).replace(".bvh", ".pkl")
        if os.path.exists(tgt_file_path) and not args.override:
            print(f"Skipping {bvh_file_path} because {tgt_file_path} exists")
            return

        try:
            lafan1_data_frames, actual_human_height = load_lafan1_file(bvh_file_path)
            src_fps = 30
        except Exception as e:
            print(f"Error loading {bvh_file_path}: {e}")
            return

        retarget = GMR(src_human="bvh", tgt_robot=args.robot, actual_human_height=actual_human_height)
        model = mj.MjModel.from_xml_path(retarget.xml_file)
        data = mj.MjData(model)

        qpos_list = []
        for curr_frame in range(len(lafan1_data_frames)):
            smplx_data = lafan1_data_frames[curr_frame]
            qpos = retarget.retarget(smplx_data)
            qpos_list.append(qpos.copy())

        qpos_list = np.array(qpos_list)
        device = fk_device
        kinematics_model = KinematicsModel(retarget.xml_file, device=device)

        root_pos = qpos_list[:, :3]
        root_rot = qpos_list[:, 3:7]
        root_rot[:, [0, 1, 2, 3]] = root_rot[:, [1, 2, 3, 0]]
        dof_pos = qpos_list[:, 7:]
        num_frames = root_pos.shape[0]

        identity_root_pos = torch.zeros((num_frames, 3), device=device)
        identity_root_rot = torch.zeros((num_frames, 4), device=device)
        identity_root_rot[:, -1] = 1.0
        local_body_pos, _ = kinematics_model.forward_kinematics(
            identity_root_pos,
            identity_root_rot,
            torch.from_numpy(dof_pos).to(device=device, dtype=torch.float),
        )
        body_names = kinematics_model.body_names

        HEIGHT_ADJUST = False
        PERFRAME_ADJUST = False
        if HEIGHT_ADJUST:
            body_pos, _ = kinematics_model.forward_kinematics(
                torch.from_numpy(root_pos).to(device=device, dtype=torch.float),
                torch.from_numpy(root_rot).to(device=device, dtype=torch.float),
                torch.from_numpy(dof_pos).to(device=device, dtype=torch.float),
            )
            ground_offset = 0.00
            if not PERFRAME_ADJUST:
                lowest_height = torch.min(body_pos[..., 2]).item()
                root_pos[:, 2] = root_pos[:, 2] - lowest_height + ground_offset
            else:
                for i in range(root_pos.shape[0]):
                    lowest_body_part = torch.min(body_pos[i, :, 2])
                    root_pos[i, 2] = root_pos[i, 2] - lowest_body_part + ground_offset

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

    work_items = []
    for dirpath, _, filenames in os.walk(src_folder):
        for filename in sorted(filenames):
            if filename.endswith(".bvh"):
                work_items.append(os.path.join(dirpath, filename))

    if fk_device.startswith("cuda"):
        if len(work_items) == 1:
            for path in tqdm(work_items, desc="Retargeting files"):
                process_file(path)
        else:
            ctx = mp.get_context("spawn")
            for path in tqdm(work_items, desc="Retargeting files"):
                process_file(path)
    else:
        for path in tqdm(work_items, desc="Retargeting files"):
            process_file(path)

    print("Done. saved to ", tgt_folder)
