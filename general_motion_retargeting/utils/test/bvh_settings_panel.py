from PyQt6.QtWidgets import QGroupBox, QGridLayout, QLabel, QLineEdit, QPushButton, QDoubleSpinBox, QSpinBox, QCheckBox, QFileDialog
from PyQt6.QtCore import Qt

# 导入模块1的可折叠面板
from collapsible_panel import CollapsiblePanel  # 假设文件名为 collapsible_panel.py

class BVHSettingsPanel(CollapsiblePanel):
    """
    BVH设置面板类，集成新增的BVH配置控件。
    - 使用可折叠面板，便于叠加到主窗口右侧。
    - 包含文件路径选择、scale、start、end、reset_to_zero和加载按钮。
    """
    def __init__(self, parent=None):
        """
        初始化BVH设置面板。
        参数：
        - parent: 父部件（可选）。
        """
        super().__init__(title="BVH Settings", parent=parent)

        # 内容布局：网格布局，便于对齐标签和控件
        grid_layout = QGridLayout()
        grid_layout.setContentsMargins(10, 10, 10, 10)  # 边距
        grid_layout.setSpacing(5)  # 间距

        # BVH文件路径
        row = 0
        grid_layout.addWidget(QLabel("BVH File:"), row, 0)
        self.bvh_path_edit = QLineEdit()
        self.bvh_path_edit.setToolTip("BVH文件路径")
        grid_layout.addWidget(self.bvh_path_edit, row, 1)
        self.browse_bvh_button = QPushButton("Browse...")
        self.browse_bvh_button.clicked.connect(self.on_browse_bvh)  # 连接浏览信号
        grid_layout.addWidget(self.browse_bvh_button, row, 2)

        # Scale
        row += 1
        grid_layout.addWidget(QLabel("Scale:"), row, 0)
        self.scale_spin = QDoubleSpinBox()
        self.scale_spin.setRange(0.001, 10.0)  # 合理范围
        self.scale_spin.setSingleStep(0.001)  # 步长
        self.scale_spin.setValue(0.01)  # 默认值
        self.scale_spin.setToolTip("BVH缩放因子")
        grid_layout.addWidget(self.scale_spin, row, 1, 1, 2)

        # Start Frame
        row += 1
        grid_layout.addWidget(QLabel("Start Frame:"), row, 0)
        self.start_spin = QSpinBox()
        self.start_spin.setRange(0, 100000)  # 假设最大帧数
        self.start_spin.setValue(0)  # 默认
        self.start_spin.setToolTip("起始帧号")
        grid_layout.addWidget(self.start_spin, row, 1, 1, 2)

        # End Frame
        row += 1
        grid_layout.addWidget(QLabel("End Frame:"), row, 0)
        self.end_spin = QSpinBox()
        self.end_spin.setRange(0, 100000)
        self.end_spin.setValue(0)  # 默认0，表示到结束
        self.end_spin.setToolTip("结束帧号 (0 表示到文件结束)")
        grid_layout.addWidget(self.end_spin, row, 1, 1, 2)

        # Reset to Zero
        row += 1
        self.reset_checkbox = QCheckBox("Reset to Zero")
        self.reset_checkbox.setChecked(False)  # 默认未选中
        self.reset_checkbox.setToolTip("重置位移和Z轴旋转为零")
        grid_layout.addWidget(self.reset_checkbox, row, 0, 1, 3)

        # 加载按钮
        row += 1
        self.load_button = QPushButton("Load BVH")
        self.load_button.setToolTip("加载BVH文件并解析")
        grid_layout.addWidget(self.load_button, row, 0, 1, 3)

        # 添加布局到内容区域
        self.add_layout(grid_layout)

    def on_browse_bvh(self):
        """
        触发BVH文件选择对话框，更新路径文本框。
        """
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择BVH文件",
            "",
            "BVH files (*.bvh);;All files (*)"
        )
        if file_path:
            self.bvh_path_edit.setText(file_path)