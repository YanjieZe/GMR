import argparse
import pathlib
import time
from general_motion_retargeting import GeneralMotionRetargeting as GMR
from general_motion_retargeting import RobotMotionViewer
from general_motion_retargeting.utils.xsens import load_xsens_file
from rich import print
from tqdm import tqdm
import os
import numpy as np

if __name__ == "__main__":

    HERE = pathlib.Path(__file__).parent

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--bvh_file",
        help="BVH motion file to load.",
        # default="./xsens_bvh/xsens_walk.bvh",
        required=True,
        type=str,
    )

    parser.add_argument(
        "--robot",
        choices=[
            "unitree_g1",
            "unitree_h1_2",
            "Q1",
            "X1",
        ],
        default="unitree_h1_2",
    )

    parser.add_argument(
        "--record_video",
        action="store_true",
        default=False,
    )

    parser.add_argument(
        "--video_path",
        type=str,
        default="videos/example.mp4",
    )

    parser.add_argument(
        "--rate_limit",
        action="store_true",
        default=True,
    )

    parser.add_argument(
        "--save_path",
        # default="./retargeting_data/unitree_h1_2_xsens_walk.pkl",
        default=None,
        help="Path to save the robot motion.",
    )

    # parser.add_argument(
    #     "--axis_order",
    #     default="zxy",
    #     help="",
    # )

    parser.add_argument(
        "--scale",
        default=0.01,
        type=float,
        help="The scaling size is determined based on the units used for displacement",
    )

    parser.add_argument(
        "--reset_to_zero",
        action="store_true",
        default=False,
        help="Set the displacement and Z-axis rotation to zero",
    )

    parser.add_argument(
        "--start",
        default=None,
        type=int,
        help="The sequence number of the first frame that you want to process",
    )

    parser.add_argument(
        "--end",
        default=None,
        type=int,
        help="The sequence number of the last frame that you want to process",
    )

    parser.add_argument(
        "--bvh_format",
        default="3DSM",
        type=str,
        choices=[
            "3DSM",
        ],
        help="The format of bvh files,3ds Max,MotionBuilder,and P6?",
    )

    args = parser.parse_args()

    if args.save_path is not None:
        save_dir = os.path.dirname(args.save_path)
        if save_dir:  # Only create directory if it's not empty
            os.makedirs(save_dir, exist_ok=True)
        qpos_list = []

    # Load SMPLX trajectory
    # lafan1_data_frames, actual_human_height = load_lafan1_file(args.bvh_file)
    lafan1_data_frames, actual_human_height,frame_time = load_xsens_file(args)

    # Initialize the retargeting system
    retargeter = GMR(
        src_human="bvh_xsens",
        tgt_robot=args.robot,
        actual_human_height=actual_human_height,
    )

    motion_fps = int(1/frame_time)

    robot_motion_viewer = RobotMotionViewer(
        robot_type=args.robot,
        motion_fps=motion_fps,
        transparent_robot=0,
        record_video=args.record_video,
        video_path=args.video_path,
        # video_width=2080,
        # video_height=1170
    )

    # FPS measurement variables
    fps_counter = 0
    fps_start_time = time.time()
    fps_display_interval = 2.0  # Display FPS every 2 seconds

    print(f"mocap_frame_rate: {motion_fps}")

    # Create tqdm progress bar for the total number of frames
    pbar = tqdm(total=len(lafan1_data_frames), desc="Retargeting")

    # Start the viewer
    i = 0

    while i < len(lafan1_data_frames):

        # FPS measurement
        fps_counter += 1
        current_time = time.time()
        if current_time - fps_start_time >= fps_display_interval:
            actual_fps = fps_counter / (current_time - fps_start_time)
            # print(f"Actual rendering FPS: {actual_fps:.2f}")
            fps_counter = 0
            fps_start_time = current_time

        # Update progress bar
        pbar.update(1)

        # Update task targets.
        smplx_data = lafan1_data_frames[i]
        smplx_data = lafan1_data_frames[i]

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
        root_rot = np.array([qpos[3:7] for qpos in qpos_list])
        dof_pos = np.array([qpos[7:] for qpos in qpos_list])
        local_body_pos = None
        body_names = None

        motion_data = {
            "fps": motion_fps,
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
