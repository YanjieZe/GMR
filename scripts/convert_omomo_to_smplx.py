import os
import joblib
import numpy as np
# these paths are from the original OMOMO dataset
motion_path1 = "/home/kai/GMR1/data/data/train_diffusion_manip_seq_joints24.p"
motion_path2 = "/home/kai/GMR1/data/data/test_diffusion_manip_seq_joints24.p"
all_motion_data1 = joblib.load(motion_path1)
all_motion_data2 = joblib.load(motion_path2)

# save as individual files
target_dir = "/home/kai/GMR1/data/test"
os.makedirs(target_dir, exist_ok=True)
for motion_data in [all_motion_data1, all_motion_data2]:
    for data_name in motion_data.keys():
        
        smpl_data = motion_data[data_name]
        seq_name = smpl_data['seq_name']
        # save as npz
        num_frames = smpl_data["pose_body"].shape[0]
        mocap_frame_rate = 30
        poses = np.concatenate([smpl_data["pose_body"], 
                                np.zeros((num_frames, 102))],
                                axis=1)
        smpl_data["poses"] = poses
        smpl_data["mocap_frame_rate"] = np.array(mocap_frame_rate)
        # save as npz
        np.savez(f"{target_dir}/{seq_name}.npz", **smpl_data)
        print(f"saved {seq_name} to npz")