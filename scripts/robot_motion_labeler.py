import argparse
import os
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter import font

from general_motion_retargeting import RobotMotionViewer, load_robot_motion


class MotionLabelerApp:
    def __init__(self, robot_type: str, motion_folder: str) -> None:
        self.robot_type = robot_type
        self.motion_folder = motion_folder

        self.motion_dataset = self._load_motion_dataset(motion_folder)
        if not self.motion_dataset:
            raise FileNotFoundError(f"No .pkl files found in {motion_folder}")

        # Launch MuJoCo viewer
        sample_motion = self.motion_dataset[0]
        self.viewer = RobotMotionViewer(robot_type=self.robot_type, motion_fps=sample_motion["motion_fps"], camera_follow=False)

        self.current_index = 0
        self.frame_idx = 0
        self.paused = False
        self.lock = threading.Lock()
        self.stop_event = threading.Event()

        self.viewer_overlay_title = "Motion"
        self.viewer_overlay_text = ""

        # Start playback thread
        self.play_thread = threading.Thread(target=self._playback_loop, daemon=True)
        self.play_thread.start()

        # Build GUI
        self.root = tk.Tk()
        self.root.title("Motion Labeler")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        default_font = font.nametofont("TkDefaultFont")
        default_font.configure(size=14)
        text_font = font.nametofont("TkTextFont")
        text_font.configure(size=14)
        fixed_font = font.nametofont("TkFixedFont")
        fixed_font.configure(size=14)

        self.status_var = tk.StringVar()
        self.status_var.set("Ready")

        self._build_gui()
        self._refresh_selection()

    def _load_motion_dataset(self, folder):
        motion_files = sorted(f for f in os.listdir(folder) if f.endswith(".pkl"))
        dataset = []
        for motion_file in motion_files:
            motion_path = os.path.join(folder, motion_file)
            try:
                (motion_data, motion_fps, motion_root_pos, motion_root_rot, motion_dof_pos, motion_local_body_pos, motion_link_body_list) = load_robot_motion(motion_path)
            except Exception as exc:
                print(f"[WARN] Failed to load {motion_file}: {exc}")
                continue
            dataset.append(
                {
                    "motion_file": motion_file,
                    "motion_path": motion_path,
                    "motion_fps": motion_fps,
                    "motion_root_pos": motion_root_pos,
                    "motion_root_rot": motion_root_rot,
                    "motion_dof_pos": motion_dof_pos,
                    "motion_local_body_pos": motion_local_body_pos,
                    "motion_link_body_list": motion_link_body_list,
                }
            )
        return dataset

    def _build_gui(self):
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.grid(row=0, column=0, sticky="nsew")

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        ttk.Label(main_frame, text="Motion Files").grid(row=0, column=0, sticky="w")

        self.listbox = tk.Listbox(main_frame, height=20, width=40)
        self.listbox.grid(row=1, column=0, rowspan=6, sticky="nsew")
        self.listbox.bind("<<ListboxSelect>>", self._on_select)
        self.listbox.bind("<Double-Button-1>", self._on_double_click)

        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=scrollbar.set)
        scrollbar.grid(row=1, column=1, rowspan=6, sticky="ns")

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=1, column=2, sticky="nw", padx=(10, 0))

        ttk.Button(button_frame, text="Prev", command=self._prev_motion).grid(row=0, column=0, pady=2, sticky="ew")
        ttk.Button(button_frame, text="Next", command=self._next_motion).grid(row=1, column=0, pady=2, sticky="ew")
        ttk.Button(button_frame, text="Pause/Resume", command=self._toggle_pause).grid(row=2, column=0, pady=2, sticky="ew")

        ttk.Label(button_frame, text="Label Actions (TODO)").grid(row=3, column=0, pady=(10, 2), sticky="w")
        ttk.Button(button_frame, text="Mark Positive", command=lambda: self._record_label("positive")).grid(row=4, column=0, pady=2, sticky="ew")
        ttk.Button(button_frame, text="Mark Negative", command=lambda: self._record_label("negative")).grid(row=5, column=0, pady=2, sticky="ew")

        status_label = ttk.Label(main_frame, textvariable=self.status_var, relief="sunken", anchor="w")
        status_label.grid(row=7, column=0, columnspan=3, sticky="ew", pady=(10, 0))

        for i in range(6):
            main_frame.rowconfigure(i + 1, weight=1)
        main_frame.columnconfigure(0, weight=1)

        for idx, motion in enumerate(self.motion_dataset):
            self.listbox.insert(tk.END, motion["motion_file"])

    def _on_select(self, event):
        selection = self.listbox.curselection()
        if not selection:
            return
        idx = selection[0]
        self._set_current_motion(idx)

    def _on_double_click(self, event):
        self._toggle_pause()

    def _set_current_motion(self, idx: int):
        with self.lock:
            self.current_index = idx
            self.frame_idx = 0
            self.paused = False
        motion_file = self.motion_dataset[idx]["motion_file"]
        self.status_var.set(f"Current: {motion_file}")

    def _prev_motion(self):
        if not self.motion_dataset:
            return
        idx = (self.current_index - 1) % len(self.motion_dataset)
        self.listbox.selection_clear(0, tk.END)
        self.listbox.selection_set(idx)
        self.listbox.activate(idx)
        self._set_current_motion(idx)

    def _next_motion(self):
        if not self.motion_dataset:
            return
        idx = (self.current_index + 1) % len(self.motion_dataset)
        self.listbox.selection_clear(0, tk.END)
        self.listbox.selection_set(idx)
        self.listbox.activate(idx)
        self._set_current_motion(idx)

    def _toggle_pause(self):
        with self.lock:
            self.paused = not self.paused
        self.status_var.set(f"Paused" if self.paused else f"Playing: {self.motion_dataset[self.current_index]['motion_file']}")

    def _record_label(self, label: str):
        motion = self.motion_dataset[self.current_index]
        self.status_var.set(f"Marked {motion['motion_file']} as {label}")
        # Placeholder: Implement persistence to disk as needed.

    def _refresh_selection(self):
        if self.motion_dataset:
            self.listbox.selection_set(0)
            self.listbox.activate(0)
            self._set_current_motion(0)

    def _playback_loop(self):
        while not self.stop_event.is_set():
            with self.lock:
                if self.current_index is None:
                    motion = None
                else:
                    motion = self.motion_dataset[self.current_index]
                paused = self.paused
                frame_idx = self.frame_idx

            if motion is None or paused:
                time.sleep(0.05)
                continue

            root_pos = motion["motion_root_pos"][frame_idx]
            root_rot = motion["motion_root_rot"][frame_idx]
            dof_pos = motion["motion_dof_pos"][frame_idx]
            total_frames = len(motion["motion_root_pos"])

            overlay_text = f"{motion['motion_file']}\nFrame {frame_idx + 1}/{total_frames}"
            self.viewer._overlay_title = "Motion"
            self.viewer._overlay_text = overlay_text

            self.viewer.step(root_pos, root_rot, dof_pos, rate_limit=True, follow_camera=False)

            with self.lock:
                if not self.paused and self.current_index is not None:
                    self.frame_idx = (self.frame_idx + 1) % total_frames

        self.viewer.close()

    def _on_close(self):
        if messagebox.askokcancel("Quit", "Exit labeler?"):
            self.stop_event.set()
            self.root.after(100, self._finalize_close)

    def _finalize_close(self):
        self.root.destroy()

    def run(self):
        self.root.mainloop()
        self.stop_event.set()
        if self.play_thread.is_alive():
            self.play_thread.join(timeout=1.0)


def parse_args():
    parser = argparse.ArgumentParser(description="Robot motion labeling GUI")
    parser.add_argument("--robot", type=str, default="unitree_g1")
    parser.add_argument("--robot_motion_folder", type=str, required=True)
    return parser.parse_args()


def main():
    args = parse_args()
    app = MotionLabelerApp(robot_type=args.robot, motion_folder=args.robot_motion_folder)
    app.run()


if __name__ == "__main__":
    main()
