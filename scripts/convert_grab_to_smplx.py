import os
import pickle
from pathlib import Path

import ipdb
import torch
import numpy as np
import smplx
from scipy.spatial.transform import Rotation as R
from smplx.joint_names import JOINT_NAMES


# These paths are from the GRAB dataset npz files
motion_files = [
    'data/GRAB/s1/apple_lift.npz',
    # '/move/u/mpiseno/data/GRAB/grab/s1/banana_pass_1.npz',
    # '/move/u/mpiseno/data/GRAB/grab/s1/binoculars_see_1.npz',
    # '/move/u/mpiseno/data/GRAB/grab/s1/cubelarge_lift.npz',
    # '/move/u/mpiseno/data/GRAB/grab/s1/cubesmall_lift.npz',
    # '/move/u/mpiseno/data/GRAB/grab/s1/duck_inspect_1.npz',
    # '/move/u/mpiseno/data/GRAB/grab/s1/elephant_offhand_1.npz',
    # 'data/GRAB/s1/mug_drink_1.npz',
    # '/move/u/mpiseno/data/GRAB/grab/s1/teapot_pour_1.npz',
    # '/move/u/mpiseno/data/GRAB/grab/s1/waterbottle_open_1.npz',
]


def construct_smplx_data(smplx_file):
    data = dict(np.load(smplx_file, allow_pickle=True))
    body_dict = data["body"].item()["params"]
    lhand_dict = data["lhand"].item()["params"]
    rhand_dict = data["rhand"].item()["params"]
    smplx_data = {}
    smplx_data["mocap_frame_rate"] = data["framerate"]
    smplx_data["gender"] = data["gender"]
    smplx_data["betas"] = np.zeros((1, 16))
    smplx_data["pose_body"] = body_dict["body_pose"]
    smplx_data["root_orient"] = body_dict["global_orient"]
    smplx_data["trans"] = body_dict["transl"]
    smplx_data["left_hand_pose"] = lhand_dict["fullpose"]
    smplx_data["right_hand_pose"] = rhand_dict["fullpose"]
    return smplx_data


def main():
    HERE = Path(__file__).parent
    smplx_body_model_dir = HERE / ".." / "assets" / "body_models"
    target_dir = "./data/GRAB_smplx"

    os.makedirs(target_dir, exist_ok=True)
    for motion_file in motion_files:
        print(f"Processing {motion_file}...")
        subject = motion_file.split('/')[-2]  # e.g., 's1'
        seq_name = motion_file.split('/')[-1][:-len('.npz')] # e.g., 'apple_lift'
        motion_file.split('/')[:-3]

        smplx_data = construct_smplx_data(motion_file)

        out_dir = f"{target_dir}/{subject}"
        os.makedirs(out_dir, exist_ok=True)
        with open(f"{out_dir}/{seq_name}.pkl", "wb") as f:
            pickle.dump(smplx_data, f)
            
        print(f"saved to {out_dir}/{seq_name}.pkl")


if __name__ == "__main__":
    main()