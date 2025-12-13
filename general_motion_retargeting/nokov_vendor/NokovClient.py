import sys
import time
from threading import Thread
from queue import Queue, Full
from typing import Dict, Tuple, Optional

import numpy as np

from scipy.spatial.transform import Rotation as R

try:
    # NOKOV Python SDK (wheel provided in repo under XINGYING-SDK/Python/...)
    from nokov.nokovsdk import (
        PySDKClient,
        DataDescriptions,
        DataDescriptors,
        ServerDescription,
        POINTER,
        c_char_p,
    )
except Exception as import_error:  # pragma: no cover
    raise ImportError(
        "nokov_sdk_py not found. Please install the local wheel first: "
        "XING_Python_SDK-2.4.0.5428/dist/nokovpy-3.0.1-py3-none-any.whl"
    ) from import_error


class NokovClient:
    """
    NOKOV real-time data client with a GMR-compatible interface.

    Features:
    - Connects to a NOKOV server
    - Parses skeleton/rigid body descriptions and builds an ID-to-name mapping
    - Continuously reads frames and converts them into GMR-style human data:
      {body_name: (position_in_meters, quaternion_wxyz)}
    - Provides blocking get_frame() and get_frame_number() APIs
    """

    def __init__(self, server_ip: str, queue_size: int = 10, print_level: int = 0) -> None:
        self.server_ip = server_ip
        self.queue: "Queue[Dict[str, Tuple[np.ndarray, np.ndarray]]]" = Queue(maxsize=queue_size)
        self.latest_frame_number: int = -1
        self._running: bool = False
        self._reader_thread: Optional[Thread] = None
        self._id_to_name: Dict[int, str] = {}
        self._client = PySDKClient()
        # Logging verbosity: 0 means silent
        self._print_level = print_level
        # Global coordinate alignment: rotate Y-up to Z-up (90 degrees around X-axis)
        self._align_rot = R.from_euler("x", 90.0, degrees=True)

    def connected(self) -> bool:
        # Simple check: initialized and reader thread is running
        return self._running and self._reader_thread is not None

    def _log(self, *args) -> None:
        if self._print_level > 0:
            print(*args)

    def _build_id_name_map(self) -> None:
        """Parse skeleton and rigid body descriptions to build an ID-to-name mapping."""
        pdds = POINTER(DataDescriptions)()
        # Wait briefly for data descriptions to become available
        n_defs = 0
        for _ in range(10):
            self._client.PyGetDataDescriptions(pdds)
            try:
                n_defs = int(pdds.contents.nDataDescriptions)
            except Exception:
                n_defs = 0
            if n_defs > 0:
                break
            time.sleep(0.1)

        if n_defs == 0:
            self._id_to_name = {}
            self._log("[NokovClient] Warning: no data descriptions available (nDataDescriptions=0)")
            return

        data_defs = pdds.contents
        id_to_name: Dict[int, str] = {}

        for i_def in range(data_defs.nDataDescriptions):
            data_def = data_defs.arrDataDescriptions[i_def]

            # Skeleton description
            if data_def.type == DataDescriptors.Descriptor_Skeleton.value:
                sk_desc = data_def.Data.SkeletonDescription.contents
                for i_body in range(sk_desc.nRigidBodies):
                    body_def = sk_desc.RigidBodies[i_body]
                    try:
                        name = body_def.szName.decode("utf-8")
                    except Exception:
                        name = f"ID_{body_def.ID}"
                    id_to_name[int(body_def.ID)] = name

            # Single rigid body description (available even without a skeleton)
            elif data_def.type == DataDescriptors.Descriptor_RigidBody.value:
                rb_desc = data_def.Data.RigidBodyDescription.contents
                try:
                    name = rb_desc.szName.decode("utf-8")
                except Exception:
                    name = f"ID_{rb_desc.ID}"
                id_to_name[int(rb_desc.ID)] = name

        self._id_to_name = id_to_name
        self._log(
            f"[NokovClient] ID-to-name mapping built, total entries: {len(self._id_to_name)}"
        )
        if not self._id_to_name:
            self._log(
                "[NokovClient] Warning: no skeleton or rigid body descriptions found. "
                "Please ensure Skeleton/RigidBody is created and running or playing in the software."
            )

    @staticmethod
    def _normalize_names(
        frame_map: Dict[str, Tuple[np.ndarray, np.ndarray]]
    ) -> Dict[str, Tuple[np.ndarray, np.ndarray]]:
        """Apply name normalization required by the GMR bvh_nokov configuration."""
        normalized = dict(frame_map)

        # bvh_nokov uses LeftFootMod / RightFootMod
        if "LeftFootMod" not in normalized and "LeftFoot" in normalized:
            normalized["LeftFootMod"] = normalized["LeftFoot"]
        if "RightFootMod" not in normalized and "RightFoot" in normalized:
            normalized["RightFootMod"] = normalized["RightFoot"]

        # Spine2 fallback: use Spine3 or Spine1 if Spine2 is missing
        if "Spine2" not in normalized:
            if "Spine3" in normalized:
                normalized["Spine2"] = normalized["Spine3"]
            elif "Spine1" in normalized:
                normalized["Spine2"] = normalized["Spine1"]

        return normalized

    def _convert_frame(
        self, frame_ptr
    ) -> Optional[Dict[str, Tuple[np.ndarray, np.ndarray]]]:
        """Convert an SDK frame pointer into the GMR-compatible data structure."""
        if not frame_ptr:
            return None

        frame = frame_ptr.contents
        self.latest_frame_number = int(frame.iFrame)
        frame_map: Dict[str, Tuple[np.ndarray, np.ndarray]] = {}

        # Iterate over all skeletons
        for i_skeleton in range(frame.nSkeletons):
            sk = frame.Skeletons[i_skeleton]

            # Iterate over rigid body segments
            for i_body in range(sk.nRigidBodies):
                body = sk.RigidBodyData[i_body]
                body_id = int(body.ID)
                name = self._id_to_name.get(body_id)
                if not name:
                    # Unknown ID, skip
                    continue

                # Position unit in NOKOV is millimeters; convert to meters
                pos_m = np.array([body.x, body.y, body.z], dtype=np.float64) / 1000.0
                # SDK quaternion order is qx, qy, qz, qw; convert to wxyz
                quat_wxyz = np.array(
                    [body.qw, body.qx, body.qy, body.qz], dtype=np.float64
                )

                # Global alignment: rotate Y-up to Z-up
                pos_aligned = self._align_rot.apply(pos_m)
                rot_body = R.from_quat(quat_wxyz, scalar_first=True)
                rot_aligned = (self._align_rot * rot_body).as_quat(scalar_first=True)

                frame_map[name] = (pos_aligned, rot_aligned)

        if not frame_map:
            return None

        return self._normalize_names(frame_map)

    def _reader_loop(self) -> None:
        """Continuously read the latest frame, convert it, and push it into the queue."""
        while self._running:
            if not self._id_to_name:
                try:
                    self._build_id_name_map()
                except Exception:
                    pass

            frame_ptr = self._client.PyGetLastFrameOfMocapData()
            try:
                if frame_ptr:
                    converted = self._convert_frame(frame_ptr)
                    if converted is not None:
                        try:
                            self.queue.put(converted, block=False)
                        except Full:
                            # Drop the oldest frame to keep the newest one
                            try:
                                _ = self.queue.get(block=False)
                            except Exception:
                                pass
                            self.queue.put(converted, block=False)
            finally:
                if frame_ptr:
                    # Free underlying frame memory
                    self._client.PyNokovFreeFrame(frame_ptr)

            # Yield CPU time briefly
            time.sleep(0.0005)

    def run(self) -> bool:
        """Initialize the client connection and start the reader thread."""
        ret = self._client.Initialize(bytes(self.server_ip, encoding="utf8"))
        if ret != 0:
            print(f"[NokovClient] Failed to connect to NOKOV server, return code: {ret}")
            return False

        # Reduce SDK internal logging
        try:
            self._client.PySetVerbosityLevel(self._print_level)
        except Exception:
            pass

        # Build ID-to-name mapping
        self._build_id_name_map()

        self._running = True
        self._reader_thread = Thread(target=self._reader_loop, daemon=True)
        self._reader_thread.start()
        self._log("[NokovClient] Reader thread started")
        return True

    def shutdown(self) -> None:
        self._running = False
        if self._reader_thread and self._reader_thread.is_alive():
            self._reader_thread.join(timeout=1.0)

    def get_frame(self) -> Dict[str, Tuple[np.ndarray, np.ndarray]]:
        """Blocking call to retrieve the next frame of human data."""
        return self.queue.get(block=True)

    def get_frame_number(self) -> int:
        return self.latest_frame_number

    # Convenience alias
    def get(self) -> Dict[str, Tuple[np.ndarray, np.ndarray]]:
        return self.get_frame()


def setup_nokov(server_address: str, print_level: int = 0) -> Optional[NokovClient]:
    client = NokovClient(server_ip=server_address, print_level=print_level)
    ok = client.run()
    if not ok:
        return None
    return client

