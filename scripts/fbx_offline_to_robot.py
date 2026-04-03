import argparse
import pathlib
import time
from general_motion_retargeting import GeneralMotionRetargeting as GMR
from general_motion_retargeting import RobotMotionViewer
from rich import print
from tqdm import tqdm
import os
import numpy as np
import pickle

def load_optitrack_fbx_motion_file(motion_file):
    with open(motion_file, "rb") as f:
        motion_data = pickle.load(f)
    return motion_data

def offset_to_ground(retargeter: GMR, motion_data):
    offset = np.inf
    for human_data in motion_data:
        human_data = retargeter.to_numpy(human_data)
        human_data = retargeter.scale_human_data(human_data, retargeter.human_root_name, retargeter.human_scale_table)
        human_data = retargeter.offset_human_data(human_data, retargeter.pos_offsets1, retargeter.rot_offsets1)
        for body_name in human_data.keys():
            pos, quat = human_data[body_name]
            if pos[2] < offset:
                offset = pos[2]

    return offset

if __name__ == "__main__":
    
    HERE = pathlib.Path(__file__).parent

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--motion_file",
        help="FBX motion file to load (OptiTrack motion).",
        required=True,
        type=str,
    )
    
    parser.add_argument(
        "--robot",
        choices=["unitree_g1", "booster_t1", "stanford_toddy", "fourier_n1", "engineai_pm01"],
        default="unitree_g1",
    )
        
    parser.add_argument(
        "--record_video",
        action="store_true",
        default=False,
    )

    parser.add_argument(
        "--video_path",
        type=str,
        default="videos/optitrack_example.mp4",
    )

    parser.add_argument(
        "--fps",
        type=int,
        default=120,
        help="Manually set fps, default 120"
    )

    parser.add_argument(
        "--rate_limit",
        action="store_true",
        default=False,
    )

    parser.add_argument(
        "--save_path",
        default=None,
        help="Path to save the robot motion.",
    )
    
    
    args = parser.parse_args()
    

    if args.save_path is not None:
        save_dir = os.path.dirname(args.save_path)
        if save_dir:  # Only create directory if it's not empty
            os.makedirs(save_dir, exist_ok=True)
        qpos_list = []

    
    # Load OptiTrack FMB motion trajectory
    print(f"Loading OptiTrack FBX motion file: {args.motion_file}")
    fbx_motion_data = load_optitrack_fbx_motion_file(args.motion_file)
    motion_fps = 120 if args.fps == 0 else args.fps
    if type(fbx_motion_data) == list:
        data_frames = fbx_motion_data
        fbx_fps = 120
    else:
        data_frames = fbx_motion_data["frames"]
        fbx_fps = fbx_motion_data["fps"]
    print(f"Loaded {len(data_frames)} frames")

    
    # Initialize the retargeting system with fbx configuration
    retargeter = GMR(
        src_human="fbx_offline",  # Use the new fbx configuration
        tgt_robot=args.robot,
        actual_human_height=1.8,
    )

    height_offset = offset_to_ground(retargeter, data_frames)
    retargeter.set_ground_offset(height_offset)

    
    robot_motion_viewer = RobotMotionViewer(robot_type=args.robot,
                                            motion_fps=fbx_fps,
                                            transparent_robot=1,
                                            record_video=args.record_video,
                                            video_path=args.video_path,
                                            camera_follow=False,
                                            # video_width=2080,
                                            # video_height=1170
                                            )
    
    # FPS measurement variables
    fps_counter = 0
    fps_start_time = time.time()
    fps_display_interval = 2.0  # Display FPS every 2 seconds
    
    print(f"FPS render target: {motion_fps}")
    print(f"FPS FBX motion: {fbx_fps}")
    
    # Create tqdm progress bar for the total number of frames
    pbar = tqdm(total=len(data_frames), desc="Retargeting OptiTrack motion")
    
    # Start the viewer
    i = 0

    while i < len(data_frames):
        
        # FPS measurement
        fps_counter += 1
        current_time = time.time()
        if current_time - fps_start_time >= fps_display_interval:
            actual_fps = fps_counter / (current_time - fps_start_time)
            print(f"Actual rendering FPS: {actual_fps:.2f}")
            fps_counter = 0
            fps_start_time = current_time
            
        # Update progress bar
        pbar.update(1)

        # Update task targets.
        smplx_data = data_frames[i]

        # retarget
        qpos = retargeter.retarget(smplx_data)

        # visualize
        robot_motion_viewer.step(
            root_pos=qpos[:3],
            root_rot=qpos[3:7],
            dof_pos=qpos[7:],
            human_motion_data=retargeter.scaled_human_data,
            rate_limit=args.rate_limit,
            # human_pos_offset=np.array([0.0, 0.0, 0.0])
        )

        i += 1

        if args.save_path is not None:
            qpos_list.append(qpos)

    if args.save_path is not None:
        import pickle
        root_pos = np.array([qpos[:3] for qpos in qpos_list])
        # save from wxyz to xyzw
        root_rot = np.array([qpos[3:7][[1,2,3,0]] for qpos in qpos_list])
        dof_pos = np.array([qpos[7:] for qpos in qpos_list])
        local_body_pos = None
        body_names = None
        
        motion_data = {
            "fps": fbx_fps,
            "root_pos": root_pos,
            "root_rot": root_rot,
            "dof_pos": dof_pos,
            "local_body_pos": local_body_pos,
            "link_body_list": body_names,
        }
        with open(args.save_path, "wb") as f:
            pickle.dump(motion_data, f)
        print(f"Saved to {args.save_path}")

    # Close progress bar
    pbar.close()
    
    robot_motion_viewer.close() 