from PyQt6.QtWidgets import QGroupBox, QGridLayout, QLabel, QComboBox, QDial, QLineEdit, QPushButton, QFileDialog
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

# 导入模块1的可折叠面板
from collapsible_panel import CollapsiblePanel  # 假设文件名为collapsible_panel.py

# 从原代码导入OffsetManager和channel_names
from curve_editor_window import OffsetManager, channel_names  # 假设原CurveEditorWindow文件

class CurveEditorPanel(CollapsiblePanel):
    """
    曲线编辑面板类，集成原CurveEditorWindow的控件（无Matplotlib图）。
    - 使用可折叠面板，叠加到MuJoCo viewer右侧。
    - 包含关节/通道选择、偏移旋钮、JSON路径和应用按钮。
    - 继承OffsetManager进行偏移管理。
    """
    def __init__(self, joint_names=None, parent=None):
        """
        初始化曲线编辑面板。
        参数：
        - joint_names: 关节名称列表（加载BVH后设置）。
        - parent: 父部件（可选）。
        """
        super().__init__(title="Curve Editor Controls", parent=parent)
        self.joint_names = joint_names or []  # 初始为空，加载BVH后更新
        self.offset_manager = OffsetManager(default_path="offsets.json")
        self.offsets = {}  # {(joint_idx, channel_idx): offset}
        self.selected_joint_idx = 0
        self.selected_channel_idx = 0
        self.scale = 100.0  # 旋钮缩放因子，与原一致

        # 内容布局：网格布局
        grid_layout = QGridLayout()
        grid_layout.setContentsMargins(10, 10, 10, 10)
        grid_layout.setSpacing(5)

        # 关节选择
        row = 0
        grid_layout.addWidget(QLabel("Joint:"), row, 0)
        self.joint_combo = QComboBox()
        self.joint_combo.addItems(self.joint_names)  # 初始为空
        self.joint_combo.currentIndexChanged.connect(self.on_joint_changed)
        grid_layout.addWidget(self.joint_combo, row, 1, 1, 2)

        # 通道选择
        row += 1
        grid_layout.addWidget(QLabel("Channel:"), row, 0)
        self.channel_combo = QComboBox()
        self.channel_combo.addItems(channel_names)
        self.channel_combo.currentIndexChanged.connect(self.on_channel_changed)
        grid_layout.addWidget(self.channel_combo, row, 1, 1, 2)

        # 偏移旋钮
        row += 1
        grid_layout.addWidget(QLabel("Offset Knob:"), row, 0)
        self.offset_dial = QDial()
        self.offset_dial.setRange(-1000, 1000)  # 与原一致
        self.offset_dial.setNotchesVisible(True)
        self.offset_dial.valueChanged.connect(self.on_offset_changed)
        grid_layout.addWidget(self.offset_dial, row, 1, 1, 2)

        # 偏移值显示
        self.offset_label = QLabel("Offset: 0.00")
        self.offset_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        grid_layout.addWidget(self.offset_label, row, 3)

        # JSON路径
        row += 1
        grid_layout.addWidget(QLabel("JSON Path:"), row, 0)
        self.path_edit = QLineEdit(self.offset_manager.default_path)
        grid_layout.addWidget(self.path_edit, row, 1, 1, 2)
        self.browse_json_button = QPushButton("Browse...")
        self.browse_json_button.clicked.connect(self.on_browse_json)
        grid_layout.addWidget(self.browse_json_button, row, 3)

        # 应用按钮
        row += 1
        self.apply_button = QPushButton("Apply Offsets")
        self.apply_button.setToolTip("应用偏移并更新MuJoCo动画")
        grid_layout.addWidget(self.apply_button, row, 0, 1, 4)

        # 添加布局到内容区域
        self.add_layout(grid_layout)

        # 初始禁用（无关节时）
        self.set_enabled(False)

    def set_enabled(self, enabled):
        """
        启用/禁用面板控件。
        参数：
        - enabled: 布尔值。
        """
        self.joint_combo.setEnabled(enabled)
        self.channel_combo.setEnabled(enabled)
        self.offset_dial.setEnabled(enabled)
        self.apply_button.setEnabled(enabled)

    def update_joint_names(self, joint_names):
        """
        更新关节名称列表，并重置偏移。
        参数：
        - joint_names: 新关节名称列表。
        """
        self.joint_names = joint_names
        self.joint_combo.clear()
        self.joint_combo.addItems(joint_names)
        loaded_offsets = self.offset_manager.load_offsets(self.path_edit.text())
        self.offsets = self.offset_manager.parse_to_window_format(joint_names, loaded_offsets)
        self.set_enabled(True)
        self.update_dial_from_offset()

    def on_browse_json(self):
        """
        触发JSON文件选择对话框，更新路径并加载偏移。
        """
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "选择或创建JSON文件",
            self.path_edit.text(),
            "JSON files (*.json);;All files (*)"
        )
        if file_path:
            self.path_edit.setText(file_path)
            self.offsets = self.offset_manager.parse_to_window_format(
                self.joint_names, self.offset_manager.load_offsets(file_path)
            )
            self.update_dial_from_offset()

    def on_joint_changed(self, idx):
        """
        关节选择变化：更新旋钮和标签。
        """
        self.selected_joint_idx = idx
        self.update_dial_from_offset()
    def on_channel_changed(self, idx):
        """
        通道选择变化：更新旋钮和标签。
        """
        self.selected_channel_idx = idx
        self.update_dial_from_offset()

    def on_offset_changed(self, value):
        """
        偏移旋钮变化：更新偏移字典和标签。
        """
        key = (self.selected_joint_idx, self.selected_channel_idx)
        self.offsets[key] = value / self.scale
        self.offset_label.setText(f"Offset: {self.offsets[key]:.2f}")

    def update_dial_from_offset(self):
        """
        根据当前偏移更新旋钮和标签。
        """
        if not self.joint_names:
            return
        key = (self.selected_joint_idx, self.selected_channel_idx)
        current_offset = self.offsets.get(key, 0.0)
        dial_value = int(current_offset * self.scale)
        self.offset_dial.blockSignals(True)
        self.offset_dial.setValue(dial_value)
        self.offset_dial.blockSignals(False)
        self.offset_label.setText(f"Offset: {current_offset:.2f}")
        self.update_plot()
    def update_plot(self):

        # 通知主窗口更新plot_panel（假设主窗口有update_plot方法，或直接访问）
        if self.parent() and hasattr(self.parent().parent(), 'plot_container'):  # parent是overlay_container，grandparent是NewMainWindow
            main_window = self.parent().parent()
            main_window.plot_container.update_selection(self.selected_joint_idx, self.selected_channel_idx)
            main_window.plot_container.update_plot()  # 确保重绘

    def get_offsets(self):
        """
        获取当前偏移字典。
        返回：{(joint_idx, channel_idx): offset}
        """
        return self.offsets

    def save_offsets(self):
        """
        保存偏移到当前JSON路径。
        """
        save_data = self.offset_manager.format_for_save(self.offsets, self.joint_names)
        self.offset_manager.save_offsets(save_data, self.path_edit.text())