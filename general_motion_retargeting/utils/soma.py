"""Loader for SOMA-format BVH files.

Used by ``general_motion_retargeting.utils.lafan1.load_bvh_file`` when
``format="soma"``. Mirrors the public contract of the LAFAN1 / Nokov loader:
returns ``(frames, human_height)`` where each frame is a
``dict[str, [position(3,), orientation(4,)]]`` in world space, with
scalar-first quaternions and positions in meters.

SOMA BVH files (e.g. from soma-retargeter samples, SEED dataset) use a
Mixamo-style skeleton with ``Root -> Hips -> Spine1/.../Chest`` and
``LeftLeg/LeftShin/LeftFoot/LeftToeBase`` on the legs. The ``Root`` and
``Hips`` joints carry 6 channels (translation + rotation) while the rest
carry only 3 rotation channels, which is why a dedicated parser is needed
(the vendored LAFAN reader assumes a single channel count per file).
"""

import re

import numpy as np
from scipy.spatial.transform import Rotation as R

from .lafan_vendor import utils as fk_utils


_POS_CHANNELS = ("Xposition", "Yposition", "Zposition")
_ROT_CHANNELS = ("Xrotation", "Yrotation", "Zrotation")
_CHANNEL_RE = re.compile(r"\s*CHANNELS\s+(\d+)\s+(.+)")
_JOINT_RE = re.compile(r"\s*(ROOT|JOINT)\s+(\S+)")
_OFFSET_RE = re.compile(
    r"\s*OFFSET\s+([\-\d\.eE]+)\s+([\-\d\.eE]+)\s+([\-\d\.eE]+)"
)
_FRAMES_RE = re.compile(r"\s*Frames:\s+(\d+)")
_FRAME_TIME_RE = re.compile(r"\s*Frame Time:\s+([\d\.eE]+)")


def _parse_bvh(bvh_file):
    """Parse a BVH with possibly mixed per-joint channel counts.

    Returns a dict with:
        names: list[str]
        parents: np.ndarray[int] (N,)
        offsets: np.ndarray[float32] (N, 3) in BVH units (typically cm)
        channels: list[list[str]] per-joint channel names, in file order
        motion: np.ndarray[float32] (F, total_channels) raw motion values
        frame_time: float (seconds per frame)
    """
    names = []
    parents = []
    offsets = []
    channels = []

    stack = []
    end_site = False
    in_motion = False
    frames_total = None
    frame_time = None

    motion_rows = []

    with open(bvh_file, "r", encoding="utf-8") as f:
        for line in f:
            if not in_motion:
                if "MOTION" in line:
                    in_motion = True
                    continue

                jmatch = _JOINT_RE.match(line)
                if jmatch:
                    names.append(jmatch.group(2))
                    parents.append(stack[-1] if stack else -1)
                    offsets.append([0.0, 0.0, 0.0])
                    channels.append([])
                    stack.append(len(names) - 1)
                    continue

                if "End Site" in line:
                    end_site = True
                    continue

                if "{" in line:
                    continue

                if "}" in line:
                    if end_site:
                        end_site = False
                    else:
                        stack.pop()
                    continue

                ommatch = _OFFSET_RE.match(line)
                if ommatch and not end_site:
                    offsets[stack[-1]] = [float(v) for v in ommatch.groups()]
                    continue

                chmatch = _CHANNEL_RE.match(line)
                if chmatch:
                    tokens = chmatch.group(2).split()
                    channels[stack[-1]] = tokens
                    continue
            else:
                fmatch = _FRAMES_RE.match(line)
                if fmatch:
                    frames_total = int(fmatch.group(1))
                    continue

                tmatch = _FRAME_TIME_RE.match(line)
                if tmatch:
                    frame_time = float(tmatch.group(1))
                    continue

                stripped = line.strip()
                if not stripped:
                    continue
                motion_rows.append([float(v) for v in stripped.split()])

    if frame_time is None:
        raise ValueError(f"Could not find 'Frame Time' in BVH file: {bvh_file}")

    motion = np.asarray(motion_rows, dtype=np.float32)
    if frames_total is not None and motion.shape[0] != frames_total:
        motion = motion[:frames_total]

    return {
        "names": names,
        "parents": np.asarray(parents, dtype=np.int32),
        "offsets": np.asarray(offsets, dtype=np.float32),
        "channels": channels,
        "motion": motion,
        "frame_time": frame_time,
    }


def _extract_local_pose(parsed):
    """Convert raw motion data into per-joint local positions and quaternions.

    Returns:
        local_pos: (F, N, 3) float32 local positions (in BVH units)
        local_quat: (F, N, 4) float32 local quaternions (scalar-first)
    """
    names = parsed["names"]
    offsets = parsed["offsets"]
    motion = parsed["motion"]
    channels = parsed["channels"]

    num_frames = motion.shape[0]
    num_joints = len(names)

    local_pos = np.tile(offsets[None, :, :], (num_frames, 1, 1)).astype(np.float32)
    local_quat = np.zeros((num_frames, num_joints, 4), dtype=np.float32)
    local_quat[..., 0] = 1.0  # identity (wxyz, scalar-first)

    cursor = 0
    for j, joint_channels in enumerate(channels):
        if not joint_channels:
            continue

        joint_slice = motion[:, cursor:cursor + len(joint_channels)]
        cursor += len(joint_channels)

        # SOMA (and MotionBuilder/Mixamo-exported) BVHs interpret channel order
        # "Zrotation Yrotation Xrotation" as successive world-axis rotations
        # composed as ``q = q_Z * q_Y * q_X`` -- i.e. scipy's *extrinsic*
        # convention (uppercase letters). Using the lowercase / intrinsic form
        # produces visually similar but numerically different quaternions and
        # causes all joints below the root to drift away from their correct
        # world-space pose. This matches soma-retargeter's Warp kernel:
        # ``for ch in rot_order: q *= axis_quat(ch, angle[ch])``.
        rot_order = ""
        rot_values = []
        for col, ch in enumerate(joint_channels):
            if ch == "Xposition":
                local_pos[:, j, 0] = joint_slice[:, col]
            elif ch == "Yposition":
                local_pos[:, j, 1] = joint_slice[:, col]
            elif ch == "Zposition":
                local_pos[:, j, 2] = joint_slice[:, col]
            elif ch in _ROT_CHANNELS:
                rot_order += ch[0].upper()
                rot_values.append(joint_slice[:, col])
            else:
                raise ValueError(
                    f"Unsupported BVH channel '{ch}' on joint '{names[j]}'"
                )

        if rot_order:
            eulers_deg = np.stack(rot_values, axis=-1)  # (F, 3) in rot_order
            quat_xyzw = R.from_euler(rot_order, eulers_deg, degrees=True).as_quat()
            local_quat[:, j, 0] = quat_xyzw[:, 3]
            local_quat[:, j, 1:] = quat_xyzw[:, :3]

    return local_pos, local_quat


def load_soma_bvh_file(bvh_file):
    """Load a SOMA-format BVH file and convert it to GMR's per-frame dict.

    Args:
        bvh_file: Path to a SOMA BVH motion file.

    Returns:
        frames: list of dicts mapping bone name to ``[position, orientation]``.
            ``position`` is a (3,) numpy array in meters, ``orientation`` a
            (4,) numpy array quaternion in ``wxyz`` (scalar-first) order.
        human_height: float, nominal human height in meters used by the
            retargeter's scale logic (see ``human_height_assumption`` in the
            IK config).
    """
    parsed = _parse_bvh(bvh_file)
    names = parsed["names"]
    parents = parsed["parents"].tolist()

    local_pos, local_quat = _extract_local_pose(parsed)

    # Forward kinematics to get global positions and orientations.
    global_quat, global_pos = fk_utils.quat_fk(local_quat, local_pos, parents)

    # World-frame fix + cm -> m, matching the LAFAN1 / Nokov loader conventions.
    rotation_matrix = np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]], dtype=np.float32)
    rotation_quat = R.from_matrix(rotation_matrix).as_quat(scalar_first=True).astype(
        np.float32
    )

    frames = []
    for frame in range(global_pos.shape[0]):
        result = {}
        for i, bone in enumerate(names):
            orientation = fk_utils.quat_mul(rotation_quat, global_quat[frame, i])
            position = global_pos[frame, i] @ rotation_matrix.T / 100.0
            result[bone] = [position, orientation]

        # Virtual "FootMod" targets, consistent with LAFAN1 / Nokov loaders:
        # foot position, toe base orientation (SOMA uses LeftToeBase/RightToeBase).
        if "LeftFoot" in result and "LeftToeBase" in result:
            result["LeftFootMod"] = [result["LeftFoot"][0], result["LeftToeBase"][1]]
        if "RightFoot" in result and "RightToeBase" in result:
            result["RightFootMod"] = [result["RightFoot"][0], result["RightToeBase"][1]]

        frames.append(result)

    # SOMA BVHs typically come from a uniform-proportion skeleton; 1.70 m matches
    # the model_height used by the NVIDIA soma-retargeter G1 config.
    human_height = 1.70

    return frames, human_height
