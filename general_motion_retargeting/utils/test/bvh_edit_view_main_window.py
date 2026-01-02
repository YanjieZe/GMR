import sys
import numpy as np
from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QApplication
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

        # 右侧叠加容器：绝对定位到viewer右侧
        self.overlay_container = QWidget(self.viewer)
        self.overlay_container.setObjectName("OverlayContainer")
        overlay_layout = QVBoxLayout(self.overlay_container)
        overlay_layout.setContentsMargins(10, 10, 10, 10)
        overlay_layout.setSpacing(10)
        self.overlay_container.setFixedWidth(400)  # 固定宽度
        self.overlay_container.setFixedHeight(400)  # 自适应高度
        self.overlay_container.move(self.viewer.width() - 410, 10)  # 初始位置（右侧上角）

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

        # 更新编辑面板
        self.editor_panel.update_joint_names(self.parser.names)
        # 设置数据到plot_panel（参考CurveEditorWindow）
        self.plot_container.set_data(self.parser.names, self.parser.rotations, self.editor_panel.offsets)
        # 初始化MuJoCo model/data
        self.xml_content = self.parser.generate_mujoco_xml(frame_0=self.anim.pos[0, 0])
        xml_file_name = "human_skeleton.xml"
        if True:
            with open(xml_file_name, "w") as f:
                f.write(self.xml_content)
            print("MuJoCo XML generated: human_skeleton.xml")
            self.model = mujoco.MjModel.from_xml_path(xml_file_name)
        else:
            self.model = mujoco.MjModel.from_xml_string(self.xml_content)
        self.data = mujoco.MjData(self.model)
        self.viewer.set_model_data(self.model, self.data)
        self.viewer.cam.distance = 5  # 示例相机设置
        self.viewer.cam.azimuth = 135
        self.viewer.cam.elevation = 0.0
        
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

    def update_animation(self):
        """
        更新动画帧：在viewer的render前设置qpos，并调用viewer.render。
        - 整合原mujoco_displayanimanim的animate_bvh逻辑，但适应QtViewer。
        """
        if not self.is_animating or not self.anim:
            return

        frames_len = self.anim.quats.shape[0]
        if self.frame_idx >= frames_len:
            self.frame_idx = 0  # 循环

        # 更新qpos和markers（类似原_draw_geom）
        for idx, name in enumerate(self.anim.bones):
            joint_id = mujoco.mj_name2id(self.viewer.model, mujoco.mjtObj.mjOBJ_JOINT, f"{name}_joint")
            if joint_id > 0:
                qpos_idx = self.viewer.model.jnt_qposadr[joint_id]
                self.viewer.data.qpos[qpos_idx : qpos_idx + 4] = self.anim.quats[self.frame_idx, idx]
                # 添加marker（使用viewer.add_marker）
                self.viewer.add_marker(
                    pos=self.global_data[1][self.frame_idx, idx],
                    mat=Rotation.from_quat(self.global_data[0][self.frame_idx, idx], scalar_first=True).as_matrix().flatten(),
                    label=name,
                    type=mujoco.mjtGeom.mjGEOM_ARROW,
                    size=[0.025, 0.025, 0.025],  # 示例大小
                    rgba=[1, 0, 0, 1]  # 示例颜色
                )
            else:  # Root
                self.viewer.data.qpos[0:3] = self.anim.pos[self.frame_idx, 0]
                self.viewer.data.qpos[3:7] = self.anim.quats[self.frame_idx, 0]
                self.viewer.add_marker(
                    pos=self.global_data[1][self.frame_idx, 0],
                    mat=Rotation.from_quat(self.global_data[0][self.frame_idx, 0], scalar_first=True).as_matrix().flatten(),
                    label=name
                )

        self.viewer.data.qvel[:] = 0  # 清零速度
        if hasattr(self, 'plot_container'):
            self.plot_container.update_current_frame(self.frame_idx)
        mujoco.mj_step(self.viewer.model, self.viewer.data)  # 模拟一步

        # 调用viewer.render更新画面
        self.viewer.render()

        self.frame_idx += 1

# 示例使用
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())