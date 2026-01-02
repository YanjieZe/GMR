import os
import subprocess
import cv2
import datetime
from pathlib import Path


class VideoRecorder(object):
    """
    Simple video record that creates a video from a stream of images.
    """

    def __init__(self, path="./LocoMuJoCo_recordings", tag=None, video_name=None, fps=60, compress=True):
        """
        Constructor.

        Args:
            path: Path at which videos will be stored.
            tag: Name of the directory at path in which the video will be stored. If None, a timestamp will be created.
            video_name: Name of the video without extension. Default is "recording".
            fps: Frame rate of the video.
            compress: Whether to compress the video after recording.
        """

        if tag is None:
            date_time = datetime.datetime.now()
            tag = date_time.strftime("%d-%m-%Y_%H-%M-%S")

        self._path = Path(path)
        self._path = self._path / tag

        self._video_name = video_name if video_name else "recording"
        self._counter = 0

        self._fps = fps

        self._compress = compress
        self._video_writer = None
        self._video_writer_path = None

    def __call__(self, frame):
        """
        Args:
            frame (np.ndarray): Frame to be added to the video (H, W, RGB)
        """
        assert frame is not None

        if self._video_writer is None:
            height, width = frame.shape[:2]
            self._create_video_writer(height, width)

        self._video_writer.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))

    def _create_video_writer(self, height, width):

        name = self._video_name
        if self._counter > 0:
            name += f"-{self._counter}.mp4"
        else:
            name += ".mp4"

        self._path.mkdir(parents=True, exist_ok=True)

        path = self._path / name

        self._video_writer_path = str(path)
        self._video_writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc('m', 'p', '4', 'v'),
                                             self._fps, (width, height))

    def stop(self):
        cv2.destroyAllWindows()
        self._video_writer.release()

        # compress video
        if self._compress:
            try:
                tmp_file = str(self._path / "tmp_") + self._video_name + ".mp4"
                subprocess.run(
                    [
                        "ffmpeg",
                        "-i", self._video_writer_path,  # Input video
                        "-c:v", "libx264",  # H.264 codec
                        "-profile:v", "baseline",  # Set to Baseline profile (can change to main if needed)
                        "-preset", "fast",  # Encoding preset
                        "-crf", "23",  # Quality setting
                        "-an",  # Remove audio
                        "-r", "30",  # Frame rate
                        "-y",  # Overwrite existing file
                        tmp_file  # Output file
                    ],
                    stdout=subprocess.DEVNULL,  # Suppress standard output
                    check=True  # Raise an error if ffmpeg fails
                )
                os.replace(tmp_file, self._video_writer_path)
                print("Successfully compressed recorded video and saved at: ", self._video_writer_path)

            except subprocess.CalledProcessError as e:
                print(f"Video compression failed: {e}")

        self._video_writer = None

        self._counter += 1

        return self._video_writer_path
