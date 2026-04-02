import argparse
import json
import time
from typing import Optional, Tuple, List

import numpy as np
import mujoco as mj
import redis
from scipy.spatial.transform import Rotation as R

from general_motion_retargeting.nokov_vendor import setup_nokov
from general_motion_retargeting import GeneralMotionRetargeting as GMR


def wrap_to_pi(angle: float) -> float:
    """Wrap an angle to the range [-pi, pi]."""
    return (angle + np.pi) % (2 * np.pi) - np.pi


def compute_mimic_obs_from_qpos(
    qpos: np.ndarray,
    prev_root_pos: Optional[np.ndarray],
    prev_yaw: Optional[float],
    dt: Optional[float],
) -> Tuple[np.ndarray, np.ndarray, float, float]:
    """
    Build mimic_obs from the current qpos and previous state.

    Returns:
        mimic_obs, root_pos, yaw, yaw_rate
    """
    root_pos = qpos[:3].copy()
    root_quat_wxyz = qpos[3:7].copy()
    dof_pos = qpos[7:].copy()

    # SciPy expects quaternion order xyzw
    root_quat_xyzw = np.array([
        root_quat_wxyz[1],
        root_quat_wxyz[2],
        root_quat_wxyz[3],
        root_quat_wxyz[0],
    ])
    rot = R.from_quat(root_quat_xyzw)

    # roll, pitch, yaw (xyz intrinsic)
    roll, pitch, yaw = rot.as_euler("xyz", degrees=False)

    # Root linear velocity in world frame
    if prev_root_pos is not None and dt is not None and dt > 1e-6:
        root_vel_world = (root_pos - prev_root_pos) / dt
    else:
        root_vel_world = np.zeros(3, dtype=np.float64)

    # Convert to root local frame
    root_vel_local = rot.inv().apply(root_vel_world)

    # Yaw rate
    if prev_yaw is not None and dt is not None and dt > 1e-6:
        yaw_rate = wrap_to_pi(yaw - prev_yaw) / dt
    else:
        yaw_rate = 0.0

    mimic_obs = np.concatenate([
        root_pos[2:3],               # height (z)
        np.array([roll, pitch, yaw]),
        root_vel_local,              # local root velocity
        np.array([yaw_rate]),        # local yaw rate
        dof_pos,
    ]).astype(np.float32)

    return mimic_obs, root_pos, yaw, yaw_rate


def _get_joint_qpos(qpos: np.ndarray, model, joint_name: str) -> Optional[float]:
    try:
        jid = mj.mj_name2id(model, mj.mjtObj.mjOBJ_JOINT, joint_name)
        if jid < 0:
            return None
        qadr = model.jnt_qposadr[jid]
        return float(qpos[qadr])
    except Exception:
        return None


def build_dof25_for_twist(
    qpos: np.ndarray,
    model,
    wrist_axis_left: str = "roll",
    wrist_axis_right: str = "roll",
    wrist_left_sign: float = 1.0,
    wrist_right_sign: float = 1.0,
    wrist_left_offset_deg: float = 0.0,
    wrist_right_offset_deg: float = 0.0,
    right_arm_pitch_sign: float = 1.0,
    right_arm_roll_sign: float = 1.0,
    right_arm_yaw_sign: float = 1.0,
    right_elbow_sign: float = 1.0,
    right_arm_pitch_offset_deg: float = 0.0,
    right_arm_roll_offset_deg: float = 0.0,
    right_arm_yaw_offset_deg: float = 0.0,
    right_elbow_offset_deg: float = 0.0,
) -> np.ndarray:
    """
    Construct the 25-DoF joint vector expected by TWIST.

    Layout:
    - First 23 DoFs: body joints
      (left leg 6 + right leg 6 + torso 3 + left arm 4 + right arm 4)
    - Indices 19 and 24: wrist joints (configurable axis, sign, and offset)

    Note:
        Only one wrist axis (roll/yaw/pitch) is selected here.
        Other wrist DoFs are handled separately by the low-level controller.
    """
    body_order: List[str] = [
        # left leg (6)
        "left_hip_pitch_joint", "left_hip_roll_joint", "left_hip_yaw_joint",
        "left_knee_joint", "left_ankle_pitch_joint", "left_ankle_roll_joint",
        # right leg (6)
        "right_hip_pitch_joint", "right_hip_roll_joint", "right_hip_yaw_joint",
        "right_knee_joint", "right_ankle_pitch_joint", "right_ankle_roll_joint",
        # torso (3)
        "waist_yaw_joint", "waist_roll_joint", "waist_pitch_joint",
        # left arm (4)
        "left_shoulder_pitch_joint", "left_shoulder_roll_joint",
        "left_shoulder_yaw_joint", "left_elbow_joint",
        # right arm (4)
        "right_shoulder_pitch_joint", "right_shoulder_roll_joint",
        "right_shoulder_yaw_joint", "right_elbow_joint",
    ]

    axis_to_name = {
        "roll": ("left_wrist_roll_joint", "right_wrist_roll_joint"),
        "yaw": ("left_wrist_yaw_joint", "right_wrist_yaw_joint"),
        "pitch": ("left_wrist_pitch_joint", "right_wrist_pitch_joint"),
    }
    wrist_left = axis_to_name.get(wrist_axis_left, axis_to_name["roll"])[0]
    wrist_right = axis_to_name.get(wrist_axis_right, axis_to_name["roll"])[1]

    # Collect 23 body joint values
    body_vals: List[float] = []
    for name in body_order:
        v = _get_joint_qpos(qpos, model, name)
        if v is None:
            v = 0.0

        # Apply configurable sign and offset for right arm joints
        if name == "right_shoulder_pitch_joint":
            v = right_arm_pitch_sign * (v + np.deg2rad(right_arm_pitch_offset_deg))
        elif name == "right_shoulder_roll_joint":
            v = right_arm_roll_sign * (v + np.deg2rad(right_arm_roll_offset_deg))
        elif name == "right_shoulder_yaw_joint":
            v = right_arm_yaw_sign * (v + np.deg2rad(right_arm_yaw_offset_deg))
        elif name == "right_elbow_joint":
            v = right_elbow_sign * (v + np.deg2rad(right_elbow_offset_deg))

        body_vals.append(float(v))

    # Fill into 25-DoF layout, skipping indices 19 and 24 (reserved for wrists)
    dof25 = np.zeros(25, dtype=np.float32)
    bi = 0
    for pos in range(25):
        if pos in (19, 24):
            continue
        dof25[pos] = body_vals[bi]
        bi += 1

    # Fill wrist joints at indices 19 and 24
    wl = _get_joint_qpos(qpos, model, wrist_left)
    wr = _get_joint_qpos(qpos, model, wrist_right)
    if wl is not None:
        dof25[19] = wrist_left_sign * (wl + np.deg2rad(wrist_left_offset_deg))
    if wr is not None:
        dof25[24] = wrist_right_sign * (wr + np.deg2rad(wrist_right_offset_deg))

    return dof25


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--server_ip", type=str, required=True, help="NOKOV server IP")
    parser.add_argument("--robot_gmr", type=str, default="unitree_g1", help="Target robot for GMR (default: unitree_g1)")
    parser.add_argument("--human_height", type=float, default=1.6, help="Human height in meters for scale alignment")
    parser.add_argument("--offset_to_ground", action="store_true", help="Align human root to ground (recommended)")

    # Wrist / arm debug options
    parser.add_argument("--wrist_axis_left", type=str, default="roll", choices=["roll", "yaw", "pitch"],
                        help="Left wrist axis (roll/yaw/pitch)")
    parser.add_argument("--wrist_axis_right", type=str, default="yaw", choices=["roll", "yaw", "pitch"],
                        help="Right wrist axis (roll/yaw/pitch)")
    parser.add_argument("--wrist_left_sign", type=float, default=1.0, help="Left wrist sign (use -1 to invert)")
    parser.add_argument("--wrist_right_sign", type=float, default=-1.0, help="Right wrist sign (use -1 to invert)")
    parser.add_argument("--wrist_left_offset_deg", type=float, default=0.0, help="Left wrist zero offset (degrees)")
    parser.add_argument("--wrist_right_offset_deg", type=float, default=0.0, help="Right wrist zero offset (degrees)")

    # Right arm joint sign and offset (for quick alignment)
    parser.add_argument("--right_arm_pitch_sign", type=float, default=1.0)
    parser.add_argument("--right_arm_roll_sign", type=float, default=1.0)
    parser.add_argument("--right_arm_yaw_sign", type=float, default=1.0)
    parser.add_argument("--right_elbow_sign", type=float, default=1.0)
    parser.add_argument("--right_arm_pitch_offset_deg", type=float, default=0.0)
    parser.add_argument("--right_arm_roll_offset_deg", type=float, default=0.0)
    parser.add_argument("--right_arm_yaw_offset_deg", type=float, default=0.0)
    parser.add_argument("--right_elbow_offset_deg", type=float, default=0.0)

    parser.add_argument("--redis_host", type=str, default="localhost")
    parser.add_argument("--redis_port", type=int, default=6379)
    parser.add_argument("--freq", type=float, default=50.0, help="Publish frequency (Hz), used for rate limiting")

    args = parser.parse_args()

    # 1) NOKOV client
    client = setup_nokov(server_address=args.server_ip, print_level=0)
    if not client:
        print("Failed to initialize NOKOV client")
        exit(1)
    print(f"NOKOV client connected: {client.connected()}")

    # 2) GMR retargeting
    retarget = GMR(
        src_human="bvh_nokov",
        tgt_robot=args.robot_gmr,
        actual_human_height=args.human_height,
        use_velocity_limit=False,
    )

    # 3) Redis publisher
    r = redis.Redis(host=args.redis_host, port=args.redis_port, db=0)
    redis_key_mimic = "action_mimic_g1"   # Read by TWIST low-level controller
    redis_key_hand = "action_hand_g1"     # Hand command (unused -> zero)

    prev_t = None
    prev_root_pos = None
    prev_yaw = None

    control_dt = 1.0 / float(args.freq)
    last_pub = time.time()

    print(
        f"[GMR → TWIST] Start publishing mimic_obs to "
        f"Redis://{args.redis_host}:{args.redis_port} "
        f"key={redis_key_mimic} @~{args.freq:.1f}Hz"
    )

    # Initialization
    last_nokov_time = time.time()
    fps_nokov = 0.0
    last_print_time = time.time()

    while True:
        now = time.time()
        dt_nokov = now - last_nokov_time
        if dt_nokov > 0:
            fps_nokov = 1.0 / dt_nokov
        last_nokov_time = now

        frame = client.get_frame()

        if now - last_print_time > 1.0:
            print(f"[FPS] {fps_nokov:.1f}")
            last_print_time = now

        t_now = time.time()

        # GMR retargeting
        qpos = retarget.retarget(frame, offset_to_ground=args.offset_to_ground)

        # Build mimic_obs (TWIST expects 33 dims = 8 + 25)
        dt = (t_now - prev_t) if prev_t is not None else None
        mimic_head, root_pos, yaw, yaw_rate = compute_mimic_obs_from_qpos(
            qpos=qpos,
            prev_root_pos=prev_root_pos,
            prev_yaw=prev_yaw,
            dt=dt,
        )

        dof25 = build_dof25_for_twist(
            qpos, retarget.model,
            wrist_axis_left=args.wrist_axis_left,
            wrist_axis_right=args.wrist_axis_right,
            wrist_left_sign=args.wrist_left_sign,
            wrist_right_sign=args.wrist_right_sign,
            wrist_left_offset_deg=args.wrist_left_offset_deg,
            wrist_right_offset_deg=args.wrist_right_offset_deg,
            right_arm_pitch_sign=args.right_arm_pitch_sign,
            right_arm_roll_sign=args.right_arm_roll_sign,
            right_arm_yaw_sign=args.right_arm_yaw_sign,
            right_elbow_sign=args.right_elbow_sign,
            right_arm_pitch_offset_deg=args.right_arm_pitch_offset_deg,
            right_arm_roll_offset_deg=args.right_arm_roll_offset_deg,
            right_arm_yaw_offset_deg=args.right_arm_yaw_offset_deg,
            right_elbow_offset_deg=args.right_elbow_offset_deg,
        )

        mimic_obs = np.concatenate([mimic_head[:8], dof25], axis=0).astype(np.float32)

        # Rate limiting
        elapsed = t_now - last_pub
        if elapsed < control_dt:
            time.sleep(control_dt - elapsed)
        last_pub = time.time()

        # Publish mimic_obs
        r.set(redis_key_mimic, json.dumps(mimic_obs.tolist()))
        # Optional: publish hand targets (set to zero here)
        # r.set(redis_key_hand, json.dumps([0.0] * 14))

        # Update previous state
        prev_t = t_now
        prev_root_pos = root_pos
        prev_yaw = yaw


if __name__ == "__main__":
    main()

