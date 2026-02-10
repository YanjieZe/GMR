import re
import numpy as np
from scipy.spatial.transform import Rotation as R

class Anim(object):
    """
    A very basic animation object
    """

    def __init__(self, quats, pos, offsets, parents, bones):
        """
        :param quats: local quaternions tensor
        :param pos: local positions tensor
        :param offsets: local joint offsets
        :param parents: bone hierarchy
        :param bones: bone names
        """
        self.quats = quats
        self.pos = pos
        self.offsets = offsets
        self.parents = parents
        self.bones = bones


ordermap = {
    "x": 0,
    "y": 1,
    "z": 2,
}

rot_channelmap = {"Xrotation": "x", "Yrotation": "y", "Zrotation": "z"}

rot_channelmap_inv = {
    "x": "Xrotation",
    "y": "Yrotation",
    "z": "Zrotation",
}

pos_channelmap = {"Xposition": "x", "Yposition": "y", "Zposition": "z"}

pos_channelmap_inv = {
    "x": "Xposition",
    "y": "Yposition",
    "z": "Zposition",
}


def euler_to_quat(euler):
    """Convert Euler angles (in degrees) to quaternion(wxyz) in xyz order."""
    # Convert degrees to radians
    mujoco_euler_rad = np.deg2rad(np.array(euler))
    # mujoco_euler_rad = euler
    rot = R.from_euler("xyz", mujoco_euler_rad, degrees=False)
    quat = rot.as_quat(scalar_first=True)
    return quat


def remove_quat_discontinuities(rotations):
    """

    Removing quat discontinuities on the time dimension (removing flips)

    :param rotations: Array of quaternions of shape (T, J, 4)
    :return: The processed array without quaternion inversion.
    """
    rots_inv = -rotations
    for i in range(1, rotations.shape[0]):
        replace_mask = np.sum(
            rotations[i - 1 : i] * rotations[i : i + 1], axis=-1
        ) < np.sum(rotations[i - 1 : i] * rots_inv[i : i + 1], axis=-1)
        replace_mask = replace_mask[..., np.newaxis]
        rotations[i] = replace_mask * rots_inv[i] + (1.0 - replace_mask) * rotations[i]
    return rotations


def quat_fk(lrot, lpos, parents):
    """
    Performs Forward Kinematics (FK) on local quaternions and local positions to retrieve global representations

    :param lrot: tensor of local quaternions with shape (..., Nb of joints, 4)
    :param lpos: tensor of local positions with shape (..., Nb of joints, 3)
    :param parents: list of parents indices
    :return: tuple of tensors of global quaternion, global positions
    """
    gp, gr = [lpos[..., :1, :]], [lrot[..., :1, :]]
    for i in range(1, len(parents)):
        gp.append(
            quat_mul_vec(gr[parents[i]], lpos[..., i : i + 1, :]) + gp[parents[i]]
        )
        gr.append(quat_mul(gr[parents[i]], lrot[..., i : i + 1, :]))

    res = np.concatenate(gr, axis=-2), np.concatenate(gp, axis=-2)
    return res


def quat_mul(x, y):
    """
    Performs quaternion multiplication on arrays of quaternions

    :param x: tensor of quaternions of shape (..., Nb of joints, 4)
    :param y: tensor of quaternions of shape (..., Nb of joints, 4)
    :return: The resulting quaternions
    """
    x0, x1, x2, x3 = x[..., 0:1], x[..., 1:2], x[..., 2:3], x[..., 3:4]
    y0, y1, y2, y3 = y[..., 0:1], y[..., 1:2], y[..., 2:3], y[..., 3:4]

    res = np.concatenate(
        [
            y0 * x0 - y1 * x1 - y2 * x2 - y3 * x3,
            y0 * x1 + y1 * x0 - y2 * x3 + y3 * x2,
            y0 * x2 + y1 * x3 + y2 * x0 - y3 * x1,
            y0 * x3 - y1 * x2 + y2 * x1 + y3 * x0,
        ],
        axis=-1,
    )

    return res


def quat_mul_vec(q, x):
    """
    Performs multiplication of an array of 3D vectors by an array of quaternions (rotation).

    :param q: tensor of quaternions of shape (..., Nb of joints, 4)
    :param x: tensor of vectors of shape (..., Nb of joints, 3)
    :return: the resulting array of rotated vectors
    """
    t = 2.0 * np.cross(q[..., 1:], x)
    res = x + q[..., 0][..., np.newaxis] * t + np.cross(q[..., 1:], t)

    return res



class Node:
    def __init__(self, name, offset=None, channels=None, is_end=False):
        self.name = name
        self.offset = offset if offset is not None else [0.0, 0.0, 0.0]
        self.channels = channels if channels is not None else []
        self.children = []
        self.is_end = is_end

    def __str__(self, level=0):
        ret = (
            "  " * level
            + f"Node: {self.name}, Offset: {self.offset}, Channels: {self.channels}, Is_End: {self.is_end}\n"
        )
        for child in self.children:
            ret += child.__str__(level + 1)
        return ret


class BVHParser:
    def __init__(self, axis_order="zxy", scale=0.01):
        self.root = None

        self.frame_time = 0.0
        self.num_frames = 0
        self.channel_map = []  # 存储每个节点的通道索引
        self.axis_idx = [ordermap[ax] for ax in axis_order]
        self.scale = scale
        self.r = 0.015

    def _HIERARCHY_paser(self, line_idx=-1):
        try:
            # print(line_idx,self.line)
            if self.line.startswith("ROOT"):
                # print("ROOT")
                name = self.line.split()[1]
                self.root = Node(name)
                self.stack.append(self.root)
                self.names.append(name)
                self.offsets.append([0.0, 0.0, 0.0])
                self.parents.append(self.active)
                self.active = len(self.parents) - 1
                self.channel_map.append((self.root, 0))
            elif self.line.startswith("JOINT"):
                name = self.line.split()[1]
                if not self.stack:
                    raise ValueError(
                        f"JOINT {name} found before ROOT or outside hierarchy"
                    )
                node = Node(name)
                self.stack[-1].children.append(node)
                # print(f"{self.stack[-1].name} has child {name}")
                self.stack.append(node)
                self.names.append(name)
                self.offsets.append([0.0, 0.0, 0.0])
                self.parents.append(self.active)
                # print(f"JOINT {name} parent is {self.active}")
                self.active = len(self.parents) - 1
                self.channel_map.append((node, 0))
            elif self.line.startswith("End Site"):
                if not self.stack:
                    raise ValueError("End Site found before ROOT or outside hierarchy")
                parent = self.stack[-1]
                name = parent.name + "_end_site"
                node = Node(name, is_end=True)
                self.stack[-1].children.append(node)
                self.stack.append(node)
                self.names.append(name)
                self.offsets.append([0.0, 0.0, 0.0])
                self.parents.append(self.active)
                self.active = len(self.parents) - 1
                self.channel_map.append((node, 0))
            elif self.line.startswith("OFFSET"):
                parts = re.findall(r"[-+]?\d*\.\d+|[-+]?\d+\.\d*", self.line)
                if len(parts) != 3:
                    raise ValueError(f"Invalid OFFSET format in self.line: {self.line}")
                offset = [float(p) for p in parts]
                # 转换为 MuJoCo 坐标系: BVH [X, Y, Z] -> MuJoCo [Z, X, Y]
                # mujoco_offset = [offset[0], offset[1], offset[2]]
                # mujoco_offset = [offset[2], offset[0], offset[1]]
                mujoco_offset = [offset[i] * self.scale for i in self.axis_idx]
                if not self.stack:
                    raise ValueError("OFFSET found before any node")
                self.stack[-1].offset = mujoco_offset
                self.offsets[-1] = mujoco_offset
            elif self.line.startswith("CHANNELS"):
                parts = self.line.split()
                num = int(parts[1])
                channels = parts[2 : 2 + num]
                if len(channels) != num:
                    raise ValueError(
                        f"CHANNELS count mismatch in self.line: {self.line}"
                    )
                if not self.stack:
                    raise ValueError("CHANNELS found before any node")
                self.stack[-1].channels = channels
                # 更新 channel_map 中的通道起始索引
                if self.stack[-1] is not self.root:
                    self.channel_map[-1] = (
                        self.stack[-1],
                        self.channel_map[-1][1] + num,
                    )
            elif self.line == "{":
                pass
            elif self.line == "}":
                if not self.stack:
                    raise ValueError("Unmatched closing brace '}'")
                self.stack.pop()
                # for idx, node in enumerate(self.stack):
                #     print("\t" * idx, node.name)
                if self.stack:
                    self.active = self.parents[self.active]
                    # print("}", self.active)
            else:
                raise ValueError(f"Unrecognized self.line in HIERARCHY: {self.line}")
        except Exception as e:
            raise ValueError(
                f"Error parsing HIERARCHY self.line {line_idx+1}: {self.line}\n{e}"
            )

        return 1

    def _init_HIERARCHY_paser_stack(self):
        self.stack = []
        self.names = []
        self.offsets = []
        self.parents = []
        self.active = -1

    def _MOTION_paser(self, line_idx=-1):
        try:
            # print(line_idx,self.line)
            if self.line.startswith("Frames:"):
                self.num_frames = int(self.line.split()[1])
                print(f"MOTION has {self.num_frames} frames")
            elif self.line.startswith("Frame Time:"):
                self.frame_time = float(self.line.split()[2])
                print(f"MOTION frame time is {self.frame_time} s/frame")
            else:
                # 解析帧数据
                parts = re.findall(r"[-+]?\d*\.\d+|[-+]?\d+\.\d*", self.line)
                frame_data = [float(p) for p in parts]
                self.frames.append(frame_data)
        except Exception as e:
            raise ValueError(
                f"Error parsing MOTION line {line_idx+1}: {self.line}\n{e}"
            )
        return 1

    def _init_MOTION_paser_stack(self):
        self.frames = []
        return

    def _MOTION_data_process(self, start=None, end=None, reset_to_zero=False):
        # 解析 MOTION
        rotations = []
        positions = []
        # # 处理帧范围
        start = start if start is not None else 0
        end = end if end is not None else self.num_frames
        if start < 0 or end > self.num_frames or start >= end:
            raise ValueError(
                f"Invalid frame range: start={start}, end={end}, num_frames={self.num_frames}"
            )
        fnum = end - start
        frames = self.frames[start:end]

        # 初始化输出数组
        N = len(self.names)  # 关节数
        self.rotations = np.zeros((fnum, N, 3))  # 欧拉角
        self.positions = np.array(self.offsets)[np.newaxis].repeat(
            fnum, axis=0
        )  # (fnum, N, 3)

        # 解析 MOTION 数据
        for fi, frame_data in enumerate(frames):
            channel_idx = 0
            for node_idx, (node, _) in enumerate(self.channel_map):
                channels = node.channels
                num_channels = len(channels)
                data = frame_data[channel_idx : channel_idx + num_channels]
                if num_channels == 6:
                    # 根节点: 位置 + 旋转
                    pos_cha = channels[:3]
                    rot_cha = channels[3:]
                    bvh_pos_idx = [ordermap[pos_channelmap[c]] for c in pos_cha]
                    bvh_rot_idx = [ordermap[rot_channelmap[c]] for c in rot_cha]
                    bvh_pos = [data[0:3][i] for i in bvh_pos_idx]
                    bvh_rot = [data[3:6][i] for i in bvh_rot_idx]

                    # 转换为 MuJoCo 坐标系: BVH [X, Y, Z] -> MuJoCo [Z, X, Y]
                    mujoco_pos = [bvh_pos[i] * self.scale for i in self.axis_idx]
                    mujoco_rot = [bvh_rot[i] for i in self.axis_idx]
                    if node.name == "Hips":
                        self.positions[fi, node_idx] = mujoco_pos
                    self.rotations[fi, node_idx] = mujoco_rot

                elif num_channels == 3:
                    # 其他关节: 仅旋转
                    rot_cha = channels
                    bvh_rot_idx = [ordermap[rot_channelmap[c]] for c in rot_cha]
                    bvh_rot = [data[0:3][i] for i in bvh_rot_idx]
                    mujoco_rot = [bvh_rot[i] for i in self.axis_idx]
                    self.rotations[fi, node_idx] = mujoco_rot
                elif num_channels == 0:
                    # End Site: 旋转赋值为0
                    self.rotations[fi, node_idx] = [0, 0, 0]
                channel_idx += num_channels
        return self.rotations, self.positions

    def _MOTION_data_post_processing(self, rotations, positions, reset_to_zero):
        # 转换为四元数
        quats = np.array(
            [[euler_to_quat(rot) for rot in frame] for frame in rotations]
        )  # (fnum, N, 4)

        # 消除四元数翻转
        quats = remove_quat_discontinuities(quats)

        # 转换为 numpy 数组
        offsets = np.array(self.offsets)  # (N, 3)
        parents = np.array(self.parents, dtype=int)  # (N,)
        if reset_to_zero:
            
            positions[:, 0][:, 0:2] -= positions[:, 0][0, 0:2]

            positions[:, 0] = self.compensate_displacements(
                quats[:, 0], positions[:, 0]
            )
            quats[:, 0] = self.compensate_z_rotation(quats[:, 0])
        return quats, positions, offsets, parents

    def bias_edit(self, rotations, positions):
        import sys
        from PyQt6.QtWidgets import QApplication
        from general_motion_retargeting.utils.xsens_vendor.bvh_edit.CurveEditor import (
            CurveEditorWindow,
        )

        # 示例数据：假设解析了BVH数据
        app = QApplication(sys.argv)
        window = CurveEditorWindow(self.names, rotations, parser=self)
        window.show()
        # app.exec()
        # sys.exit(app.exec())
        return window

    def compensate_displacements(self, quaternions, displacements):
        """
        计算第一个四元数的 z 轴转角，并对所有位移值应用补偿旋转（反向旋转）。
        参数：
            quaternions: n x 4 的 NumPy 数组，每行是一个四元数 [w, x, y, z]
            displacements: n x 3 的 NumPy 数组，每行是一个位移向量 [x, y, z]
        返回：
            新的 n x 3 数组，所有位移值已被补偿旋转
        """
        # 确保输入形状正确
        quaternions = np.array(quaternions, dtype=float)
        displacements = np.array(displacements, dtype=float)
        if (
            quaternions.shape[1] != 4
            or displacements.shape[1] != 3
            or quaternions.shape[0] != displacements.shape[0]
        ):
            raise ValueError("输入数组必须是 n x 4 的四元数和 n x 3 的位移")

        # 获取第一个四元数并归一化
        q1 = quaternions[0] / np.linalg.norm(quaternions[0])
        w, x, y, z = q1

        # 计算 z 轴转角 θ（考虑符号和象限）
        theta = 2 * np.arctan2(z, w)

        # 补偿旋转角度为 -theta
        cos_neg_theta = np.cos(-theta)
        sin_neg_theta = np.sin(-theta)

        # 构造绕 z 轴的旋转矩阵 R(-theta)
        rotation_matrix = np.array(
            [
                [cos_neg_theta, -sin_neg_theta, 0],
                [sin_neg_theta, cos_neg_theta, 0],
                [0, 0, 1],
            ]
        )

        # 对所有位移向量应用旋转（矢量化操作，更高效）
        compensated_displacements = np.dot(
            displacements, rotation_matrix.T
        )  # 使用 .T 因为矩阵是行向量形式

        return compensated_displacements

    def compensate_z_rotation(self, quaternions):
        """
        补偿 n x 4 四元数数组中所有四元数的 z 轴转角，使其等于第一个四元数的 z 轴转角归零。
        参数：
            quaternions: n x 4 的 NumPy 数组，每行是一个四元数 [w, x, y, z]
        返回：
            新的 n x 4 数组，所有四元数的 z 轴转角已被补偿
        """
        # 确保输入是 n x 4 的 NumPy 数组
        quaternions = np.array(quaternions, dtype=np.float32)
        if quaternions.shape[1] != 4:
            raise ValueError("输入数组必须是 n x 4 的形状")

        # 获取第一个四元数并归一化
        q1 = quaternions[0] / np.linalg.norm(quaternions[0])
        w, x, y, z = q1

        # 计算 z 轴转角
        # 四元数绕 z 轴旋转的表示为 [cos(θ/2), 0, 0, sin(θ/2)]
        # 比较 q1 和 z 轴旋转四元数，提取 θ
        theta = 2 * np.arctan2(z, w)  # z 轴旋转角度

        # 构造反向旋转四元数（绕 z 轴旋转 -θ）
        cos_half_theta = np.cos(-theta / 2)
        sin_half_theta = np.sin(-theta / 2)
        q_comp = np.array([cos_half_theta, 0.0, 0.0, sin_half_theta])

        # 四元数乘法函数
        def quaternion_multiply(q1, q2):
            w1, x1, y1, z1 = q1
            w2, x2, y2, z2 = q2
            w = w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2
            x = w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2
            y = w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2
            z = w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2
            return np.array([w, x, y, z])

        # 对每个四元数应用补偿旋转
        result = np.zeros_like(quaternions)
        for i in range(quaternions.shape[0]):
            # 归一化当前四元数
            q = quaternions[i] / np.linalg.norm(quaternions[i])
            # 应用补偿旋转：q_new = q_comp * q
            result[i] = quaternion_multiply(q_comp, q)
            # 确保结果四元数是单位四元数
            result[i] = result[i] / np.linalg.norm(result[i])

        return result

    def parse(self, text, start=None, end=None, reset_to_zero=False):
        lines = text.strip().split("\n")
        i = 0
        self._init_HIERARCHY_paser_stack()
        self._init_MOTION_paser_stack()
        mode = ""  # 切换 HIERARCHY 和 MOTION 模式
        # 解析 HIERARCHY
        while i < len(lines):
            self.line = lines[i].strip()
            if not self.line:
                i += 1
                continue
            if self.line.startswith("HIERARCHY"):
                mode = "HIERARCHY"
                i += 1
                continue
            if self.line.startswith("MOTION") and mode == "HIERARCHY":
                mode = "MOTION"
                i += 1
                continue

            if mode == "HIERARCHY":
                self._HIERARCHY_paser(i)
            elif mode == "MOTION":
                self._MOTION_paser(i)
            i += 1

        if self.stack:
            raise ValueError(
                "HIERARCHY parsing incomplete: stack not empty, missing closing braces"
            )
        if not self.root:
            raise ValueError("No ROOT node found in hierarchy")

        if len(self.frames) != self.num_frames:
            raise ValueError(
                f"MOTION data has {len(self.frames)} frames, but expected {self.num_frames}"
            )

        return self._MOTION_data_process(start, end, reset_to_zero)

    def generate_mujoco_xml(self, frame_0=[]):
        def generate_xml(node, indent=2):
            spaces = " " * indent
            if node.name == "Hips":
                # frame_0[2] += 0.2/self.scale
                pos_str = " ".join(f"{x:.6f}" for x in frame_0)
            else:
                pos_str = " ".join(f"{x:.6f}" for x in node.offset)

            xml = f'{spaces}<body name="{node.name}" pos="{pos_str}">\n'
            if node.name == "Hips":  # Root
                xml += f'{spaces}  <joint name="floating_base_joint" type="free" limited="false" actuatorfrclimited="false"/>\n'
            else:
                xml += f'{spaces}  <joint type="ball" name="{node.name}_joint"/>\n'
            if node.name == "Hips":
                xml += (
                    f'{spaces}  <geom type="sphere" size="{str(self.r*1.5)}" rgba="0.5 0.0 1.0 0.5"/>\n'
                )
            elif node.name.endswith("_end_site"):
                xml += (
                    f'{spaces}  <geom type="sphere" size="{str(self.r*1.5)}" rgba="1.0 0.5 0.0 0.5"/>\n'
                )
            else:
                xml += (
                    f'{spaces}  <geom type="sphere" size="{str(self.r*1.5)}" rgba="0.8 0.8 0.8 0.5"/>\n'
                )
            for child in node.children:
                v = np.array(child.offset)
                l = np.linalg.norm(v)
                pos_str = " ".join(f"{x/2:.6f}" for x in child.offset)
                q_xyzw = R.align_vectors([v/l], [[0,0,1]])[0].as_quat(scalar_first = True).tolist()
                q_str = " ".join(f"{x/2}" for x in q_xyzw)
                xml += (
                    f'{spaces}  <geom type="capsule" size="{str(self.r)} {str(np.clip(l*0.5 - self.r*2,min=0)+1e-5)}" pos="{pos_str}"  quat="{q_str}"  rgba="1.0 0.5 1.0 0.5"/>\n'
                )
                xml += generate_xml(child, indent + 2)

            xml += f"{spaces}</body>\n"
            return xml

        xml_header = """<mujoco model="human_skeleton">
  <compiler angle="degree" coordinate="local"/>
  <option gravity="0 0 -9.81"/>
  <worldbody>
"""
        xml_footer = """  </worldbody>
        """
        xml_end = """
</mujoco>
"""
        body_xml = generate_xml(self.root, 4)
        scene = """
    <!-- setup scene -->
  <statistic center="1.0 0.7 1.0" extent="0.8"/>
    <visual>
        <headlight diffuse="0.6 0.6 0.6" ambient="0.1 0.1 0.1" specular="0.9 0.9 0.9"/>
        <rgba haze="0.15 0.25 0.35 1"/>
        <global azimuth="-140" elevation="-20" offwidth="2080" offheight="1170"/>
    </visual>
    <asset>
        <texture type="skybox" builtin="gradient" rgb1="1 1 1" rgb2="1 1 1" width="800" height="800"/>
    <texture type="2d" name="groundplane" builtin="checker" mark="edge" rgb1="1 1 1" rgb2="1 1 1" markrgb="0 0 0"
      width="300" height="300"/>
    <material name="groundplane" texture="groundplane" texuniform="true" texrepeat="5 5" reflectance="0"/>
        <texture type="skybox" builtin="gradient" rgb1=".4 .5 .6" rgb2="0 0 0" width="100" height="100"/>
        <texture builtin="flat" height="1278" mark="cross" markrgb="1 1 1" name="texgeom" random="0.01" rgb1="0.8 0.6 0.4" rgb2="0.8 0.6 0.4" type="cube" width="127"/>
        <texture name="texplane" builtin="checker" height="512" width="512" rgb1=".2 .3 .4" rgb2=".1 .15 .2" type="2d" />
        <material name="MatPlane" reflectance="0.5" shininess="0.01" specular="0.1" texrepeat="1 1" texture="texplane" texuniform="true" />
        <material name="geom" texture="texgeom" texuniform="true"/>
    </asset>
    <worldbody>
        <geom name="floor" size="0 0 0.01" type="plane" material="groundplane" contype="1" conaffinity="0" priority="1"
      friction="0.6" condim="3"/>
      <!-- <light diffuse=".5 .5 .5" pos="0 0 5" dir="0 0 -1" castshadow="true"/> -->

          <light diffuse=".5 .5 .5" pos="-3 -3 5" dir="3 3 -5" castshadow="true"/>


    </worldbody>
"""
        return xml_header + body_xml + xml_footer + scene + xml_end