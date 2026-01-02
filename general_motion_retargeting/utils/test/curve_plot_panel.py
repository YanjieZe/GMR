from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.widgets import Cursor
import numpy as np
from collapsible_panel import CollapsiblePanel
# 假设channel_names已定义
channel_names = ["X", "Y", "Z"]

class CurvePlotPanel(CollapsiblePanel):
    """
    可折叠曲线绘制面板类，参考CurveEditorWindow的Matplotlib部分。
    - 包含图表、导航工具栏和游标。
    - 支持外部更新关节、通道和偏移数据。
    - 无独立控件，只显示曲线。
    """
    def __init__(self, title="Channel Curve Plot", parent=None):
        """
        初始化曲线绘制面板。
        参数：
        - title: 面板标题。
        - parent: 父部件。
        """
        super().__init__(title=title, parent=parent)

        # 初始化数据（外部设置）
        self.data = None  # 完整数据 (frame_num, joint_num, 3)
        self.offsets = {}  # {(joint_idx, channel_idx): offset}
        self.selected_joint_idx = 0
        self.selected_channel_idx = 0
        self.joint_names = []
        self.frames = None
        self.current_frame = 0  # 当前动画帧（可选，用于垂直线）

        # Matplotlib Figure和Canvas
        self.figure = Figure(figsize=(8, 4))  # 调整大小以适合下半部分
        self.canvas = FigureCanvas(self.figure)
        self.add_widget(self.canvas)  # 添加到内容区域

        # 导航工具栏
        self.toolbar = NavigationToolbar(self.canvas, self)
        self.add_widget(self.toolbar)

        # 初始化轴
        self.ax = self.figure.add_subplot(111)
        self.ax.set_title("Rotation Curve")
        self.ax.set_xlabel("Frame")
        self.ax.set_ylabel("Rotation Value")
        self.ax.grid(True)

        # 添加cursor（水平/垂直线）
        self.cursor = Cursor(self.ax, useblit=True, color="red", linewidth=1)

        # 初始折叠
        self.toggle_content()  # 可选初始展开

    def set_data(self, joint_names, data, offsets):
        """
        设置数据：关节名称、原始数据和偏移字典。
        参数：
        - joint_names: 关节列表。
        - data: np.array (frame_num, joint_num, 3)
        - offsets: 偏移字典。
        """
        self.joint_names = joint_names
        self.data = data
        self.offsets = offsets
        self.frames = np.arange(data.shape[0]) if data is not None else None
        self.update_plot()

    def update_selection(self, joint_idx, channel_idx):
        """
        更新选择的关节和通道，并重绘。
        参数：
        - joint_idx: 关节索引。
        - channel_idx: 通道索引。
        """
        self.selected_joint_idx = joint_idx
        self.selected_channel_idx = channel_idx
        self.update_plot()

    def update_current_frame(self, frame_idx):
        """
        更新当前帧指示（垂直线）。
        参数：
        - frame_idx: 当前动画帧。
        """
        self.current_frame = frame_idx
        self.update_plot()  # 重绘以更新垂直线

    def update_plot(self):
        """
        更新曲线图，参考CurveEditorWindow。
        - 绘制应用偏移后的曲线。
        - 添加当前帧垂直线（可选）。
        """
        if self.data is None or not self.joint_names:
            return  # 无数据时跳过

        self.ax.clear()
        channel_data = self.get_channel_data()
        current_offset = self.offsets.get((self.selected_joint_idx, self.selected_channel_idx), 0.0)
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

        # 添加当前帧垂直线（可选增强）
        if self.frames is not None:
            self.ax.axvline(x=self.current_frame, color='green', linestyle='--', label='Current Frame')
            self.ax.legend()

        self.canvas.draw()

    def get_channel_data(self):
        """
        获取当前关节/通道的数据，并应用偏移。
        参考CurveEditorWindow。
        """
        joint_data = self.data[:, self.selected_joint_idx, self.selected_channel_idx]
        current_offset = self.offsets.get((self.selected_joint_idx, self.selected_channel_idx), 0.0)
        return joint_data + current_offset