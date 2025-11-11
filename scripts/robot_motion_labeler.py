import argparse
import json
import os
import re
import threading
import multiprocessing as mp
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import ttk, messagebox
from tkinter import font
from typing import Optional

from general_motion_retargeting import RobotMotionViewer, load_robot_motion

mp_context = mp.get_context("spawn")


class MotionLabelerApp:
    def __init__(self, robot_type: str, motion_folder: str, description_json: Optional[str] = None) -> None:
        self.robot_type = robot_type
        self.motion_folder = motion_folder

        self.motion_dataset = self._load_motion_dataset(motion_folder)
        if not self.motion_dataset:
            raise FileNotFoundError(f"No .pkl files found in {motion_folder}")

        (
            self.motion_info_map,
            self.motion_info_normalized_map,
        ) = self._load_motion_info(description_json)

        self.current_index = 0
        self.frame_idx = 0
        self.paused = False
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.viewer_lock = threading.Lock()
        self.viewer = None
        self.record_processes = []
        self._record_polling = False

        self.viewer_overlay_title = "Motion"
        self.viewer_overlay_text = ""

        # Build GUI
        self.root = tk.Tk()
        self.root.title("Motion Labeler")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self.status_var = tk.StringVar(value="Ready")
        self.description_var = tk.StringVar(value="No description available.")
        self.frame_info_var = tk.StringVar(value="Frame: 0/0")

        default_font = font.nametofont("TkDefaultFont")
        default_font.configure(size=14)
        tktext_font = font.nametofont("TkTextFont")
        tktext_font.configure(size=14)
        fixed_font = font.nametofont("TkFixedFont")
        fixed_font.configure(size=14)

        self._build_gui()
        self._refresh_selection()
        # Kick off playback loop in Tk event loop
        self.root.after(0, self._playback_step)

    def _load_motion_dataset(self, folder):
        motion_paths = []
        for root, _, files in os.walk(folder):
            for name in files:
                if name.endswith(".pkl"):
                    motion_paths.append(os.path.join(root, name))

        motion_paths.sort()

        dataset = []
        for motion_path in motion_paths:
            motion_file = os.path.relpath(motion_path, folder)
            try:
                (
                    motion_data,
                    motion_fps,
                    motion_root_pos,
                    motion_root_rot,
                    motion_dof_pos,
                    motion_local_body_pos,
                    motion_link_body_list,
                ) = load_robot_motion(motion_path)
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

    def _load_motion_info(self, description_json: Optional[str]):
        if not description_json:
            return {}, {}
        try:
            with open(description_json, "r") as f:
                info = json.load(f)
            print(
                f"[MotionLabeler] Loaded descriptions from {description_json} (entries: {len(info)})"
            )
            normalized = {}
            for raw_key, value in info.items():
                norm_key = self._normalize_key(raw_key)
                normalized.setdefault(norm_key, value)
            return info, normalized
        except FileNotFoundError:
            print(f"[WARN] Description file not found: {description_json}")
        except Exception as exc:
            print(f"[WARN] Failed to load description file {description_json}: {exc}")
        return {}, {}

    def _get_motion_description(self, motion_file: str):
        if not self.motion_info_map:
            return None
        basename = os.path.basename(motion_file)
        candidates = [
            motion_file,
            os.path.splitext(motion_file)[0],
            basename,
            os.path.splitext(basename)[0],
        ]
        for key in candidates:
            if key in self.motion_info_map:
                return self.motion_info_map[key]
            norm_key = self._normalize_key(key)
            if norm_key and norm_key in self.motion_info_normalized_map:
                return self.motion_info_normalized_map[norm_key]
        norm_original = self._normalize_key(motion_file)
        if norm_original and norm_original in self.motion_info_normalized_map:
            return self.motion_info_normalized_map[norm_original]
        return None

    def _update_description_panel(self, motion_file: str):
        info = self._get_motion_description(motion_file)
        if info is None:
            text = "No description available."
        else:
            sentences = info.get("sentences") or []
            if sentences:
                text = "\n".join(sentences)
            else:
                text = json.dumps(info, indent=2, ensure_ascii=False)

        self._set_description_text(text)

    def _set_description_text(self, text: str):
        self.root.after(0, lambda: self.description_var.set(text))

    def _update_frame_info(self, frame_idx: int, total_frames: int):
        self.root.after(0, lambda: self.frame_info_var.set(f"Frame: {frame_idx}/{total_frames}"))

    def _create_viewer(self, motion, force: bool = False):
        with self.viewer_lock:
            if force and self.viewer is not None:
                try:
                    self.viewer.close()
                except Exception:
                    pass
                self.viewer = None

            if self.viewer is None:
                fps = 30
                if motion and motion.get("motion_fps"):
                    fps = motion["motion_fps"]
                try:
                    self.viewer = RobotMotionViewer(
                        robot_type=self.robot_type,
                        motion_fps=fps,
                        camera_follow=True,
                    )
                except Exception as exc:
                    print(f"[WARN] Failed to create viewer: {exc}")
                    self.viewer = None
            return self.viewer

    def _reopen_viewer(self):
        motion = None
        with self.lock:
            if self.motion_dataset:
                motion = self.motion_dataset[self.current_index]
        viewer = self._create_viewer(motion, force=True)
        if viewer is not None:
            self._set_status("Viewer reopened")
        else:
            self._set_status("Failed to reopen viewer")

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
        ttk.Button(button_frame, text="Reopen Viewer", command=self._reopen_viewer).grid(row=3, column=0, pady=(10, 2), sticky="ew")

        ttk.Label(button_frame, text="Label Actions (TODO)").grid(row=4, column=0, pady=(10, 2), sticky="w")
        ttk.Button(button_frame, text="Mark Positive", command=lambda: self._record_label("positive", save_video=False)).grid(row=5, column=0, pady=2, sticky="ew")
        ttk.Button(button_frame, text="Record Positive", command=lambda: self._record_label("positive", save_video=True)).grid(row=5, column=1, pady=2, sticky="ew", padx=(5, 0))
        ttk.Button(button_frame, text="Mark Negative", command=lambda: self._record_label("negative", save_video=False)).grid(row=6, column=0, pady=2, sticky="ew")
        ttk.Button(button_frame, text="Record Negative", command=lambda: self._record_label("negative", save_video=True)).grid(row=6, column=1, pady=2, sticky="ew", padx=(5, 0))

        desc_frame = ttk.Frame(main_frame)
        desc_frame.grid(row=7, column=0, columnspan=4, sticky="nsew", pady=(10, 0))
        ttk.Label(desc_frame, text="Description").grid(row=0, column=0, sticky="w")
        self.description_label = ttk.Label(
            desc_frame,
            textvariable=self.description_var,
            anchor="w",
            justify="left",
            wraplength=600,
        )
        self.description_label.grid(row=1, column=0, columnspan=2, sticky="nsew")
        desc_frame.rowconfigure(1, weight=1)
        desc_frame.columnconfigure(0, weight=1)
        self.frame_info_label = ttk.Label(desc_frame, textvariable=self.frame_info_var, anchor="w")
        self.frame_info_label.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(5, 0))

        status_label = ttk.Label(main_frame, textvariable=self.status_var, relief="sunken", anchor="w")
        status_label.grid(row=8, column=0, columnspan=4, sticky="ew", pady=(10, 0))

        for i in range(1, 7):
            main_frame.rowconfigure(i, weight=1)
        main_frame.rowconfigure(7, weight=2)
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(3, weight=2)

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
        self._update_description_panel(motion_file)

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

    def _record_label(self, label: str, save_video: bool = False):
        motion = None
        with self.lock:
            if self.motion_dataset:
                motion = self.motion_dataset[self.current_index]
        if motion is None:
            self.status_var.set("No motion selected")
            return

        if save_video:
            if not messagebox.askyesno("Confirm", f"Record {label} video for {motion['motion_file']}?"):
                return
            self._start_video_recording(motion, label)
        else:
            self._set_status(f"Marked {motion['motion_file']} as {label}")

    def _start_video_recording(self, motion, label: str):
        video_dir = Path("/home/kai/GMR1/videos") / label
        video_dir.mkdir(parents=True, exist_ok=True)
        slug = motion["motion_file"].replace("/", "_").replace(".pkl", "")
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        video_path = video_dir / f"{slug}_{timestamp}.mp4"

        self._set_status(f"Recording {label} video...")

        motion_path = motion["motion_path"]
        process = mp_context.Process(
            target=_record_video_worker,
            args=(motion_path, self.robot_type, str(video_path)),
            daemon=True,
        )
        process.start()

        self.record_processes.append({"process": process, "path": video_path})
        if not self._record_polling:
            self._record_polling = True
            self.root.after(500, self._poll_record_processes)

    def _poll_record_processes(self):
        if not self.record_processes:
            self._record_polling = False
            return

        remaining = []
        for entry in self.record_processes:
            process = entry["process"]
            video_path = entry["path"]
            if process.exitcode is None:
                remaining.append(entry)
                continue
            if process.exitcode == 0:
                self._set_status(f"Saved video to {video_path}")
            else:
                self._set_status(f"Video recording failed (exit code {process.exitcode})")

        self.record_processes = remaining
        if self.record_processes:
            self.root.after(500, self._poll_record_processes)
        else:
            self._record_polling = False

    def _set_status(self, text: str):
        self.root.after(0, lambda: self.status_var.set(text))

    def _refresh_selection(self):
        if self.motion_dataset:
            self.listbox.selection_set(0)
            self.listbox.activate(0)
            self._set_current_motion(0)

    def _playback_step(self):
        if self.stop_event.is_set():
            return

        with self.lock:
            motion = self.motion_dataset[self.current_index] if self.motion_dataset else None
            paused = self.paused
            frame_idx = self.frame_idx

        if motion is None or paused:
            self.root.after(30, self._playback_step)
            return

        total_frames = len(motion["motion_root_pos"])
        if total_frames == 0:
            self.root.after(30, self._playback_step)
            return

        root_pos = motion["motion_root_pos"][frame_idx]
        root_rot = motion["motion_root_rot"][frame_idx]
        dof_pos = motion["motion_dof_pos"][frame_idx]

        description = self._get_motion_description(motion["motion_file"])
        sentence = ""
        if description:
            sentences = description.get("sentences") or []
            if sentences:
                sentence = sentences[0]

        overlay_lines = [motion["motion_file"], f"Frame {frame_idx + 1}/{total_frames}"]
        if sentence:
            overlay_lines.append(sentence)
        overlay_text = "\n".join(overlay_lines)

        self._update_description_panel(motion["motion_file"])
        self._update_frame_info(frame_idx + 1, total_frames)

        viewer = self._create_viewer(motion)
        if viewer is not None:
            try:
                if hasattr(viewer, "set_overlay_text"):
                    viewer.set_overlay_text("Motion", overlay_text)
                else:
                    viewer._overlay_title = "Motion"
                    viewer._overlay_text = overlay_text

                viewer.step(root_pos, root_rot, dof_pos, rate_limit=True, follow_camera=True)
            except Exception as exc:
                print(f"[WARN] Viewer step failed, will recreate: {exc}")
                with self.viewer_lock:
                    try:
                        if self.viewer is not None:
                            self.viewer.close()
                    except Exception:
                        pass
                    self.viewer = None

        with self.lock:
            if not self.paused and self.current_index is not None:
                self.frame_idx = (self.frame_idx + 1) % total_frames

        self.root.after(1, self._playback_step)

    def _on_close(self):
        if messagebox.askokcancel("Quit", "Exit labeler?"):
            self.stop_event.set()
            self._cleanup_resources()
            self.root.after(100, self._finalize_close)

    def _finalize_close(self):
        with self.viewer_lock:
            if self.viewer is not None:
                try:
                    self.viewer.close()
                except Exception:
                    pass
                self.viewer = None
        self._cleanup_resources()
        self.root.destroy()

    def _cleanup_resources(self):
        for entry in list(self.record_processes):
            process = entry["process"]
            if process.exitcode is None:
                process.terminate()
                process.join(timeout=1)
        self.record_processes.clear()
        self._record_polling = False

    def run(self):
        self.root.mainloop()
        self.stop_event.set()

    def _normalize_key(self, key: str) -> str:
        if not key:
            return ""
        key = key.lower()
        for token in ["0-", "stageii", "stagei", "stage", "_poses", "poses", ".pkl", ".npz", ".npy", ".json"]:
            key = key.replace(token, "")
        key = re.sub(r"[^a-z0-9]", "", key)
        return key


def _record_video_worker(motion_path: str, robot_type: str, video_path: str):
    try:
        (
            _motion_data,
            motion_fps,
            motion_root_pos,
            motion_root_rot,
            motion_dof_pos,
            _local_body_pos,
            _link_body_list,
        ) = load_robot_motion(motion_path)
        viewer = RobotMotionViewer(
            robot_type=robot_type,
            motion_fps=motion_fps,
            camera_follow=True,
            record_video=True,
            video_path=video_path,
        )
        total_frames = len(motion_root_pos)
        for idx in range(total_frames):
            viewer.step(
                motion_root_pos[idx],
                motion_root_rot[idx],
                motion_dof_pos[idx],
                rate_limit=False,
                follow_camera=True,
            )
        viewer.close()
    except Exception as exc:
        print(f"[RecordWorker] Failed to record video: {exc}")
        raise


def parse_args():
    parser = argparse.ArgumentParser(description="Robot motion labeling GUI")
    parser.add_argument("--robot", type=str, default="unitree_g1")
    parser.add_argument("--robot_motion_folder", type=str, required=True)
    parser.add_argument(
        "--description_json",
        type=str,
        default=None,
        help="Path to JSON file mapping motion filenames to descriptive info",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    app = MotionLabelerApp(
        robot_type=args.robot,
        motion_folder=args.robot_motion_folder,
        description_json=args.description_json,
    )
    app.run()


if __name__ == "__main__":
    main()
