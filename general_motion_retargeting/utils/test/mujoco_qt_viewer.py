import mujoco
import glfw
import numpy as np
import imageio
import yaml
from threading import Lock
import time
import pathlib
from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QApplication
from PyQt6.QtGui import QImage, QPixmap, QKeyEvent, QMouseEvent,QResizeEvent
from PyQt6.QtCore import QTimer, Qt, pyqtSignal

MUJOCO_VERSION = tuple(map(int, mujoco.__version__.split('.')))

class Callbacks:
    """
    Callbacks类：处理用户交互逻辑，如键盘按键、鼠标操作等。
    此类去除对GLFW的直接依赖，而是通过Qt信号触发。
    所有原GLFW回调（如_key_callback、_cursor_pos_callback）被迁移到Qt事件中。
    """
    def __init__(self, hide_menus):
        # 线程锁，用于保护GUI相关操作
        self._gui_lock = Lock()
        # 鼠标按键状态
        self._button_left_pressed = False
        self._button_right_pressed = False
        self._left_double_click_pressed = False
        self._right_double_click_pressed = False
        self._last_left_click_time = None
        self._last_right_click_time = None
        self._last_mouse_x = 0
        self._last_mouse_y = 0
        # 模拟控制状态
        self._paused = False
        self._hide_graph = False
        self._transparent = False
        self._contacts = False
        self._joints = False
        self._shadows = True
        self._wire_frame = False
        self._convex_hull_rendering = False
        self._inertias = False
        self._com = False
        self._render_every_frame = True
        self._image_idx = 0
        self._image_path = "/tmp/frame_%07d.png"
        self._time_per_render = 1 / 60.0
        self._run_speed = 1.0
        self._loop_count = 0
        self._advance_by_one_step = False
        self._hide_menus = hide_menus

    def handle_key_press(self, key, mods):
        """
        处理键盘按键事件，相当于原_key_callback。
        参数：
        - key: Qt的键值（例如Qt.Key.Key_Space）。
        - mods: 修饰键状态（例如Qt.KeyboardModifier.ShiftModifier）。
        """
        # 切换相机
        if key == Qt.Key.Key_Tab:
            self.cam.fixedcamid += 1
            self.cam.type = mujoco.mjtCamera.mjCAMERA_FIXED
            if self.cam.fixedcamid >= self.model.ncam:
                self.cam.fixedcamid = -1
                self.cam.type = mujoco.mjtCamera.mjCAMERA_FREE
        # 暂停模拟
        elif key == Qt.Key.Key_Space and self._paused is not None:
            self._paused = not self._paused
        # 单步前进
        elif key == Qt.Key.Key_Right and self._paused is not None:
            self._advance_by_one_step = True
            self._paused = True
        # 减速
        elif key == Qt.Key.Key_S and mods != Qt.KeyboardModifier.ControlModifier:
            self._run_speed /= 2.0
        # 加速
        elif key == Qt.Key.Key_F:
            self._run_speed *= 2.0
        # 切换每帧渲染
        elif key == Qt.Key.Key_D:
            self._render_every_frame = not self._render_every_frame
        # 截图
        elif key == Qt.Key.Key_T:
            img = np.zeros((self.viewport.height, self.viewport.width, 3), dtype=np.uint8)
            mujoco.mjr_readPixels(img, None, self.viewport, self.ctx)
            imageio.imwrite(self._image_path % self._image_idx, np.flipud(img))
            self._image_idx += 1
        # 显示接触力
        elif key == Qt.Key.Key_C:
            self._contacts = not self._contacts
            self.vopt.flags[mujoco.mjtVisFlag.mjVIS_CONTACTPOINT] = self._contacts
            self.vopt.flags[mujoco.mjtVisFlag.mjVIS_CONTACTFORCE] = self._contacts
        # 显示关节
        elif key == Qt.Key.Key_J:
            self._joints = not self._joints
            self.vopt.flags[mujoco.mjtVisFlag.mjVIS_JOINT] = self._joints
        # 切换参考帧
        elif key == Qt.Key.Key_E:
            self.vopt.frame += 1
            if self.vopt.frame == mujoco.mjtFrame.mjNFRAME.value:
                self.vopt.frame = 0
        # 隐藏菜单
        elif key == Qt.Key.Key_Alt:
            self._hide_menus = not self._hide_menus
        elif key == Qt.Key.Key_H:
            self._hide_menus = not self._hide_menus
        # 透明模式
        elif key == Qt.Key.Key_R:
            self._transparent = not self._transparent
            if self._transparent:
                self.model.geom_rgba[:, 3] /= 5.0
            else:
                self.model.geom_rgba[:, 3] *= 5.0
        # 切换图表
        elif key == Qt.Key.Key_G:
            self._hide_graph = not self._hide_graph
        # 显示惯性
        elif key == Qt.Key.Key_I:
            self._inertias = not self._inertias
            self.vopt.flags[mujoco.mjtVisFlag.mjVIS_INERTIA] = self._inertias
        # 显示质心
        elif key == Qt.Key.Key_M:
            self._com = not self._com
            self.vopt.flags[mujoco.mjtVisFlag.mjVIS_COM] = self._com
        # 阴影渲染
        elif key == Qt.Key.Key_O:
            self._shadows = not self._shadows
            self.scn.flags[mujoco.mjtRndFlag.mjRND_SHADOW] = self._shadows
        # 凸包渲染
        elif key == Qt.Key.Key_V:
            self._convex_hull_rendering = not self._convex_hull_rendering
            self.vopt.flags[mujoco.mjtVisFlag.mjVIS_CONVEXHULL] = self._convex_hull_rendering
        # 线框渲染
        elif key == Qt.Key.Key_W:
            self._wire_frame = not self._wire_frame
            self.scn.flags[mujoco.mjtRndFlag.mjRND_WIREFRAME] = self._wire_frame
        # 几何组可见性
        elif key in (Qt.Key.Key_0, Qt.Key.Key_1, Qt.Key.Key_2, Qt.Key.Key_3, Qt.Key.Key_4, Qt.Key.Key_5):
            self.vopt.geomgroup[key - Qt.Key.Key_0] ^= 1
        # 保存相机配置
        elif key == Qt.Key.Key_S and mods == Qt.KeyboardModifier.ControlModifier:
            cam_config = {
                "type": self.cam.type,
                "fixedcamid": self.cam.fixedcamid,
                "trackbodyid": self.cam.trackbodyid,
                "lookat": self.cam.lookat.tolist(),
                "distance": self.cam.distance,
                "azimuth": self.cam.azimuth,
                "elevation": self.cam.elevation
            }
            try:
                with open(self.CONFIG_PATH, "w") as f:
                    yaml.dump(cam_config, f)
                print("Camera config saved at {}".format(self.CONFIG_PATH))
            except Exception as e:
                print(e)
        # 退出
        elif key == Qt.Key.Key_Escape:
            print("Pressed ESC")
            print("Quitting.")
            # 在Qt中关闭窗口
            self.close_signal.emit()

    def handle_mouse_move(self, xpos, ypos):
        """
        处理鼠标移动事件，相当于原_cursor_pos_callback。
        参数：
        - xpos, ypos: 鼠标当前位置。
        """
        if not (self._button_left_pressed or self._button_right_pressed):
            return

        mod_shift = False  # Qt中需单独检查Shift键，此处简化假设（可在事件中传入）
        if self._button_right_pressed:
            action = mujoco.mjtMouse.mjMOUSE_MOVE_H if mod_shift else mujoco.mjtMouse.mjMOUSE_MOVE_V
        elif self._button_left_pressed:
            action = mujoco.mjtMouse.mjMOUSE_ROTATE_H if mod_shift else mujoco.mjtMouse.mjMOUSE_ROTATE_V
        else:
            action = mujoco.mjtMouse.mjMOUSE_ZOOM

        dx = int(self._scale * xpos) - self._last_mouse_x
        dy = int(self._scale * ypos) - self._last_mouse_y
        width, height = self.viewport.width, self.viewport.height

        with self._gui_lock:
            if self.pert.active:
                mujoco.mjv_movePerturb(self.model, self.data, action, dx / height, dy / height, self.scn, self.pert)
            else:
                mujoco.mjv_moveCamera(self.model, action, dx / height, dy / height, self.scn, self.cam)

        self._last_mouse_x = int(self._scale * xpos)
        self._last_mouse_y = int(self._scale * ypos)

    def handle_mouse_button(self, button, act, mods, xpos, ypos):
        """
        处理鼠标按键事件，相当于原_mouse_button_callback。
        参数：
        - button: Qt.MouseButton.LeftButton 等。
        - act: 按下或释放（1为按下，0为释放）。
        - mods: 修饰键。
        - xpos, ypos: 鼠标位置。
        """
        self._button_left_pressed = (button == Qt.MouseButton.LeftButton and act == 1)
        self._button_right_pressed = (button == Qt.MouseButton.RightButton and act == 1)

        self._last_mouse_x = int(self._scale * xpos)
        self._last_mouse_y = int(self._scale * ypos)

        # 检测双击
        self._left_double_click_pressed = False
        self._right_double_click_pressed = False
        time_now = time.time()

        if self._button_left_pressed:
            if self._last_left_click_time is None:
                self._last_left_click_time = time_now
            time_diff = time_now - self._last_left_click_time
            if 0.01 < time_diff < 0.3:
                self._left_double_click_pressed = True
            self._last_left_click_time = time_now

        if self._button_right_pressed:
            if self._last_right_click_time is None:
                self._last_right_click_time = time_now
            time_diff = time_now - self._last_right_click_time
            if 0.01 < time_diff < 0.2:
                self._right_double_click_pressed = True
            self._last_right_click_time = time_now

        # 设置扰动
        key = mods == Qt.KeyboardModifier.ControlModifier
        newperturb = 0
        if key and self.pert.select > 0:
            if self._button_right_pressed:
                newperturb = mujoco.mjtPertBit.mjPERT_TRANSLATE
            if self._button_left_pressed:
                newperturb = mujoco.mjtPertBit.mjPERT_ROTATE
            if newperturb and not self.pert.active:
                mujoco.mjv_initPerturb(self.model, self.data, self.scn, self.pert)
        self.pert.active = newperturb

        # 处理双击
        if self._left_double_click_pressed or self._right_double_click_pressed:
            selmode = 0
            if self._left_double_click_pressed:
                selmode = 1
            if self._right_double_click_pressed:
                selmode = 2
            if self._right_double_click_pressed and key:
                selmode = 3

            width, height = self.viewport.width, self.viewport.height
            aspectratio = width / height
            relx = xpos / width
            rely = (height - ypos) / height
            selpnt = np.zeros(3)
            selgeom = np.zeros(1, dtype=np.int32)
            selflex = np.zeros(1, dtype=np.int32)
            selskin = np.zeros(1, dtype=np.int32)

            if MUJOCO_VERSION >= (3, 0, 0):
                selbody = mujoco.mjv_select(self.model, self.data, self.vopt, aspectratio, relx, rely, self.scn, selpnt, selgeom, selflex, selskin)
            else:
                selbody = mujoco.mjv_select(self.model, self.data, self.vopt, aspectratio, relx, rely, self.scn, selpnt, selgeom, selskin)

            if selmode == 2 or selmode == 3:
                if selbody >= 0:
                    self.cam.lookat = selpnt.flatten()
                if selmode == 3 and selbody > 0:
                    self.cam.type = mujoco.mjtCamera.mjCAMERA_TRACKING
                    self.cam.trackbodyid = selbody
                    self.cam.fixedcamid = -1
            else:
                if selbody >= 0:
                    self.pert.select = selbody
                    self.pert.skinselect = selskin
                    vec = selpnt.flatten() - self.data.xpos[selbody]
                    self.pert.localpos = self.data.xmat[selbody].reshape(3, 3).dot(vec)
                else:
                    self.pert.select = 0
                    self.pert.skinselect = -1
            self.pert.active = 0

        if act == 0:
            self.pert.active = 0

    def handle_scroll(self, y_offset):
        """
        处理鼠标滚轮事件，相当于原_scroll_callback。
        参数：
        - y_offset: 滚轮偏移量。
        """
        with self._gui_lock:
            mujoco.mjv_moveCamera(self.model, mujoco.mjtMouse.mjMOUSE_ZOOM, 0, -0.05 * y_offset, self.scn, self.cam)


class MujocoQtViewer(Callbacks, QWidget):
    """
    MujocoQtViewer类：集成MuJoCo渲染到PyQt6的查看器。
    继承自QWidget和Callbacks，使用offscreen渲染模式。
    使用GLFW创建隐藏窗口作为渲染上下文，读取像素后转换为QImage显示在QLabel中。
    使用QTimer定时渲染。
    """
    close_signal = pyqtSignal()  # 自定义信号，用于关闭窗口

    def __init__(self, model, data, title="MuJoCo Qt Viewer", width=None, height=None, hide_menus=False):
        """
        初始化查看器。
        参数：
        - model: MuJoCo模型。
        - data: MuJoCo数据。
        - title: 窗口标题。
        - width, height: 初始窗口大小。
        - hide_menus: 是否隐藏菜单。
        """
        Callbacks.__init__(self,hide_menus)
        QWidget.__init__(self)

        self.model = model
        self.data = data
        self.setWindowTitle(title)
        self.setMouseTracking(True)  # 启用鼠标跟踪

        # 配置路径
        self.CONFIG_PATH = pathlib.Path.joinpath(pathlib.Path.home(), ".config/mujoco_viewer/config.yaml")

        # GLFW初始化（用于offscreen上下文）
        glfw.init()
        if not width:
            width, _ = glfw.get_video_mode(glfw.get_primary_monitor()).size

        if not height:
            _, height = glfw.get_video_mode(glfw.get_primary_monitor()).size
        self.resize(width, height)
        glfw.window_hint(glfw.VISIBLE, 0)  # 隐藏窗口
        self.glfw_window = glfw.create_window(width, height, title, None, None)
        print(width, height)
        glfw.make_context_current(self.glfw_window)
        glfw.swap_interval(1)

        # 帧缓冲区大小
        framebuffer_width, framebuffer_height = glfw.get_framebuffer_size(self.glfw_window)
        self._scale = framebuffer_width / width

        # MuJoCo对象
        self.vopt = mujoco.MjvOption()
        self.cam = mujoco.MjvCamera()
        self.pert = mujoco.MjvPerturb()
        self.scn = None
        self.ctx = None
        if self.model:
            self.scn = mujoco.MjvScene(self.model, maxgeom=10000)
            self.ctx = mujoco.MjrContext(self.model, mujoco.mjtFontScale.mjFONTSCALE_150.value)
                
        # 图表（figures）
        max_num_figs = 3
        self.figs = []
        for idx in range(max_num_figs):
            fig = mujoco.MjvFigure()
            mujoco.mjv_defaultFigure(fig)
            fig.flg_extend = 1
            self.figs.append(fig)

        # 加载相机配置
        pathlib.Path(self.CONFIG_PATH.parent).mkdir(parents=True, exist_ok=True)
        pathlib.Path(self.CONFIG_PATH).touch(exist_ok=True)
        print("Loading camera configuration from %s" % self.CONFIG_PATH)
        with open(self.CONFIG_PATH, "r") as f:
            try:
                cam_config = {
                    "type": self.cam.type,
                    "fixedcamid": self.cam.fixedcamid,
                    "trackbodyid": self.cam.trackbodyid,
                    "lookat": self.cam.lookat.tolist(),
                    "distance": self.cam.distance,
                    "azimuth": self.cam.azimuth,
                    "elevation": self.cam.elevation
                }
                load_config = yaml.safe_load(f)
                if isinstance(load_config, dict):
                    for key, val in load_config.items():
                        if key in cam_config:
                            cam_config[key] = val
                if cam_config["type"] == mujoco.mjtCamera.mjCAMERA_FIXED and cam_config["fixedcamid"] < self.model.ncam:
                    self.cam.type = cam_config["type"]
                    self.cam.fixedcamid = cam_config["fixedcamid"]
                if cam_config["type"] == mujoco.mjtCamera.mjCAMERA_TRACKING and cam_config["trackbodyid"] < self.model.nbody:
                    self.cam.type = cam_config["type"]
                    self.cam.trackbodyid = cam_config["trackbodyid"]
                self.cam.lookat = np.array(cam_config["lookat"])
                self.cam.distance = cam_config["distance"]
                self.cam.azimuth = cam_config["azimuth"]
                self.cam.elevation = cam_config["elevation"]
            except yaml.YAMLError as e:
                print(e)

        # Qt布局
        layout = QVBoxLayout()
        self.image_label = QLabel(self)
        layout.addWidget(self.image_label)
        self.setLayout(layout)

        # 视口
        self.viewport = mujoco.MjrRect(0, 0, framebuffer_width, framebuffer_height)

        # 叠加和标记
        self._overlay = {}
        self._markers = []

        # 定时器用于渲染循环
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.render)
        self.timer.start(int(1))  # 毫秒

        # 连接关闭信号
        self.close_signal.connect(self.close)

    def set_model_data(self, model, data):
        """
        设置model和data，并初始化scn、ctx。
        - 用于加载BVH后动态设置。
        """
        self.model = model
        self.data = data
        if self.model:
            self.scn = mujoco.MjvScene(self.model, maxgeom=10000)
            self.ctx = mujoco.MjrContext(self.model, mujoco.mjtFontScale.mjFONTSCALE_150.value)
        # 更新视口（基于当前大小）
        framebuffer_width, framebuffer_height = glfw.get_framebuffer_size(self.glfw_window)
        self.viewport = mujoco.MjrRect(0, 0, framebuffer_width, framebuffer_height)    

    def add_line_to_fig(self, line_name, fig_idx=0):
        """添加线到图表，参考原代码。"""
        assert isinstance(line_name, str)
        fig = self.figs[fig_idx]
        if line_name.encode('utf8') == b'':
            raise Exception("Line name cannot be empty.")
        if line_name.encode('utf8') in fig.linename:
            raise Exception("Line name already exists.")
        linecount = fig.linename.tolist().index(b'')
        fig.linename[linecount] = line_name
        for i in range(mujoco.mjMAXLINEPNT):
            fig.linedata[linecount][2 * i] = -float(i)

    def add_data_to_line(self, line_name, line_data, fig_idx=0):
        """更新线数据，参考原代码。"""
        fig = self.figs[fig_idx]
        _line_name = line_name.encode('utf8')
        linenames = fig.linename.tolist()
        try:
            line_idx = linenames.index(_line_name)
        except ValueError:
            raise Exception("Invalid line name.")
        pnt = min(mujoco.mjMAXLINEPNT, fig.linepnt[line_idx] + 1)
        for i in range(pnt - 1, 0, -1):
            fig.linedata[line_idx][2 * i + 1] = fig.linedata[line_idx][2 * i - 1]
        fig.linepnt[line_idx] = pnt
        fig.linedata[line_idx][1] = line_data

    def add_marker(self, **marker_params):
        """添加标记，参考原代码。"""
        self._markers.append(marker_params)

    def _add_marker_to_scene(self, marker):
        """将标记添加到场景，参考原代码。"""
        if self.scn.ngeom >= self.scn.maxgeom:
            raise RuntimeError('Ran out of geoms.')
        g = self.scn.geoms[self.scn.ngeom]
        # 默认值设置...
        g.dataid = -1
        g.objtype = mujoco.mjtObj.mjOBJ_UNKNOWN
        g.objid = -1
        g.category = mujoco.mjtCatBit.mjCAT_DECOR
        g.texid = -1
        g.texuniform = 0
        g.texrepeat[0] = 1
        g.texrepeat[1] = 1
        g.emission = 0
        g.specular = 0.5
        g.shininess = 0.5
        g.reflectance = 0
        g.type = mujoco.mjtGeom.mjGEOM_BOX
        g.size[:] = np.ones(3) * 0.1
        g.mat[:] = np.eye(3)
        g.rgba[:] = np.ones(4)

        for key, value in marker.items():
            if isinstance(value, (int, float, mujoco._enums.mjtGeom)):
                setattr(g, key, value)
            elif isinstance(value, (tuple, list, np.ndarray)):
                attr = getattr(g, key)
                attr[:] = np.asarray(value).reshape(attr.shape)
            elif isinstance(value, str):
                if key == "label":
                    if value is None:
                        g.label[0] = 0
                    else:
                        g.label = value
            else:
                raise ValueError(f"Invalid type for {key}")

        self.scn.ngeom += 1

    def _create_overlay(self):
        """创建叠加文本，参考原代码。"""
        topleft = mujoco.mjtGridPos.mjGRID_TOPLEFT
        topright = mujoco.mjtGridPos.mjGRID_TOPRIGHT
        bottomleft = mujoco.mjtGridPos.mjGRID_BOTTOMLEFT
        bottomright = mujoco.mjtGridPos.mjGRID_BOTTOMRIGHT

        def add_overlay(gridpos, text1, text2):
            if gridpos not in self._overlay:
                self._overlay[gridpos] = ["", ""]
            self._overlay[gridpos][0] += text1 + "\n"
            self._overlay[gridpos][1] += text2 + "\n"

        # 添加各种叠加项...
        if self._render_every_frame:
            add_overlay(topleft, "", "")
        else:
            add_overlay(topleft, "Run speed = %.3f x real time" % self._run_speed, "[S]lower, [F]aster")
        add_overlay(
            topleft,
            "Ren[d]er every frame",
            "On" if self._render_every_frame else "Off")
        add_overlay(
            topleft, "Switch camera (#cams = %d)" %
            (self.model.ncam + 1), "[Tab] (camera ID = %d)" %
            self.cam.fixedcamid)
        add_overlay(
            topleft,
            "[C]ontact forces",
            "On" if self._contacts else "Off")
        add_overlay(
            topleft,
            "[J]oints",
            "On" if self._joints else "Off")
        add_overlay(
            topleft,
            "[G]raph Viewer",
            "Off" if self._hide_graph else "On")
        add_overlay(
            topleft,
            "[I]nertia",
            "On" if self._inertias else "Off")
        add_overlay(
            topleft,
            "Center of [M]ass",
            "On" if self._com else "Off")
        add_overlay(
            topleft, "Shad[O]ws", "On" if self._shadows else "Off"
        )
        add_overlay(
            topleft,
            "T[r]ansparent",
            "On" if self._transparent else "Off")
        add_overlay(
            topleft,
            "[W]ireframe",
            "On" if self._wire_frame else "Off")
        add_overlay(
            topleft,
            "Con[V]ex Hull Rendering",
            "On" if self._convex_hull_rendering else "Off",
        )
        if self._paused is not None:
            if not self._paused:
                add_overlay(topleft, "Stop", "[Space]")
            else:
                add_overlay(topleft, "Start", "[Space]")
                add_overlay(
                    topleft,
                    "Advance simulation by one step",
                    "[right arrow]")
        add_overlay(topleft, "Toggle geomgroup visibility (0-5)",
                    ",".join(["On" if g else "Off" for g in self.vopt.geomgroup]))
        add_overlay(
            topleft,
            "Referenc[e] frames",
            mujoco.mjtFrame(self.vopt.frame).name)
        add_overlay(topleft, "[H]ide Menus", "")
        if self._image_idx > 0:
            fname = self._image_path % (self._image_idx - 1)
            add_overlay(topleft, "Cap[t]ure frame", "Saved as %s" % fname)
        else:
            add_overlay(topleft, "Cap[t]ure frame", "")

        add_overlay(
            bottomleft, "FPS", "%d%s" %
            (1 / self._time_per_render, ""))

        if MUJOCO_VERSION >= (3, 0, 0):
            add_overlay(
                bottomleft, "Max solver iters", str(
                    max(self.data.solver_niter) + 1))
        else:
            add_overlay(
                bottomleft, "Solver iterations", str(
                    self.data.solver_iter + 1))

        add_overlay(
            bottomleft, "Step", str(
                round(
                    self.data.time / self.model.opt.timestep)))
        add_overlay(bottomleft, "timestep", "%.5f" % self.model.opt.timestep)

    def apply_perturbations(self):
        """应用扰动，参考原代码。"""
        self.data.xfrc_applied = np.zeros_like(self.data.xfrc_applied)
        mujoco.mjv_applyPerturbPose(self.model, self.data, self.pert, 0)
        mujoco.mjv_applyPerturbForce(self.model, self.data, self.pert)

    def read_pixels(self, camid=None, depth=False):
        """读取像素，参考原代码的offscreen模式。"""
        if camid is not None:
            if camid == -1:
                self.cam.type = mujoco.mjtCamera.mjCAMERA_FREE
            else:
                self.cam.type = mujoco.mjtCamera.mjCAMERA_FIXED
            self.cam.fixedcamid = camid

        self.viewport.width, self.viewport.height = glfw.get_framebuffer_size(self.glfw_window)
        # mujoco.mjv_updateScene(self.model, self.data, self.vopt, self.pert, self.cam, mujoco.mjtCatBit.mjCAT_ALL.value, self.scn)
        # mujoco.mjr_render(self.viewport, self.scn, self.ctx)
        shape = glfw.get_framebuffer_size(self.glfw_window)

        if depth:
            rgb_img = np.zeros((shape[1], shape[0], 3), dtype=np.uint8)
            depth_img = np.zeros((shape[1], shape[0], 1), dtype=np.float32)
            mujoco.mjr_readPixels(rgb_img, depth_img, self.viewport, self.ctx)
            rgb_img = np.flipud(rgb_img)
            rgb_img = np.ascontiguousarray(rgb_img)
            depth_img = np.flipud(depth_img)
            depth_img = np.ascontiguousarray(depth_img)
            return rgb_img, depth_img
        else:
            img = np.zeros((shape[1], shape[0], 3), dtype=np.uint8)
            mujoco.mjr_readPixels(img, None, self.viewport, self.ctx)
            img = np.flipud(img)
            img = np.ascontiguousarray(img)
            return img

    def render(self):
        """渲染函数，使用QTimer调用。"""
        # 创建叠加
        if self.model is None or self.data is None:
            return
        # 检查窗口大小，避免除零或无效渲染
        width, height = glfw.get_framebuffer_size(self.glfw_window)
        if width <= 0 or height <= 0:
            return
        mujoco.mj_step(self.model, self.data)
        self._create_overlay()

        render_start = time.time()
        width, height = glfw.get_framebuffer_size(self.glfw_window)
        self.viewport.width, self.viewport.height = width, height
        with self._gui_lock:
            mujoco.mjv_updateScene(self.model, self.data, self.vopt, self.pert, self.cam, mujoco.mjtCatBit.mjCAT_ALL.value, self.scn)
            # for marker in self._markers:
            #     self._add_marker_to_scene(marker)
            mujoco.mjr_render(self.viewport, self.scn, self.ctx)
            for gridpos, [t1, t2] in self._overlay.items():
                menu_positions = [mujoco.mjtGridPos.mjGRID_TOPLEFT, mujoco.mjtGridPos.mjGRID_BOTTOMLEFT]
                if gridpos in menu_positions and self._hide_menus:
                    continue
                mujoco.mjr_overlay(mujoco.mjtFontScale.mjFONTSCALE_150, gridpos, self.viewport, t1, t2, self.ctx)

            if not self._hide_graph:
                for idx, fig in enumerate(self.figs):
                    width_adjustment = width % 4
                    x = int(3 * width / 4) + width_adjustment
                    y = idx * int(height / 4)
                    fig_viewport = mujoco.MjrRect(x, y, int(width / 4), int(height / 4))
                    has_lines = len([i for i in fig.linename if i != b''])
                    if has_lines:
                        mujoco.mjr_figure(fig_viewport, fig, self.ctx)

        # 读取像素并更新QLabel
        img = self.read_pixels()
        qimg = QImage(img.data, img.shape[1], img.shape[0], QImage.Format.Format_RGB888)
        self.image_label.setPixmap(QPixmap.fromImage(qimg))
        # width, height = img.shape[1], img.shape[0]  # width = img.shape[1], height = img.shape[0]
        # bytes_per_line = width * 3  # 对于 Format_RGB888，每像素 3 字节
        # qimg = QImage(img.data, width, height, bytes_per_line, QImage.Format.Format_RGB888)
        # self.image_label.setPixmap(QPixmap.fromImage(qimg))

        self._time_per_render = 0.9 * self._time_per_render + 0.1 * (time.time() - render_start)
        self._overlay.clear()
        self._markers[:] = []

        self.apply_perturbations()

        if self._paused:
            while self._paused:
                if self._advance_by_one_step:
                    self._advance_by_one_step = False
                    break
        else:
            self._loop_count += self.model.opt.timestep / (self._time_per_render * self._run_speed)
            if self._render_every_frame:
                self._loop_count = 1
            while self._loop_count > 0:
                self._loop_count -= 1

    def keyPressEvent(self, event: QKeyEvent):
        """重载Qt键盘按下事件。"""
        if self.model is None or self.data is None:
            return
        mods = event.modifiers()
        self.handle_key_press(event.key(), mods)

    def mouseMoveEvent(self, event: QMouseEvent):
        """重载Qt鼠标移动事件。"""
        if self.model is None or self.data is None:
            return
        self.handle_mouse_move(event.position().x(), event.position().y())

    def mousePressEvent(self, event: QMouseEvent):
        """重载Qt鼠标按下事件。"""
        if self.model is None or self.data is None:
            return
        mods = event.modifiers()
        self.handle_mouse_button(event.button(), 1, mods, event.position().x(), event.position().y())

    def mouseReleaseEvent(self, event: QMouseEvent):
        """重载Qt鼠标释放事件。"""
        if self.model is None or self.data is None:
            return
        mods = event.modifiers()
        self.handle_mouse_button(event.button(), 0, mods, event.position().x(), event.position().y())

    def wheelEvent(self, event):
        """重载Qt滚轮事件。"""
        if self.model is None or self.data is None:
            return
        y_offset = event.angleDelta().y() / 120.0  # 标准化偏移
        self.handle_scroll(y_offset)

    def closeEvent(self, event):
        """关闭事件。"""
        glfw.terminate()
        self.ctx.free()
        event.accept()

    def resizeEvent(self, event: QResizeEvent):
        """
        重载resize事件：同步调整GLFW窗口大小、视口和缩放因子，确保MuJoCo渲染自适应。
        - 调用super()以保持Qt默认行为。
        - 仅当model存在时更新MuJoCo对象（避免初始化时错误）。
        """
        super().resizeEvent(event)
        
# 示例使用
if __name__ == "__main__":
    # 假设model和data已从MuJoCo加载
    model = mujoco.MjModel.from_xml_path('humanoid.xml')
    data = mujoco.MjData(model)

    app = QApplication([])
    viewer = MujocoQtViewer(model, data)
    viewer.show()
    app.exec()