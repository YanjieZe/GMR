from PyQt6.QtWidgets import QGridLayout, QLabel, QLineEdit, QPushButton, QComboBox, QFileDialog
from collapsible_panel import CollapsiblePanel  # 假设文件名为collapsible_panel.py

class RetargetingSettingsPanel(CollapsiblePanel):
    """
    Retargeting设置面板类，用于pkl文件路径选择和机器人型号选择。
    - 可折叠，便于集成到overlay_container。
    - pkl路径：QLineEdit + QPushButton，支持浏览保存。
    - 机器人型号：QComboBox，默认"Q1"。
    """
    def __init__(self, parent=None):
        """
        初始化Retargeting设置面板。
        参数：
        - parent: 父部件（可选）。
        """
        super().__init__(title="Retargeting Settings", parent=parent)

        # 内容布局：网格布局
        grid_layout = QGridLayout()
        grid_layout.setContentsMargins(10, 10, 10, 10)
        grid_layout.setSpacing(5)

        # pkl文件路径选择
        row = 0
        grid_layout.addWidget(QLabel("PKL File:"), row, 0)
        self.pkl_path_edit = QLineEdit("default_retarget.pkl")  # 默认路径
        self.pkl_path_edit.setToolTip("选择或保存pkl文件路径")
        grid_layout.addWidget(self.pkl_path_edit, row, 1)
        self.browse_pkl_button = QPushButton("Browse...")
        self.browse_pkl_button.clicked.connect(self.on_browse_pkl)
        grid_layout.addWidget(self.browse_pkl_button, row, 2)

        # 机器人型号下拉
        row += 1
        grid_layout.addWidget(QLabel("Robot Model:"), row, 0)
        self.robot_combo = QComboBox()
        self.robot_combo.addItems(["unitree_g1", "unitree_h1_2", "Q1", "X1"])
        self.robot_combo.setCurrentText("Q1")  # 默认
        self.robot_combo.currentIndexChanged.connect(self.on_robot_changed)  # 连接变化信号
        grid_layout.addWidget(self.robot_combo, row, 1, 1, 2)

        # 添加布局到内容区域
        self.add_layout(grid_layout)

    def on_browse_pkl(self):
        """
        触发pkl文件选择对话框，更新路径文本框。
        - 支持保存/打开pkl文件。
        """
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "选择或创建PKL文件",
            self.pkl_path_edit.text(),
            "PKL files (*.pkl);;All files (*)"
        )
        if file_path:
            self.pkl_path_edit.setText(file_path)

    def on_robot_changed(self, idx):
        """
        机器人型号变化：可触发主窗口重新加载对应XML（通过信号）。
        """
        print(f"Selected robot: {self.robot_combo.currentText()}")
        # 可emit信号通知主窗口重新加载模型
        if self.parent() and hasattr(self.parent().parent(), 'on_mode_toggled'):
            main_window = self.parent().parent()
            if main_window.mode_switch.isChecked():
                main_window.on_mode_toggled(True)  # 重新加载机器人模型