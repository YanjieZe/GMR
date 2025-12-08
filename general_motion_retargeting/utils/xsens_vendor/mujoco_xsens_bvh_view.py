import numpy as np
import mujoco
import mujoco.viewer
import time
from BVHParser import BVHParser, euler_to_quat, Anim, quat_fk
from scipy.spatial.transform import Rotation
import argparse
from video_recorder import VideoRecorder


class mujoco_displayanimanim:
    def __init__(self, _parser, _anim):
        self.scale = _parser.scale
        self.parser = _parser
        self.anim = _anim
        self.global_data = quat_fk(self.anim.quats, self.anim.pos, self.anim.parents)

    def _init_xml_data(self, save_flag=True):
        # 生成 MuJoCo XML
        self.xml_content = self.parser.generate_mujoco_xml(frame_0=self.anim.pos[0, 0])
        # print(xml_content)
        xml_file_name = "human_skeleton.xml"
        if save_flag:
            with open(xml_file_name, "w") as f:
                f.write(self.xml_content)
            print("MuJoCo XML generated: human_skeleton.xml")
            self.model = mujoco.MjModel.from_xml_path(xml_file_name)
        else:
            self.model = mujoco.MjModel.from_xml_string(self.xml_content)
        self.data = mujoco.MjData(self.model)

    def _draw_geom(
        self,
        position,
        rotation_matrix=None,
        axis_length=0.1,
        shaft_width=0.008,
        position_offset=np.array([0, 0, 0]),
        joint_name=None,
        orientation_correction=Rotation.from_euler("xyz", [0, 0, 0]),
    ):
        # 添加X轴箭头（红色）
        i = self.viewer.user_scn.ngeom
        from_pos = np.array(position + position_offset, dtype=np.float64).reshape(-1, 1)
        if rotation_matrix is not None:
            rotation_matrix = (
                np.array(rotation_matrix, dtype=np.float64).reshape(9).reshape(-1, 1)
            )
        else:
            rotation_matrix = (
                np.eye(3).flatten().astype(np.float64).reshape(-1, 1)
            )  # 默认单位矩阵
        rgba_list = [
            np.array([1.0, 0.0, 0.0, 1.0], dtype=np.float32).reshape(-1, 1),  # 红色
            np.array([0.0, 1.0, 0.0, 1.0], dtype=np.float32).reshape(-1, 1),  # 绿色
            np.array([0.0, 0.0, 1.0, 1.0], dtype=np.float32).reshape(-1, 1),  # 蓝色
        ]
        for axis_idx in range(3):
            geom = self.viewer.user_scn.geoms[self.viewer.user_scn.ngeom]
            if joint_name is not None:
                geom.label = joint_name
            # print("from_pos:\r\n\t",from_pos.shape,"\r\n\t",from_pos)
            # print("rotation_matrix:\r\n\t",rotation_matrix.shape,"\r\n\t",rotation_matrix)
            # print("rgba_list[axis_idx]:\r\n\t",rgba_list[axis_idx].shape,"\r\n\t",rgba_list[axis_idx])
            mujoco.mjv_initGeom(
                geom,
                type=mujoco.mjtGeom.mjGEOM_ARROW,
                size=np.array([0.0, 0.0, 0.0], dtype=np.float64).reshape(-1, 1),
                pos=from_pos,
                mat=rotation_matrix,
                rgba=rgba_list[axis_idx],
            )
            fix = orientation_correction.as_matrix().astype(np.float64)
            to_pos = from_pos + axis_length * (rotation_matrix.reshape(3, 3) @ fix)[
                :, axis_idx
            ].reshape(-1, 1)
            # print("to_pos:\r\n\t",to_pos.shape,"\r\n\t",to_pos)
            mujoco.mjv_connector(
                geom,
                type=mujoco.mjtGeom.mjGEOM_ARROW,
                width=shaft_width,
                from_=from_pos,
                to=to_pos,
            )
            self.viewer.user_scn.ngeom += 1

    def set_camera(self):
        self.viewer.cam.distance = 5
        self.viewer.cam.azimuth = 135
        self.viewer.cam.elevation = 0.0
        self.viewer.cam.fixedcamid = -1
        self.viewer.cam.type = mujoco.mjtCamera.mjCAMERA_TRACKING
        self.viewer.cam.trackbodyid = 0

    def animate_bvh(self, scale=None):
        scale = self.scale if scale is None else 0.01
        print("animate scale:", scale)
        # 动画播放
        frames_len = len(self.parser.frames)
        frame_time = self.parser.frame_time
        with mujoco.viewer.launch_passive(
            self.model,
            self.data,
            # show_left_ui=False,
            # show_right_ui=False
        ) as self.viewer:
            frame_idx = 0
            self.set_camera()
            self.renderer = mujoco.renderer.Renderer(self.model, height=480, width=640)
            self.video_recorder = VideoRecorder(
                path="./recordings",
                tag=None,
                video_name="video_0",
                fps=int(1 / frame_time),
                compress=False,
            )
            while self.viewer.is_running() and frame_idx < frames_len:
                self.viewer.user_scn.ngeom = 0
                for idx, name in enumerate(self.anim.bones):
                    joint_id = mujoco.mj_name2id(
                        self.model, mujoco.mjtObj.mjOBJ_JOINT, f"{name}_joint"
                    )
                    if joint_id > 0:
                        qpos_idx = self.model.jnt_qposadr[joint_id]
                        self.data.qpos[qpos_idx : qpos_idx + 4] = self.anim.quats[
                            frame_idx, idx, :
                        ]
                        self._draw_geom(
                            self.global_data[1][frame_idx, idx],
                            rotation_matrix=Rotation.from_quat(
                                self.global_data[0][frame_idx, idx], scalar_first=True
                            )
                            .as_matrix()
                            .flatten(),
                            joint_name=name,
                        )
                    else:
                        self.data.qpos[0:3] = self.anim.pos[frame_idx, 0, :]
                        self.data.qpos[3:7] = self.anim.quats[frame_idx, 0, :]
                        self._draw_geom(
                            self.global_data[1][frame_idx, idx],
                            rotation_matrix=Rotation.from_quat(
                                self.global_data[0][frame_idx, idx], scalar_first=True
                            )
                            .as_matrix()
                            .flatten(),
                            joint_name=name,
                        )
                self.data.qvel[:] = 0
                time.sleep(frame_time)
                mujoco.mj_step(self.model, self.data)
                # self.set_camera()
                self.renderer.update_scene(
                    self.data,
                    camera=self.viewer.cam,  # 使用查看器的相机视图
                    scene_option=self.viewer.opt,  # 使用查看器的渲染选项
                )

                # 捕获图像：返回 (height, width, 3) 的 uint8 NumPy 数组 (RGB)
                img = self.renderer.render()
                self.video_recorder(img)
                self.viewer.sync()
                frame_idx += 1
                if frame_idx % frames_len == 0:
                    break


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--bvh_file",
        help="BVH motion file to load.",
        default="xsens_bvh/251016_01_slowly_walk.bvh",
        required=False,
        type=str,
    )
    parser.add_argument(
        "--scale",
        help="displacement scale",
        required=False,
        default=0.01,
        type=float,
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
        "--reset_to_zero",
        action="store_true",
        default=False,
        help="Set the displacement and Z-axis rotation to zero",
    )

    args = parser.parse_args()
    bvh_file_name = args.bvh_file
    xml_file_name = "human_skeleton.xml"
    scale = args.scale
    parser = BVHParser("zxy", args.scale)
    with open(args.bvh_file, "r") as f:
        bvh_text = f.read()
        rotations, positions = parser.parse(
            bvh_text, start=args.start, end=args.end, reset_to_zero=args.reset_to_zero
        )
    from PyQt6.QtWidgets import QApplication
    import sys

    app = QApplication(sys.argv)
    window = parser.bias_edit(rotations, positions)  # 假设rotations/positions预计算
    window.show()
    sys.exit(app.exec())
    # d = mujoco_displayanimanim(bvh_file_name, scale)
    # d.animate_bvh()
