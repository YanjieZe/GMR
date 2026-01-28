import sys
import numpy as np
from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QApplication,QCheckBox
from PyQt6.QtCore import Qt, QTimer
import mujoco
from scipy.spatial.transform import Rotation
# 导入提供的代码：MujocoQtViewer、BVHParser、Anim、quat_fk等
from mujoco_qt_viewer import MujocoQtViewer  # 假设文件名为mujoco_qt_viewer.py
from bvh_parser import BVHParser, Anim, quat_fk, remove_quat_discontinuities  # 假设文件名为bvh_parser.py

# 导入模块2和3
from bvh_settings_panel import BVHSettingsPanel  # 假设文件名为bvh_settings_panel.py
from curve_editor_panel import CurveEditorPanel  # 假设文件名为curve_editor_panel.py
from curve_plot_panel import CurvePlotPanel  # 假设文件名为curve_plot_panel.py
from retargeting_settings_panel import RetargetingSettingsPanel  # 假设文件名为retargeting_settings_panel.py
from general_motion_retargeting import ROBOT_XML_DICT, ROBOT_BASE_DICT, VIEWER_CAM_DISTANCE_DICT
from general_motion_retargeting import GeneralMotionRetargeting as GMR

class MainWindow(QMainWindow):
    """
    新主窗口类，整合MuJoCo viewer和叠加控件。
    - viewer铺满窗口，自适应大小。
    - 右侧叠加两个可折叠面板：BVH设置和曲线编辑。
    - 处理BVH加载、偏移应用和动画更新。
    """
    def __init__(self):
        """
        初始化主窗口。
        """
        super().__init__()
        self.setWindowTitle("BVH MuJoCo Editor")
        self.resize(1200, 800)  # 初始大小

        # 初始化MuJoCo相关（初始为空model/data，加载BVH后设置）
        self.model = None
        self.data = None
        self.parser = None
        self.anim = None
        self.global_data = None
        self.frame_idx = 0  # 当前帧
        self.is_animating = False  # 动画状态
        num = 9
        self.setFixedHeight(108*num+18)
        self.setFixedWidth(192*num+18)
        # 创建MuJoCo viewer并设置为中央部件（铺满UI）
        self.viewer = MujocoQtViewer(None, None, width=192*num, height=108*num)  # 初始空model/data
        self.setCentralWidget(self.viewer)

        # 开关控件
        self.mode_switch = QCheckBox("Retargeting Mode (Off: BVH, On: Retargeting)")
        self.mode_switch.setChecked(False)  # 默认关（BVH模式）
        self.mode_switch.toggled.connect(self.on_mode_toggled)  # 连接切换信号

        # 右侧叠加容器：绝对定位到viewer右侧
        self.overlay_container = QWidget(self.viewer)
        self.overlay_container.setObjectName("OverlayContainer")
        overlay_layout = QVBoxLayout(self.overlay_container)
        overlay_layout.insertWidget(0, self.mode_switch)  # 插入到布局顶部
        overlay_layout.setContentsMargins(10, 10, 10, 10)
        overlay_layout.setSpacing(10)
        self.overlay_container.setFixedWidth(400)  # 固定宽度
        self.overlay_container.setFixedHeight(400)  # 自适应高度
        self.overlay_container.move(self.viewer.width() - 410, 10)  # 初始位置（右侧上角）

        # Retargeting设置面板
        self.retarget_panel = RetargetingSettingsPanel(self.overlay_container)
        overlay_layout.addWidget(self.retarget_panel)

        # BVH设置面板
        self.bvh_panel = BVHSettingsPanel(self.overlay_container)
        self.bvh_panel.load_button.clicked.connect(self.on_load_bvh)  # 连接加载信号
        overlay_layout.addWidget(self.bvh_panel)

        # 曲线编辑面板
        self.editor_panel = CurveEditorPanel(parent=self.overlay_container)
        self.editor_panel.apply_button.clicked.connect(self.on_apply_offsets)  # 连接应用信号
        overlay_layout.addWidget(self.editor_panel)

        # 下部叠加容器：绝对定位到viewer下半部分
        self.plot_container = CurvePlotPanel(title="Channel Curve Plot", parent=self.viewer)
        self.plot_container.setFixedHeight(300)  # 固定高度，调整为下半部分
        self.plot_container.move(10, self.viewer.height() - 310)  # 定位到左下，留边距
        
        # 动画定时器：用于帧更新
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self.update_animation)
        self.anim_timer.setInterval(1)  # 约60FPS

    def load_model(self, xml_path):
        """
        封装模型加载：从XML路径加载MjModel和MjData，并设置到viewer。
        参数：
        - xml_path: XML文件路径。
        """
        self.model = mujoco.MjModel.from_xml_path(xml_path)
        self.data = mujoco.MjData(self.model)
        self.viewer.set_model_data(self.model, self.data)
        print(f"Loaded model from {xml_path}")
    
    def on_mode_toggled(self, checked):
        """
        开关切换：关-BVH模式，开-retargeting模式。
        - 加载对应模型，但不重复加载如果已匹配。
        - 更新动画模式。
        """
        if not self.parser or not self.anim:
            print("未加载BVH，无法切换模式。")
            self.mode_switch.setChecked(False)
            return

        if checked:  # Retargeting模式
            # TODO: 根据选择的机器人型号加载对应模型
            robot_model = self.retarget_panel.robot_combo.currentText()
            xml_path = self.robot_xml_paths.get(robot_model, "default_robot.xml")  # 从预设路径
            self.load_model(xml_path)  # 切换模型
            print("Switched to Retargeting mode with robot:", robot_model)
        else:  # BVH模式
            self.load_model("human_skeleton.xml")  # 切换回人类模型
            print("Switched to BVH mode")

        # 重置帧
        self.frame_idx = 0
    def update_bvh_animation(self):
        """
        BVH模式动画更新：使用anim数据设置qpos和markers。
        - 与原update_animation类似，但提取为独立方法。
        """
        if not self.is_animating or not self.anim:
            return

        frames_len = self.anim.quats.shape[0]
        if self.frame_idx >= frames_len:
            self.frame_idx = 0

        for idx, name in enumerate(self.anim.bones):
            joint_id = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_JOINT, f"{name}_joint")
            if joint_id > 0:
                qpos_idx = self.model.jnt_qposadr[joint_id]
                self.data.qpos[qpos_idx : qpos_idx + 4] = self.anim.quats[self.frame_idx, idx]
                self.viewer.add_marker(
                    pos=self.global_data[1][self.frame_idx, idx],
                    mat=Rotation.from_quat(self.global_data[0][self.frame_idx, idx], scalar_first=True).as_matrix().flatten(),
                    label=name,
                    type=mujoco.mjtGeom.mjGEOM_ARROW,
                    size=[0.025, 0.025, 0.025],
                    rgba=[1, 0, 0, 1]
                )
            else:
                self.data.qpos[0:3] = self.anim.pos[self.frame_idx, 0]
                self.data.qpos[3:7] = self.anim.quats[self.frame_idx, 0]
                self.viewer.add_marker(
                    pos=self.global_data[1][self.frame_idx, 0],
                    mat=Rotation.from_quat(self.global_data[0][self.frame_idx, 0], scalar_first=True).as_matrix().flatten(),
                    label=name
                )

        self.data.qvel[:] = 0
        mujoco.mj_step(self.model, self.data)
        self.viewer.render()
        self.frame_idx += 1

    def bvh_to_smplx(self,):
        anim, global_data, frame_time = self.anim, self.global_data, self.parser.frame_time 
        frames = []
        for frame in range(anim.pos.shape[0]):
            result = {}
            for i, bone in enumerate(anim.bones):
                orientation = global_data[0][frame, i]
                position = global_data[1][frame, i]
                result[bone] = (position, orientation)

            result["LeftFootMod"] = (
                np.array(
                    [
                        result["LeftAnkle"][0][0],
                        result["LeftAnkle"][0][1],
                        result["LeftAnkle"][0][2],
                        # result["LeftToe"][0][2],
                    ]
                ),
                result["LeftAnkle"][1],
                # result["LeftToe_end_site"][1],
            )
            result["RightFootMod"] = (
                np.array(
                    [
                        result["RightAnkle"][0][0],
                        result["RightAnkle"][0][1],
                        result["RightAnkle"][0][2],
                        # result["RightToe"][0][2],
                    ]
                ),
                result["RightAnkle"][1],
                # result["RightToe_end_site"][1],
            )
            frames.append(result)

        human_height = result["Head_end_site"][0][2] - min(
            result["LeftToe_end_site"][0][2], result["LeftToe_end_site"][0][2]
        )
        return frames, human_height, frame_time
    
    def update_retarget_animation(self):
        """
        Retargeting模式动画更新：使用retargeter映射smplx_data到qpos。
        - 假设smplx_data从BVH转换，retargeter为现成库。
        """
        if not self.is_animating or not self.anim:
            return

        # 使用retargeter
        qpos = self.retargeter.retarget(self.data_frames[self.frame_idx])  # 预留API

        # 设置qpos（假设机器人关节匹配qpos长度）
        self.data.qpos[:] = qpos
        self.data.qvel[:] = 0
        mujoco.mj_step(self.model, self.data)

        # 添加markers（可选，根据机器人调整）
        # ...

        self.viewer.render()
        self.frame_idx += 1  # 假设帧数与BVH一致

    def convert_to_smplx(self, frame_idx):
        """
        占位：从BVH当前帧转换到SMPL-X数据。
        - 使用smplx库实现（需import smplx）。
        返回：smplx_data（dict或array，根据retargeter需求）。
        """
        # 实现逻辑：从self.anim.quats/pos等转换
        return {}  # 占位

    def update_animation(self):
        """
        统一动画更新：根据开关选择BVH或retarget模式。
        """
        if self.mode_switch.isChecked():
            self.update_retarget_animation()
        else:
            self.update_bvh_animation()
        # 公共部分：更新plot_container等
        if hasattr(self, 'plot_container'):
            self.plot_container.update_current_frame(self.frame_idx)
    
    def on_mode_toggled(self, checked):
        """
        开关切换：关-BVH模式，开-retargeting模式。
        - 加载对应模型，但不重复加载如果已匹配。
        - 更新动画模式。
        """
        if not self.parser or not self.anim:
            print("未加载BVH，无法切换模式。")
            self.mode_switch.setChecked(False)
            return

        if checked:  # Retargeting模式
            
            robot_model = self.retarget_panel.robot_combo.currentText()
            xml_path = ROBOT_XML_DICT[robot_model]
            print("xml_path:",xml_path)
            self.load_model(str(xml_path))  # 切换模型
            print("Switched to Retargeting mode with robot:", robot_model)
        else:  # BVH模式
            self.load_model("human_skeleton.xml")  # 切换回人类模型
            print("Switched to BVH mode")

        # 重置帧
        self.frame_idx = 0
        
    def resizeEvent(self, event):
        """
        重载resize事件：调整叠加容器位置，确保始终在右侧。
        """
        super().resizeEvent(event)
        if self.overlay_container:
            self.overlay_container.move(self.viewer.width() - self.overlay_container.width() - 10, 10)
            self.overlay_container.setFixedHeight(500)  # 自适应高度
        if self.plot_container:
            self.plot_container.move(10, self.viewer.height() - self.plot_container.height() - 10)
            self.plot_container.setFixedWidth(1200)

    def on_load_bvh(self):
        """
        加载BVH文件：解析、更新编辑面板，并启动动画。
        """
        bvh_path = self.bvh_panel.bvh_path_edit.text()
        if not bvh_path:
            print("BVH路径为空，无法加载。")
            return

        # 获取参数
        scale = self.bvh_panel.scale_spin.value()
        start = self.bvh_panel.start_spin.value()
        end = self.bvh_panel.end_spin.value() if self.bvh_panel.end_spin.value() > 0 else None
        reset_to_zero = self.bvh_panel.reset_checkbox.isChecked()

        # 解析BVH
        self.parser = BVHParser(axis_order="zxy", scale=scale)
        with open(bvh_path, "r") as f:
            bvh_text = f.read()
        rotations, positions = self.parser.parse(bvh_text, start=start, end=end, reset_to_zero=reset_to_zero)

        # 后处理
        positions = np.copy(self.parser.positions)
        _quats, _positions, _offsets, _parents = self.parser._MOTION_data_post_processing(rotations, positions, reset_to_zero)
        self.anim = Anim(_quats, _positions, _offsets, _parents, self.parser.names)
        self.global_data = quat_fk(self.anim.quats, self.anim.pos, self.anim.parents)

        self.data_frames,self.human_height, self.frame_time= self.bvh_to_smplx()
        self.retargeter = GMR(
            src_human="xsens_bvh",
            tgt_robot=self.retarget_panel.robot_combo.currentText(),
            actual_human_height=self.human_height,
        )

        # 更新编辑面板
        self.editor_panel.update_joint_names(self.parser.names)
        # 设置数据到plot_panel（参考CurveEditorWindow）
        self.plot_container.set_data(self.parser.names, self.parser.rotations, self.editor_panel.offsets)
        # 初始化MuJoCo model/data
        self.xml_content = self.parser.generate_mujoco_xml(frame_0=self.anim.pos[0, 0])
        xml_file_name = "human_skeleton.xml"
        with open(xml_file_name, "w") as f:
            f.write(self.xml_content)
        print("MuJoCo XML generated: human_skeleton.xml")
        
        self.viewer.set_model_data(self.model, self.data)
        self.viewer.cam.distance = 5  # 示例相机设置
        self.viewer.cam.azimuth = 135
        self.viewer.cam.elevation = 0.0
        self.load_model("human_skeleton.xml")  # 初始加载人类模型
        # 启动动画
        self.is_animating = True
        self.frame_idx = 0
        self.anim_timer.start()
        
    def on_apply_offsets(self):
        """
        应用偏移：保存偏移，更新rotations，重新计算anim，并重启动画。
        """
        if not self.parser or not self.anim:
            print("未加载BVH，无法应用偏移。")
            return

        # 保存偏移
        self.editor_panel.save_offsets()

        # 获取偏移并应用到rotations
        offsets = self.editor_panel.get_offsets()
        joint_offset = np.zeros((self.parser.rotations.shape[1], 3))
        for j in range(self.parser.rotations.shape[1]):
            for c in range(3):
                joint_offset[j, c] = offsets[(j, c)]
        new_rotations = self.parser.rotations + joint_offset  # 假设rotations是欧拉角

        # 重新后处理
        positions = np.copy(self.parser.positions)
        print("reset_to_zero: ",self.bvh_panel.reset_checkbox.isChecked())
        _quats, _positions, _offsets_arr, _parents = self.parser._MOTION_data_post_processing(
            new_rotations, positions, reset_to_zero=self.bvh_panel.reset_checkbox.isChecked()  # 不重置，以保留原设置
        )
        self.anim = Anim(_quats, _positions, _offsets_arr, _parents, self.parser.names)
        self.global_data = quat_fk(self.anim.quats, self.anim.pos, self.anim.parents)

        # 重置帧并继续动画
        self.frame_idx = 0


# 示例使用
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())