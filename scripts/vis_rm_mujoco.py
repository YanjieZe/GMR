import argparse
import os

if "--headless" in os.sys.argv:
    os.environ.setdefault("MUJOCO_GL", "egl")

import imageio
import mujoco as mj
from tqdm import tqdm

from general_motion_retargeting import (
    ROBOT_BASE_DICT,
    ROBOT_XML_DICT,
    VIEWER_CAM_DISTANCE_DICT,
    RobotMotionViewer,
    load_robot_motion,
)


def render_headless_video(
    robot_type,
    motion_fps,
    motion_root_pos,
    motion_root_rot,
    motion_dof_pos,
    video_path,
    width,
    height,
    loops,
    camera_distance,
    camera_elevation,
    camera_azimuth,
):
    model = mj.MjModel.from_xml_path(str(ROBOT_XML_DICT[robot_type]))
    data = mj.MjData(model)
    robot_base = ROBOT_BASE_DICT[robot_type]

    renderer = mj.Renderer(model, height=height, width=width)
    camera = mj.MjvCamera()
    mj.mjv_defaultCamera(camera)
    camera.type = mj.mjtCamera.mjCAMERA_FREE
    camera.distance = camera_distance
    camera.elevation = camera_elevation
    camera.azimuth = camera_azimuth

    video_dir = os.path.dirname(video_path)
    if video_dir:
        os.makedirs(video_dir, exist_ok=True)

    with imageio.get_writer(video_path, fps=motion_fps) as writer:
        for _ in range(loops):
            for frame_idx in tqdm(range(len(motion_root_pos)), desc="Rendering"):
                data.qpos[:3] = motion_root_pos[frame_idx]
                data.qpos[3:7] = motion_root_rot[frame_idx]
                data.qpos[7:] = motion_dof_pos[frame_idx]
                mj.mj_forward(model, data)

                camera.lookat[:] = data.xpos[model.body(robot_base).id]
                renderer.update_scene(data, camera=camera)
                writer.append_data(renderer.render())

    renderer.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--robot", type=str, default="unitree_g1")
    parser.add_argument("--robot_motion_path", type=str, required=True)
    parser.add_argument("--record_video", action="store_true")
    parser.add_argument("--video_path", type=str, default="videos/example.mp4")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--loops", type=int, default=1)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--camera_distance", type=float, default=None)
    parser.add_argument("--camera_elevation", type=float, default=-10)
    parser.add_argument("--camera_azimuth", type=float, default=90)

    args = parser.parse_args()

    robot_type = args.robot
    robot_motion_path = args.robot_motion_path
    camera_distance = (
        args.camera_distance
        if args.camera_distance is not None
        else VIEWER_CAM_DISTANCE_DICT[robot_type]
    )

    if not os.path.exists(robot_motion_path):
        raise FileNotFoundError(f"Motion file {robot_motion_path} not found")

    (
        motion_data,
        motion_fps,
        motion_root_pos,
        motion_root_rot,
        motion_dof_pos,
        motion_local_body_pos,
        motion_link_body_list,
    ) = load_robot_motion(robot_motion_path)

    if args.headless:
        if not args.record_video:
            raise ValueError("--headless requires --record_video")
        render_headless_video(
            robot_type=robot_type,
            motion_fps=motion_fps,
            motion_root_pos=motion_root_pos,
            motion_root_rot=motion_root_rot,
            motion_dof_pos=motion_dof_pos,
            video_path=args.video_path,
            width=args.width,
            height=args.height,
            loops=args.loops,
            camera_distance=camera_distance,
            camera_elevation=args.camera_elevation,
            camera_azimuth=args.camera_azimuth,
        )
        print(f"Saved headless video to {args.video_path}")
        raise SystemExit(0)

    env = RobotMotionViewer(
        robot_type=robot_type,
        motion_fps=motion_fps,
        camera_follow=False,
        record_video=args.record_video,
        video_path=args.video_path,
    )

    frame_idx = 0
    while True:
        env.step(
            motion_root_pos[frame_idx],
            motion_root_rot[frame_idx],
            motion_dof_pos[frame_idx],
            rate_limit=True,
        )
        frame_idx += 1
        if frame_idx >= len(motion_root_pos):
            frame_idx = 0
    env.close()
