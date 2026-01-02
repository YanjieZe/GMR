import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QPushButton, QComboBox, QLineEdit
from PyQt5.QtGui import QPainter, QColor
from PyQt5.QtCore import Qt

class CanvasWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAutoFillBackground(True)  # 启用背景填充

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(200, 200, 255))  # 填充背景颜色作为示例画布
        # 在此处添加自定义绘图逻辑，例如绘制线条或图像
        painter.setPen(QColor(0, 0, 0))
        painter.drawText(self.rect(), Qt.AlignCenter, "这是一个铺满UI的画布")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # 确保画布随窗口大小变化而重绘
        self.update()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyQt画布叠加控件示例")
        self.resize(800, 600)

        # 创建画布并设置为中央部件
        self.canvas = CanvasWidget(self)
        self.setCentralWidget(self.canvas)

        # 在画布上叠加按钮（使用绝对定位）
        self.button = QPushButton("点击我", self.canvas)
        self.button.setGeometry(600, 500, 150, 50)  # 设置位置和大小
        self.button.clicked.connect(self.on_button_clicked)

        # 在画布上方叠加下拉选择控件
        self.combo_box = QComboBox(self.canvas)
        self.combo_box.addItems(["选项1", "选项2", "选项3"])  # 添加示例选项
        self.combo_box.setGeometry(600, 20, 150, 30)  # 放置在顶部右侧
        self.combo_box.currentIndexChanged.connect(self.on_combo_changed)

        # 在画布上方叠加文本输入控件
        self.line_edit = QLineEdit(self.canvas)
        self.line_edit.setPlaceholderText("请输入数据")  # 设置占位符文本
        self.line_edit.setGeometry(600, 60, 150, 30)  # 放置在下拉控件下方
        self.line_edit.textChanged.connect(self.on_text_changed)

    def on_button_clicked(self):
        print("按钮被点击")

    def on_combo_changed(self, index):
        print(f"下拉选项更改为: {self.combo_box.currentText()}")

    def on_text_changed(self, text):
        print(f"输入文本更改为: {text}")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # 调整按钮位置以保持相对位置（可选）
        self.button.move(self.canvas.width() - 200, self.canvas.height() - 100)
        # 调整下拉控件和输入控件位置，保持在顶部右侧
        self.combo_box.move(self.canvas.width() - 200, 20)
        self.line_edit.move(self.canvas.width() - 200, 60)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())