import argparse
import os
import pathlib
import pickle

import numpy as np
from rich import print
from tqdm import tqdm

from general_motion_retargeting import GeneralMotionRetargeting as GMR
from general_motion_retargeting import RobotMotionViewer, load_robot_motion
from general_motion_retargeting.utils.lafan1 import load_bvh_file


DEFAULT_NEW_ROBOTS = [
    "unitree_h1",
    "booster_t1",
    "kuavo_s45",
    "hightorque_hi",
    "galaxea_r1pro",
    "berkeley_humanoid_lite",
    "booster_k1",
    "pnd_adam_lite",
    "tienkung",
    "fourier_gr3",
]


def retarget_one_motion(bvh_file, bvh_format, robot, save_path, motion_fps):
    lafan1_data_frames, actual_human_height = load_bvh_file(
        bvh_file,
        format=bvh_format,
    )

    retargeter = GMR(
        src_human=f"bvh_{bvh_format}",
        tgt_robot=robot,
        actual_human_height=actual_human_height,
    )

    qpos_list = []
    for frame in tqdm(
        lafan1_data_frames,
        desc=f"Retarget {robot}",
        leave=False,
    ):
        qpos = retargeter.retarget(frame)
        qpos_list.append(qpos.copy())

    root_pos = np.array([qpos[:3] for qpos in qpos_list])
    root_rot = np.array([qpos[3:7][[1, 2, 3, 0]] for qpos in qpos_list])
    dof_pos = np.array([qpos[7:] for qpos in qpos_list])

    motion_data = {
        "fps": motion_fps,
        "root_pos": root_pos,
        "root_rot": root_rot,
        "dof_pos": dof_pos,
        "local_body_pos": None,
        "link_body_list": None,
    }

    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    with open(save_path, "wb") as f:
        pickle.dump(motion_data, f)


def visualize_saved_motion(robot, motion_path, vis_loops=1):
    _, motion_fps, root_pos, root_rot, dof_pos, _, _ = load_robot_motion(
        motion_path,
    )

    viewer = RobotMotionViewer(
        robot_type=robot,
        motion_fps=motion_fps,
        transparent_robot=0,
        record_video=False,
    )

    try:
        for _ in range(vis_loops):
            for idx in range(len(root_pos)):
                viewer.step(
                    root_pos=root_pos[idx],
                    root_rot=root_rot[idx],
                    dof_pos=dof_pos[idx],
                    rate_limit=True,
                    follow_camera=True,
                )
    finally:
        viewer.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--bvh_file",
        type=str,
        default="dataset/lafan1/BVH/fallAndGetUp1_subject1.bvh",
        help="Single BVH file used for quick multi-robot sanity check.",
    )
    parser.add_argument(
        "--format",
        type=str,
        choices=["lafan1", "nokov"],
        default="lafan1",
    )
    parser.add_argument(
        "--output_root",
        type=str,
        default="dataset/lafan1/robot_motion",
        help="Root folder to save retargeted pkl files.",
    )
    parser.add_argument(
        "--robots",
        nargs="+",
        default=DEFAULT_NEW_ROBOTS,
        help="Robot list to process.",
    )
    parser.add_argument(
        "--motion_fps",
        type=int,
        default=30,
    )
    parser.add_argument(
        "--skip_retarget",
        action="store_true",
        default=False,
        help="Only visualize already-saved motions.",
    )
    parser.add_argument(
        "--skip_visualize",
        action="store_true",
        default=False,
        help="Only retarget and save pkl files.",
    )
    parser.add_argument(
        "--vis_loops",
        type=int,
        default=1,
        help=(
            "How many times to replay each robot motion "
            "before switching to next robot."
        ),
    )

    args = parser.parse_args()

    bvh_stem = pathlib.Path(args.bvh_file).stem

    failed = []
    for robot in args.robots:
        save_path = os.path.join(args.output_root, robot, f"{bvh_stem}.pkl")

        print(f"\n[bold cyan]=== {robot} ===[/bold cyan]")
        print(f"save_path: {save_path}")

        try:
            if not args.skip_retarget:
                retarget_one_motion(
                    bvh_file=args.bvh_file,
                    bvh_format=args.format,
                    robot=robot,
                    save_path=save_path,
                    motion_fps=args.motion_fps,
                )
                print(f"[green]Retarget done:[/green] {save_path}")

            if not args.skip_visualize:
                print(f"[yellow]Visualizing {robot} ...[/yellow]")
                visualize_saved_motion(
                    robot,
                    save_path,
                    vis_loops=args.vis_loops,
                )

        except Exception as exc:
            failed.append((robot, str(exc)))
            print(f"[red]Failed on {robot}:[/red] {exc}")

    if failed:
        print("\n[red]Finished with failures:[/red]")
        for robot, err in failed:
            print(f"- {robot}: {err}")
    else:
        print("\n[green]All robots processed successfully.[/green]")


if __name__ == "__main__":
    main()
