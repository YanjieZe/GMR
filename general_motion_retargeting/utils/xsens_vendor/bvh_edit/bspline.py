import sys
import numpy as np
from scipy.interpolate import splprep, splev
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.patches import Circle
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QComboBox, QLabel
from PyQt6.QtCore import Qt

class InteractiveBSplinePyQt(QMainWindow):
    def __init__(self, joint_data, joint_names, degree=3):
        super().__init__()
        self.setWindowTitle("Interactive B-Spline Joint Editor")
        self.setGeometry(100, 100, 800, 800)
        
        # 数据假设：(frame_num, joint_num, 2)，随机生成示例
        self.joint_data = joint_data  # 形状: (frame_num, joint_num, 2)
        self.joint_names = joint_names
        self.degree = degree
        self.current_joint = 0  # 默认选择第一个关节
        self.dragging_point = None
        
        # 主布局
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # 下拉框选择关节
        self.joint_selector = QComboBox()
        self.joint_selector.addItems(self.joint_names)
        self.joint_selector.currentIndexChanged.connect(self.update_joint)
        layout.addWidget(QLabel("Select Joint:"))
        layout.addWidget(self.joint_selector)
        
        # Matplotlib画布
        self.fig, (self.ax_curve, self.ax_curvature) = plt.subplots(2, 1, figsize=(6, 8))
        self.canvas = FigureCanvas(self.fig)
        layout.addWidget(self.canvas)
        
        # 初始化控制点（从当前关节数据采样，例如每5帧取一个点）
        self.update_control_points()
        
        # 连接Matplotlib事件
        self.cid_press = self.fig.canvas.mpl_connect('button_press_event', self.on_press)
        self.cid_release = self.fig.canvas.mpl_connect('button_release_event', self.on_release)
        self.cid_motion = self.fig.canvas.mpl_connect('motion_notify_event', self.on_motion)
        
        self.plot_curve()

    def update_joint(self, index):
        self.current_joint = index
        self.update_control_points()
        self.plot_curve()

    def update_control_points(self):
        # 从关节数据中采样控制点（示例：均匀采样10个点）
        data = self.joint_data[:, self.current_joint, :]
        frame_num = data.shape[0]
        num_samples = min(10, frame_num)
        indices = np.linspace(0, frame_num - 1, num_samples, dtype=int)
        self.control_points = data[indices]

    def plot_curve(self):
        # 清空轴
        self.ax_curve.cla()
        self.ax_curvature.cla()
        
        # 生成B样条曲线
        if len(self.control_points) < self.degree + 1:
            self.ax_curve.text(0.5, 0.5, "Insufficient control points", ha='center')
            self.canvas.draw()
            return
        
        tck, u = splprep(self.control_points.T, k=self.degree, s=0)
        u_fine = np.linspace(0, 1, 1000)
        curve = splev(u_fine, tck)
        
        # 绘制曲线
        self.ax_curve.plot(curve[0], curve[1], 'b-', label='B-Spline')
        
        # 绘制控制点和控制多边形
        self.ax_curve.plot(self.control_points[:, 0], self.control_points[:, 1], 'r--', label='Control Polygon')
        self.control_circles = [Circle((x, y), 0.2, color='r', fill=False) for x, y in self.control_points]
        for circle in self.control_circles:
            self.ax_curve.add_patch(circle)
        
        self.ax_curve.legend()
        self.ax_curve.set_aspect('equal')
        
        # 计算并绘制曲率
        dx = np.gradient(curve[0])
        dy = np.gradient(curve[1])
        ddx = np.gradient(dx)
        ddy = np.gradient(dy)
        curvature = np.abs(dx * ddy - dy * ddx) / (dx**2 + dy**2)**1.5
        self.ax_curvature.plot(u_fine, curvature, 'g-')
        self.ax_curvature.set_ylim(0, np.max(curvature) * 1.1 if np.max(curvature) > 0 else 1)
        
        self.canvas.draw()

    def on_press(self, event):
        if event.inaxes != self.ax_curve:
            return
        for i, circle in enumerate(self.control_circles):
            if circle.contains(event)[0]:
                self.dragging_point = i
                break

    def on_motion(self, event):
        if self.dragging_point is None or event.inaxes != self.ax_curve:
            return
        self.control_points[self.dragging_point] = [event.xdata, event.ydata]
        self.control_circles[self.dragging_point].center = (event.xdata, event.ydata)
        self.plot_curve()

    def on_release(self, event):
        self.dragging_point = None

# 示例运行
if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # 示例数据：frame_num=100, joint_num=5, dim=2
    frame_num, joint_num, dim = 100, 5, 2
    joint_data = np.random.rand(frame_num, joint_num, dim) * 10
    joint_names = [f"Joint {i+1}" for i in range(joint_num)]
    
    window = InteractiveBSplinePyQt(joint_data, joint_names, degree=3)
    window.show()
    sys.exit(app.exec())