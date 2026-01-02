from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QHBoxLayout
from PyQt6.QtCore import Qt

class CollapsiblePanel(QWidget):
    """
    可折叠面板类，用于集成多个控件组。
    - 标题按钮：点击切换折叠状态。
    - 内容区域：容纳子控件，支持动态展开/折叠。
    - 使用QVBoxLayout管理整体布局，确保自适应。
    """
    def __init__(self, title="", parent=None):
        """
        初始化可折叠面板。
        参数：
        - title: 面板标题字符串。
        - parent: 父部件（可选）。
        """
        super().__init__(parent)
        self.setObjectName("CollapsiblePanel")  # 用于样式表标识

        # 主布局：垂直布局，包含标题和内容
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)  # 无边距
        self.main_layout.setSpacing(0)  # 无间距

        # 标题布局：水平布局，包含展开图标和标题
        self.title_layout = QHBoxLayout()
        self.title_layout.setContentsMargins(5, 5, 5, 5)  # 轻微边距以美观

        # 展开图标标签：使用文本模拟图标 (+ 或 -)
        self.toggle_icon = QLabel("+")  # 初始为折叠状态
        self.toggle_icon.setFixedSize(20, 20)  # 固定大小
        self.title_layout.addWidget(self.toggle_icon)

        # 标题按钮：无边框，点击触发折叠切换
        self.toggle_button = QPushButton(title)
        self.toggle_button.setFlat(True)  # 无边框按钮
        self.toggle_button.clicked.connect(self.toggle_content)  # 连接点击信号
        self.title_layout.addWidget(self.toggle_button)
        self.title_layout.addStretch()  # 右侧拉伸填充

        # 添加标题布局到主布局
        self.main_layout.addLayout(self.title_layout)

        # 内容容器：初始隐藏
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)  # 内容垂直布局
        self.content_layout.setContentsMargins(10, 5, 10, 5)  # 内容边距
        self.main_layout.addWidget(self.content_widget)
        self.content_widget.hide()  # 初始折叠

        self.is_expanded = False  # 初始状态：折叠

    def add_widget(self, widget):
        """
        添加子控件到内容区域。
        参数：
        - widget: 要添加的QWidget实例。
        """
        self.content_layout.addWidget(widget)

    def add_layout(self, layout):
        """
        添加子布局到内容区域。
        参数：
        - layout: 要添加的QLayout实例。
        """
        self.content_layout.addLayout(layout)

    def toggle_content(self):
        """
        切换内容区域的可见性，并更新图标和大小。
        - 如果展开，显示内容并调整窗口大小。
        - 如果折叠，隐藏内容。
        """
        if self.is_expanded:
            self.content_widget.hide()  # 隐藏内容
            self.toggle_icon.setText("+")  # 更新图标为 +
            self.is_expanded = False
        else:
            self.content_widget.show()  # 显示内容
            self.toggle_icon.setText("-")  # 更新图标为 -
            self.is_expanded = True
        # 动态调整父窗口大小（如果需要，可通过信号通知主窗口）
        self.adjustSize()
        if self.parent():
            self.parent().adjustSize()