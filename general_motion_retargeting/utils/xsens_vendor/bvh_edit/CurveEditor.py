import sys
import numpy as np
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QLabel,
    QComboBox,
    QDial,
    QSlider,
    QPushButton,
    QGridLayout,
    QGroupBox,
    QLineEdit,
    QFileDialog,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from matplotlib.widgets import Cursor

channel_names = ["X", "Y", "Z"]

from PyQt6.QtCore import QThread, pyqtSignal
import threading  # 用于MuJoCo线程
import json
import os


class MujocoThread(QThread):
    finished = pyqtSignal()  # 信号：MuJoCo完成或停止

    def __init__(self, anim, parser, parent=None):
        super().__init__(parent)
        self.anim = anim
        self.parser = parser
        self.stop_flag = threading.Event()

    def run(self):
        # 在线程中运行MuJoCo显示
        from mujoco_xsens_bvh_view import mujoco_displayanimanim  # 延迟导入避免循环

        d = mujoco_displayanimanim(
            self.parser, self.anim
        )  # 假设bvh_file=None，使用预计算anim
        # d.anim = self.anim  # 注入预计算的Anim
        d._init_xml_data(save_flag=True)  # 使用内存XML
        try:
            d.animate_bvh()
        except Exception as e:
            print(f"MuJoCo error: {e}")
        finally:
            self.finished.emit()


class OffsetManager:
    """类用于读取、保存和解析 JSON 文件中的 offset 数据。
    数据格式：{ "joint_name": { "X": offset, "Y": offset, "Z": offset }, ... }
    """

    def __init__(self, default_path="offsets.json"):
        self.default_path = default_path
        self.offsets = self.load_offsets()

    def load_offsets(self, path=None):
        """从指定路径加载 offset。如果路径不存在，则初始化为全 0。"""
        path = path or self.default_path
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    data = json.load(f)
                return data
            except (json.JSONDecodeError, IOError) as e:
                print(f"加载 JSON 时出错: {e}. 初始化为全 0。")
        else:
            print(f"路径 {path} 不存在. 初始化为全 0。")
        return {}  # 返回空字典，后续在窗口中填充全 0

    def save_offsets(self, offsets, path):
        """保存 offset 到指定路径。"""
        try:
            with open(path, "w") as f:
                json.dump(offsets, f, indent=4)
            print(f"Offset 已保存至 {path}。")
        except IOError as e:
            print(f"保存 JSON 时出错: {e}。")

    def parse_to_window_format(self, joint_names, offsets_dict):
        """解析 JSON 数据到窗口的 offsets 字典格式 {(joint_idx, channel_idx): offset}。"""
        offsets = {}
        for j, joint in enumerate(joint_names):
            joint_data = offsets_dict.get(joint, {"X": 0.0, "Y": 0.0, "Z": 0.0})
            for c, channel in enumerate(channel_names):
                offsets[(j, c)] = joint_data.get(channel, 0.0)
        return offsets

    def format_for_save(self, offsets, joint_names):
        """将窗口 offsets 格式化为 JSON 保存格式。"""
        save_data = {}
        for j, joint in enumerate(joint_names):
            save_data[joint] = {
                channel_names[c]: offsets.get((j, c), 0.0) for c in range(3)
            }
        return save_data


class CurveEditorWindow(QMainWindow):
    def __init__(self, joint_names, data, scale=100.0, parser=None):
        super().__init__()
        self.parser = parser  # 传入BVHParser实例
        self.is_frozen = False
        self.mujoco_thread = None
        self.is_mujoco_running = False

        self.setWindowTitle("BVH Curve Editor (Independent Bias per Joint/Channel)")
        self.setGeometry(100, 100, 1200, 800)
        self.joint_num = data.shape[1]
        self.frame_num = data.shape[0]
        self.joint_names = joint_names
        self.data = data
        # 初始化偏移字典：{ (joint_idx, channel_idx): bias }
        self.offset_manager = OffsetManager(default_path="offsets.json")
        loaded_offsets = self.offset_manager.load_offsets()
        # self.offsets = {(j, c): 0.0 for j in range(self.joint_num) for c in range(3)}
        self.offsets = self.offset_manager.parse_to_window_format(
            joint_names, loaded_offsets
        )

        self.scale = scale

        # 当前选择
        self.selected_joint_idx = 0
        self.selected_channel_idx = 0

        # 中央widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # 控件组
        control_group = QGroupBox("Controls")
        control_layout = QGridLayout(control_group)

        # 关节选择
        self.joint_combo = QComboBox()
        self.joint_combo.addItems(self.joint_names)
        self.joint_combo.currentIndexChanged.connect(self.on_joint_changed)
        control_layout.addWidget(QLabel("Joint:"), 0, 0)
        control_layout.addWidget(self.joint_combo, 0, 1)

        # 通道选择
        self.channel_combo = QComboBox()
        self.channel_combo.addItems(channel_names)
        self.channel_combo.currentIndexChanged.connect(self.on_channel_changed)
        control_layout.addWidget(QLabel("Channel:"), 0, 2)
        control_layout.addWidget(self.channel_combo, 0, 3)

        # 偏移旋钮
        self.offset_dial = QDial()
        self.offset_dial.setRange(-1000, 1000)  # 范围-100到100，单位0.1
        self.offset_dial.setNotchesVisible(True)
        self.offset_dial.setWrapping(False)
        self.offset_dial.valueChanged.connect(self.on_offset_changed)
        self.offset_dial.setSingleStep(1)
        control_layout.addWidget(QLabel("Offset Knob:"), 1, 0)
        control_layout.addWidget(self.offset_dial, 1, 1, 1, 2)

        # 偏移值显示
        self.offset_label = QLabel(f"Offset: {self.offsets[(0, 0)]:.2f}")
        self.offset_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        control_layout.addWidget(self.offset_label, 1, 3)

        # 添加路径选择 UI
        self.path_edit = QLineEdit(self.offset_manager.default_path)
        self.path_edit.setToolTip("编辑或选择 JSON 文件路径")
        control_layout.addWidget(QLabel("JSON Path:"), 2, 0)
        control_layout.addWidget(self.path_edit, 2, 1, 1, 2)

        self.browse_button = QPushButton("Browse...")
        self.browse_button.clicked.connect(self.on_browse_clicked)
        control_layout.addWidget(self.browse_button, 2, 3)

        # 新增按钮
        self.apply_button = QPushButton("Apply and Preview")
        self.apply_button.clicked.connect(self.on_apply_preview)
        control_layout.addWidget(self.apply_button, 3, 0, 1, 4)

        layout.addWidget(control_group)

        # Matplotlib Figure和Canvas
        self.figure = Figure(figsize=(10, 6))
        self.canvas = FigureCanvas(self.figure)
        layout.addWidget(self.canvas)

        # 导航工具栏
        self.toolbar = NavigationToolbar(self.canvas, self)
        layout.addWidget(self.toolbar)

        # 初始化轴和绘图
        self.ax = self.figure.add_subplot(111)
        self.ax.set_title("Rotation Curve")
        self.ax.set_xlabel("Frame")
        self.ax.set_ylabel("Rotation Value")
        self.ax.grid(True)
        self.frames = np.arange(self.frame_num)

        # 初始绘图和旋钮设置
        self.update_plot()
        self.update_dial_from_offset()

        # 添加cursor
        self.cursor = Cursor(self.ax, useblit=True, color="red", linewidth=1)

    def freeze_ui(self):
        self.is_frozen = True
        self.joint_combo.setEnabled(False)
        self.channel_combo.setEnabled(False)
        self.offset_dial.setEnabled(False)
        self.apply_button.setEnabled(False)
        print("UI freezed")

    def unfreeze_ui(self):
        self.is_frozen = False
        self.joint_combo.setEnabled(True)
        self.channel_combo.setEnabled(True)
        self.offset_dial.setEnabled(True)
        self.apply_button.setEnabled(True)
        print("UI unfreezed")

    def on_browse_clicked(self):
        """触发文件选择对话框，更新路径文本框。"""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "选择或创建 JSON 文件",
            self.path_edit.text(),
            "JSON files (*.json);;All files (*)",
        )
        if file_path:
            self.path_edit.setText(file_path)

    def on_apply_preview(self):
        print("button press")
        """应用并预览：保存 offset 到指定路径，并执行预览逻辑（后续可扩展 MuJoCo）。"""
        save_path = self.path_edit.text()
        if not save_path:
            print("路径为空，无法保存。")
            return
        save_data = self.offset_manager.format_for_save(self.offsets, self.joint_names)
        self.offset_manager.save_offsets(save_data, save_path)
        print("json has saved: " + save_path)

        if self.is_frozen:
            return
        self.freeze_ui()
        # 完成解析并启动MuJoCo线程
        rotations = self.get_new_data()  # 获取当前调整数据
        print("rotations has add offset")
        positions = np.copy(self.parser.positions)
        _quats, _positions, _offsets, _parents = (
            self.parser._MOTION_data_post_processing(
                rotations, positions, reset_to_zero=True
            )
        )
        print("MOTION_data_post_processing")
        from BVHParser import Anim

        anim = Anim(_quats, _positions, _offsets, _parents, self.joint_names)
        print("anim prepared")
        self.mujoco_thread = MujocoThread(anim, self.parser, self)
        self.mujoco_thread.finished.connect(self.on_mujoco_finished)
        self.mujoco_thread.start()
        self.is_mujoco_running = True

    def get_channel_data(self):
        """获取当前选定关节和通道的数据，并应用偏移"""
        joint_data = self.data[:, self.selected_joint_idx, self.selected_channel_idx]
        current_offset = self.offsets[
            (self.selected_joint_idx, self.selected_channel_idx)
        ]
        return joint_data + current_offset

    def get_new_data(self):
        new_data = np.zeros_like(self.data)
        joint_offset = np.zeros((self.joint_num, 3))
        for i in range(self.joint_num):
            for j in range(3):
                joint_offset[i, j] = self.offsets[(i, j)]
        new_data = self.data + joint_offset
        return new_data

    def update_plot(self):
        """更新曲线图"""
        self.ax.clear()
        channel_data = self.get_channel_data()
        current_offset = self.offsets[
            (self.selected_joint_idx, self.selected_channel_idx)
        ]
        self.ax.plot(
            self.frames,
            channel_data,
            "b-",
            linewidth=1,
            label=f"{self.joint_names[self.selected_joint_idx]} {channel_names[self.selected_channel_idx]}",
        )
        self.ax.set_title(
            f"Curve: {self.joint_names[self.selected_joint_idx]} - {channel_names[self.selected_channel_idx]} (Offset: {current_offset:.2f})"
        )
        self.ax.set_xlabel("Frame")
        self.ax.set_ylabel("Rotation Value")
        self.ax.grid(True)
        self.ax.legend()
        self.canvas.draw()

    def update_dial_from_offset(self):
        """根据当前偏移更新旋钮位置"""
        current_offset = self.offsets[
            (self.selected_joint_idx, self.selected_channel_idx)
        ]
        dial_value = int(current_offset * self.scale)  # 转换为旋钮整数值
        self.offset_dial.blockSignals(True)  # 防止递归信号
        self.offset_dial.setValue(dial_value)
        self.offset_dial.blockSignals(False)
        self.offset_label.setText(f"Offset: {current_offset:.2f}")

    def on_joint_changed(self, idx):
        """关节选择变化"""
        self.selected_joint_idx = idx
        self.update_dial_from_offset()
        self.update_plot()

    def on_channel_changed(self, idx):
        """通道选择变化"""
        self.selected_channel_idx = idx
        self.update_dial_from_offset()
        self.update_plot()

    def on_offset_changed(self, value):
        """偏移旋钮变化：更新当前关节-通道的偏移并重绘"""
        # print("偏移旋钮变化")
        key = (self.selected_joint_idx, self.selected_channel_idx)
        self.offsets[key] = value / self.scale  # 转换为浮点
        # print("偏移旋钮变化"+f"Offset: {self.offsets[key]:.2f}")
        self.offset_label.setText(f"Offset: {self.offsets[key]:.2f}")
        self.update_plot()
        if self.is_mujoco_running:
            self.stop_mujoco()
            # 重新计算并重启（类似on_apply_preview逻辑）
            self.on_apply_preview()  # 复用逻辑，但需优化避免递归

    def stop_mujoco(self):
        if self.mujoco_thread:
            self.mujoco_thread.stop_flag.set()  # 自定义停止信号（需在MuJoCo循环中检查）
            self.mujoco_thread.wait()
            self.is_mujoco_running = False

    def on_mujoco_finished(self):
        self.unfreeze_ui()
        self.is_mujoco_running = False

class CurveEditorWindow_02(CurveEditorWindow):
    ...
    
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CurveEditorWindow()
    window.show()
    sys.exit(app.exec())
