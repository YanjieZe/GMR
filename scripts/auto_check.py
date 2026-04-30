#!/usr/bin/env python3
"""
Auto check robot motions for abnormalities:
1. Floating detection: Both feet off ground for extended periods
2. Joint limit violation: Joint angles exceeding robot limits

Judgment criteria:
- Floating: Both feet simultaneously off ground (height > threshold) for > 3s OR > 50% of frames
- Joint limits: Any joint angle exceeds lower or upper limit at any frame
"""

import argparse
import json
import os
from collections import defaultdict
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import List, Optional, Dict, Tuple

import numpy as np
import torch
import mujoco as mj

from general_motion_retargeting.data_loader import load_robot_motion
from general_motion_retargeting.kinematics_model import KinematicsModel
from general_motion_retargeting.params import ROBOT_XML_DICT, ROBOT_BASE_DICT

DEFAULT_FOOT_KEYS = [
    "left_ankle_roll_link",
    "right_ankle_roll_link",
    "left_toe_link",
    "right_toe_link",
    "left_foot_link",
    "right_foot_link",
]

OFF_GROUND_THRESHOLD = 0.12  # 12cm above ground (stricter threshold)
MIN_CONTINUOUS_SECONDS = 1.0
MIN_CONTINUOUS_RATIO = 0.25

SELF_COLLISION_MIN_SECONDS = 0.6
SELF_COLLISION_MIN_RATIO = 0.10

# contact_dict-style filters to keep only meaningful self-collisions
# `pairs`: optional whitelist of (body_a, body_b) tuples (sorted names)
# `min_penetration`: minimum penetration depth (in meters) to count a collision
SELF_COLLISION_CONTACT_DICT = {
    "default": {
        "pairs": [],
        "min_penetration": 0.003,
    },
}

# Joint limit violation thresholds
JOINT_LIMIT_TOLERANCE = 0.005  # Tolerance in radians (~1.15 degrees): only flag if violation exceeds this amount
MIN_JOINT_VIOLATION_RATIO = 0.05  # Minimum ratio of frames with violations to flag as abnormal (10%)

# Joint discontinuity thresholds
MAX_JOINT_JUMP = 0.5  # Maximum allowed joint angle change between consecutive frames (radians, ~29 degrees)
MIN_JOINT_JUMP_RATIO = 0.05  # Minimum ratio of frames with jumps to flag as abnormal (5%)
SEVERE_JOINT_JUMP = 1.0  # Severe jump threshold in radians (~57 degrees): always flag even if ratio is low


@dataclass
class FloatingInfo:
    is_floating: bool
    total_frames: int
    fps: float
    total_duration: float
    max_continuous_off_ground_frames: int
    max_continuous_off_ground_seconds: float
    max_continuous_off_ground_ratio: float
    total_off_ground_frames: int
    total_off_ground_ratio: float
    ground_level: float
    foot_heights_min: float
    foot_heights_max: float
    foot_heights_mean: float
    violation_reason: Optional[str] = None


@dataclass
class JointLimitInfo:
    has_limit_violation: bool
    total_frames: int
    num_violation_frames: int
    violation_ratio: float
    violated_joints: List[int] = field(default_factory=list)
    max_violation_per_joint: Dict[int, float] = field(default_factory=dict)
    violation_details: Optional[str] = None


@dataclass
class JointDiscontinuityInfo:
    has_discontinuity: bool
    total_frames: int
    num_discontinuity_frames: int
    discontinuity_ratio: float
    max_jump_rad: float
    max_jump_deg: float
    max_jump_frame: int
    max_jump_joint: int
    jumped_joints: List[int] = field(default_factory=list)
    discontinuity_details: Optional[str] = None


@dataclass
class CheckReport:
    motion_file: str
    is_abnormal: bool  # True if floating, joint limit violation, or discontinuity
    floating: FloatingInfo
    joint_limits: JointLimitInfo
    joint_discontinuity: JointDiscontinuityInfo
    self_collision: "SelfCollisionInfo"


@dataclass
class SelfCollisionInfo:
    has_self_collision: bool
    total_frames: int
    collision_frames: int
    collision_ratio: float
    max_continuous_collision_frames: int
    max_continuous_collision_seconds: float
    max_continuous_collision_ratio: float
    total_collision_events: int
    top_collision_pairs: List[str]
    violation_reason: Optional[str] = None


def get_mujoco_rendered_data(
    root_pos: np.ndarray,
    root_rot: np.ndarray,
    dof_pos: np.ndarray,
    robot_type: str,
) -> tuple:
    """Render motion data through MuJoCo and get actual joint positions, body positions, and collisions.
    
    Returns:
        actual_dof_pos: (T, N) actual joint angles from MuJoCo (may be clipped)
        actual_body_pos: (T, M, 3) actual world positions of all bodies from MuJoCo
        body_names: List of body names
        collisions_by_frame: List[List[Tuple[str, str, float]]] collisions per frame
    """
    if robot_type not in ROBOT_XML_DICT:
        raise ValueError(f"Unknown robot type: {robot_type}")
    
    xml_file = ROBOT_XML_DICT[robot_type]
    model = mj.MjModel.from_xml_path(str(xml_file))
    data = mj.MjData(model)
    
    total_frames = len(root_pos)
    num_dof = len(dof_pos[0]) if len(dof_pos.shape) > 1 else 0
    num_bodies = model.nbody
    num_geoms = model.ngeom
    
    actual_dof_pos = np.zeros((total_frames, num_dof))
    actual_body_pos = np.zeros((total_frames, num_bodies, 3))
    body_names = []
    geom_names = []
    collisions_by_frame: List[List[Tuple[str, str, float]]] = [[] for _ in range(total_frames)]
    
    filter_cfg = SELF_COLLISION_CONTACT_DICT.get(
        robot_type, SELF_COLLISION_CONTACT_DICT.get("default", {})
    )
    pair_whitelist = {
        tuple(sorted(pair)) for pair in filter_cfg.get("pairs", []) if len(pair) == 2
    }
    min_penetration = filter_cfg.get("min_penetration", 0.0)
    
    # Get body and geom names
    for i in range(num_bodies):
        name = mj.mj_id2name(model, mj.mjtObj.mjOBJ_BODY, i)
        body_names.append(name if name is not None else f"body_{i}")
    for i in range(num_geoms):
        name = mj.mj_id2name(model, mj.mjtObj.mjOBJ_GEOM, i)
        geom_names.append(name if name is not None else f"geom_{i}")
    
    # Render each frame through MuJoCo
    for frame_idx in range(total_frames):
        # Set joint positions
        data.qpos[:3] = root_pos[frame_idx]
        data.qpos[3:7] = root_rot[frame_idx]  # quat scalar first for MuJoCo
        data.qpos[7:] = dof_pos[frame_idx]
        
        # Forward kinematics + collision detection
        mj.mj_forward(model, data)
        
        # Get actual joint angles (after potential clipping)
        actual_dof_pos[frame_idx] = data.qpos[7:].copy()
        
        # Get actual body positions in world frame
        actual_body_pos[frame_idx] = data.xpos.copy()
        
        # Collect self-collisions (exclude world/environment geoms)
        if data.ncon > 0:
            frame_collisions = collisions_by_frame[frame_idx]
            for c_idx in range(data.ncon):
                contact = data.contact[c_idx]
                geom1 = contact.geom1
                geom2 = contact.geom2
                if geom1 < 0 or geom2 < 0:
                    continue
                body1 = model.geom_bodyid[geom1]
                body2 = model.geom_bodyid[geom2]
                # Skip contacts involving world/ground (body id 0)
                if body1 <= 0 or body2 <= 0:
                    continue
                body_pair = tuple(sorted((body_names[body1], body_names[body2])))
                if pair_whitelist and body_pair not in pair_whitelist:
                    continue
                penetration = max(0.0, -float(contact.dist))
                if penetration < min_penetration:
                    continue
                frame_collisions.append(
                    (body_pair[0], body_pair[1], penetration)
                )
    
    return actual_dof_pos, actual_body_pos, body_names, collisions_by_frame


def calculate_foot_world_heights(
    root_pos: np.ndarray,
    body_pos: np.ndarray,
    link_names: List[str],
    foot_names: List[str],
    is_world_positions: bool = False,
) -> dict:
    """Calculate world heights for each foot link.
    
    Args:
        root_pos: (T, 3) root position (used if body_pos is local)
        body_pos: (T, N, 3) body positions (either local or world frame)
        link_names: List of link/body names
        foot_names: List of foot link names to check
        is_world_positions: If True, body_pos is in world frame (from MuJoCo data.xpos)
    """
    foot_heights = {}
    FOOT_BOTTOM_OFFSET = -0.03
    
    for foot_name in foot_names:
        if foot_name not in link_names:
            continue
        foot_idx = link_names.index(foot_name)
        
        if is_world_positions:
            # body_pos is already in world frame (from MuJoCo data.xpos)
            world_heights = body_pos[:, foot_idx, 2]
        else:
            # body_pos is in local frame, need to add root_pos
            link_center_height = root_pos[:, 2] + body_pos[:, foot_idx, 2]
            world_heights = link_center_height
        
        # Apply foot bottom offset for ankle_roll_link
        if "ankle_roll_link" in foot_name:
            world_heights = world_heights + FOOT_BOTTOM_OFFSET
        
        foot_heights[foot_name] = world_heights
    return foot_heights


def find_max_continuous_off_ground(mask: np.ndarray) -> tuple:
    """Find maximum continuous sequence of True values in mask."""
    if mask.size == 0:
        return (0, -1, -1)
    
    max_length = 0
    max_start = -1
    max_end = -1
    
    current_length = 0
    current_start = -1
    
    for i, value in enumerate(mask):
        if value:
            if current_length == 0:
                current_start = i
            current_length += 1
            if current_length > max_length:
                max_length = current_length
                max_start = current_start
                max_end = i
        else:
            current_length = 0
            current_start = -1
    
    return (max_length, max_start, max_end)


def detect_floating(
    root_pos: np.ndarray,
    body_pos: np.ndarray,
    link_body_list: List[str],
    fps: float,
    foot_names: List[str] = None,
    height_threshold: float = OFF_GROUND_THRESHOLD,
    min_seconds: float = MIN_CONTINUOUS_SECONDS,
    min_ratio: float = MIN_CONTINUOUS_RATIO,
    is_world_positions: bool = False,
) -> FloatingInfo:
    """Detect if robot is floating.
    
    Args:
        root_pos: (T, 3) root position
        body_pos: (T, N, 3) body positions (local or world frame)
        link_body_list: List of body names
        fps: Frames per second
        foot_names: List of foot link names to check
        height_threshold: Height threshold for off-ground detection
        min_seconds: Minimum continuous seconds off-ground
        min_ratio: Minimum ratio of frames off-ground
        is_world_positions: If True, body_pos is in world frame (from MuJoCo)
    """
    if foot_names is None:
        foot_names = DEFAULT_FOOT_KEYS
    
    foot_heights = calculate_foot_world_heights(
        root_pos, body_pos, link_body_list, foot_names, is_world_positions=is_world_positions
    )
    
    if not foot_heights:
        # Return default info if no feet found
        return FloatingInfo(
            is_floating=False,
            total_frames=len(root_pos),
            fps=fps,
            total_duration=len(root_pos) / fps if fps > 0 else 0.0,
            max_continuous_off_ground_frames=0,
            max_continuous_off_ground_seconds=0.0,
            max_continuous_off_ground_ratio=0.0,
            total_off_ground_frames=0,
            total_off_ground_ratio=0.0,
            ground_level=0.0,
            foot_heights_min=0.0,
            foot_heights_max=0.0,
            foot_heights_mean=0.0,
            violation_reason="No valid foot links found",
        )
    
    # Find left and right foot
    left_foot = None
    right_foot = None
    
    for name in ["left_ankle_roll_link", "left_toe_link", "left_foot_link"]:
        if name in foot_heights:
            left_foot = foot_heights[name]
            break
    
    for name in ["right_ankle_roll_link", "right_toe_link", "right_foot_link"]:
        if name in foot_heights:
            right_foot = foot_heights[name]
            break
    
    if left_foot is None or right_foot is None:
        available_feet = list(foot_heights.values())
        if len(available_feet) < 2:
            return FloatingInfo(
                is_floating=False,
                total_frames=len(root_pos),
                fps=fps,
                total_duration=len(root_pos) / fps if fps > 0 else 0.0,
                max_continuous_off_ground_frames=0,
                max_continuous_off_ground_seconds=0.0,
                max_continuous_off_ground_ratio=0.0,
                total_off_ground_frames=0,
                total_off_ground_ratio=0.0,
                ground_level=0.0,
                foot_heights_min=0.0,
                foot_heights_max=0.0,
                foot_heights_mean=0.0,
                violation_reason=f"Need at least 2 feet, found {len(available_feet)}",
            )
        left_foot = available_feet[0]
        right_foot = available_feet[1]
    
    ground_level = 0.0
    
    left_off_ground = left_foot > (ground_level + height_threshold)
    right_off_ground = right_foot > (ground_level + height_threshold)
    both_feet_off_ground = left_off_ground & right_off_ground
    
    total_frames = len(both_feet_off_ground)
    total_duration = total_frames / fps if fps > 0 else 0.0
    
    max_continuous_frames, start_idx, end_idx = find_max_continuous_off_ground(
        both_feet_off_ground
    )
    max_continuous_seconds = max_continuous_frames / fps if fps > 0 else 0.0
    max_continuous_ratio = max_continuous_frames / total_frames if total_frames > 0 else 0.0
    
    total_off_ground_frames = int(np.sum(both_feet_off_ground))
    total_off_ground_ratio = total_off_ground_frames / total_frames if total_frames > 0 else 0.0
    
    all_foot_heights = np.concatenate([left_foot, right_foot])
    foot_heights_min = float(np.min(all_foot_heights))
    foot_heights_max = float(np.max(all_foot_heights))
    foot_heights_mean = float(np.mean(all_foot_heights))
    
    is_floating = False
    violation_reason = None
    
    if max_continuous_seconds >= min_seconds:
        is_floating = True
        violation_reason = f"Continuous {max_continuous_seconds:.2f}s >= {min_seconds}s"
    elif max_continuous_ratio >= min_ratio:
        is_floating = True
        violation_reason = f"Continuous ratio {max_continuous_ratio:.2%} >= {min_ratio:.2%}"
    
    return FloatingInfo(
        is_floating=is_floating,
        total_frames=total_frames,
        fps=fps,
        total_duration=total_duration,
        max_continuous_off_ground_frames=max_continuous_frames,
        max_continuous_off_ground_seconds=max_continuous_seconds,
        max_continuous_off_ground_ratio=max_continuous_ratio,
        total_off_ground_frames=total_off_ground_frames,
        total_off_ground_ratio=total_off_ground_ratio,
        ground_level=float(ground_level),
        foot_heights_min=foot_heights_min,
        foot_heights_max=foot_heights_max,
        foot_heights_mean=foot_heights_mean,
        violation_reason=violation_reason,
    )


def detect_joint_limit_violation(
    dof_pos: np.ndarray,
    lower_limits: np.ndarray,
    upper_limits: np.ndarray,
    fps: float,
    tolerance: float = JOINT_LIMIT_TOLERANCE,
    min_violation_ratio: float = MIN_JOINT_VIOLATION_RATIO,
) -> JointLimitInfo:
    """Detect if any joint angles exceed limits."""
    if len(dof_pos.shape) != 2:
        raise ValueError(f"Expected dof_pos shape (T, N), got {dof_pos.shape}")
    
    total_frames, num_joints = dof_pos.shape
    
    if len(lower_limits) != num_joints or len(upper_limits) != num_joints:
        return JointLimitInfo(
            has_limit_violation=False,
            total_frames=total_frames,
            num_violation_frames=0,
            violation_ratio=0.0,
            violated_joints=[],
            max_violation_per_joint={},
            violation_details=f"Joint count mismatch: dof_pos has {num_joints} joints, limits have {len(lower_limits)}",
        )
    
    # Convert to numpy if torch tensors
    if isinstance(lower_limits, torch.Tensor):
        lower_limits = lower_limits.cpu().numpy()
    if isinstance(upper_limits, torch.Tensor):
        upper_limits = upper_limits.cpu().numpy()
    
    # Check violations: below lower limit or above upper limit
    # First check if values are beyond limits (without tolerance - any violation counts)
    below_lower = dof_pos < lower_limits[None, :]  # (T, N)
    above_upper = dof_pos > upper_limits[None, :]  # (T, N)
    violations = below_lower | above_upper  # (T, N)
    
    # Per-frame violation mask (any joint violated)
    frame_violations = np.any(violations, axis=1)  # (T,)
    num_violation_frames = int(np.sum(frame_violations))
    violation_ratio = num_violation_frames / total_frames if total_frames > 0 else 0.0
    
    # Find violated joints (joints that have at least one violation)
    joint_violations = np.any(violations, axis=0)  # (N,)
    violated_joints = [int(i) for i in np.where(joint_violations)[0]]
    
    # Calculate maximum violation amount per joint (only count violations exceeding tolerance)
    # Use tolerance to filter out minor numerical errors, but still report all violations
    max_violation_per_joint = {}
    for joint_idx in violated_joints:
        violations_below = np.where(below_lower[:, joint_idx])[0]
        violations_above = np.where(above_upper[:, joint_idx])[0]
        
        max_violation = 0.0
        if len(violations_below) > 0:
            violations_below_amounts = lower_limits[joint_idx] - dof_pos[violations_below, joint_idx]
            # Only count violations that exceed tolerance
            significant_violations = violations_below_amounts[violations_below_amounts > tolerance]
            if len(significant_violations) > 0:
                max_violation = float(np.max(significant_violations))
        if len(violations_above) > 0:
            violations_above_amounts = dof_pos[violations_above, joint_idx] - upper_limits[joint_idx]
            # Only count violations that exceed tolerance
            significant_violations = violations_above_amounts[violations_above_amounts > tolerance]
            if len(significant_violations) > 0:
                max_violation = max(max_violation, float(np.max(significant_violations)))
        
        if max_violation > 0:
            max_violation_per_joint[joint_idx] = float(max_violation)
    
    # Only flag as violation if violation ratio exceeds minimum threshold
    has_limit_violation = violation_ratio >= min_violation_ratio
    
    violation_details = None
    if has_limit_violation:
        violation_details = f"{num_violation_frames}/{total_frames} frames ({violation_ratio:.2%}) violated limits (threshold: {min_violation_ratio:.2%}, tolerance: {tolerance:.4f} rad)"
    elif num_violation_frames > 0:
        # There were violations but below the ratio threshold
        violation_details = f"{num_violation_frames}/{total_frames} frames ({violation_ratio:.2%}) violated limits (below threshold {min_violation_ratio:.2%})"
    
    return JointLimitInfo(
        has_limit_violation=has_limit_violation,
        total_frames=total_frames,
        num_violation_frames=num_violation_frames,
        violation_ratio=violation_ratio,
        violated_joints=violated_joints,
        max_violation_per_joint=max_violation_per_joint,
        violation_details=violation_details,
    )


def detect_joint_discontinuity(
    dof_pos: np.ndarray,
    fps: float,
    max_jump: float = MAX_JOINT_JUMP,
    min_jump_ratio: float = MIN_JOINT_JUMP_RATIO,
    severe_jump: float = SEVERE_JOINT_JUMP,
) -> JointDiscontinuityInfo:
    """Detect sudden jumps/discontinuities in joint angles between consecutive frames."""
    if len(dof_pos.shape) != 2:
        raise ValueError(f"Expected dof_pos shape (T, N), got {dof_pos.shape}")
    
    total_frames, num_joints = dof_pos.shape
    
    if total_frames < 2:
        return JointDiscontinuityInfo(
            has_discontinuity=False,
            total_frames=total_frames,
            num_discontinuity_frames=0,
            discontinuity_ratio=0.0,
            max_jump_rad=0.0,
            max_jump_deg=0.0,
            max_jump_frame=-1,
            max_jump_joint=-1,
            jumped_joints=[],
            discontinuity_details="Insufficient frames for discontinuity detection",
        )
    
    # Calculate frame-to-frame changes
    joint_changes = np.abs(np.diff(dof_pos, axis=0))  # (T-1, N)
    
    # Find frames with jumps exceeding threshold
    large_jumps = joint_changes > max_jump  # (T-1, N)
    
    # Per-frame discontinuity mask (any joint has large jump)
    frame_discontinuities = np.any(large_jumps, axis=1)  # (T-1,)
    num_discontinuity_frames = int(np.sum(frame_discontinuities))
    discontinuity_ratio = num_discontinuity_frames / (total_frames - 1) if total_frames > 1 else 0.0
    
    # Find joints with jumps
    joint_has_jumps = np.any(large_jumps, axis=0)  # (N,)
    jumped_joints = [int(i) for i in np.where(joint_has_jumps)[0]]
    
    # Find maximum jump (always, not just when exceeding threshold)
    max_jump_idx_1d = np.argmax(joint_changes)
    max_jump_frame_idx = max_jump_idx_1d // num_joints
    max_jump_joint_idx = max_jump_idx_1d % num_joints
    max_jump_value = joint_changes[max_jump_frame_idx, max_jump_joint_idx]
    
    # Frame index where jump occurs (jump is between frame and frame+1)
    max_jump_frame = int(max_jump_frame_idx)
    max_jump_joint = int(max_jump_joint_idx)
    max_jump_rad = float(max_jump_value)
    max_jump_deg = float(max_jump_value * 180.0 / np.pi)
    
    # Flag as discontinuity if:
    # 1. Ratio exceeds minimum threshold, OR
    # 2. Maximum jump exceeds severe threshold (always flag severe jumps)
    has_discontinuity = (discontinuity_ratio >= min_jump_ratio) or (max_jump_rad >= severe_jump)
    
    discontinuity_details = None
    if has_discontinuity:
        if max_jump_rad >= severe_jump:
            discontinuity_details = (
                f"SEVERE jump detected: {max_jump_deg:.2f} deg at frame {max_jump_frame+1} (joint {max_jump_joint}) "
                f"(exceeds severe threshold {severe_jump*180/np.pi:.1f} deg)"
            )
        else:
            discontinuity_details = (
                f"{num_discontinuity_frames} frame transitions ({discontinuity_ratio:.2%}) have jumps > {max_jump:.3f} rad. "
                f"Max jump: {max_jump_deg:.2f} deg at frame {max_jump_frame+1} (joint {max_jump_joint})"
            )
    elif max_jump_rad > 0:
        discontinuity_details = (
            f"Found jump of {max_jump_deg:.2f} deg at frame {max_jump_frame+1} (joint {max_jump_joint}) "
            f"(below threshold ratio {min_jump_ratio:.2%})"
        )
    
    return JointDiscontinuityInfo(
        has_discontinuity=has_discontinuity,
        total_frames=total_frames,
        num_discontinuity_frames=num_discontinuity_frames,
        discontinuity_ratio=discontinuity_ratio,
        max_jump_rad=max_jump_rad,
        max_jump_deg=max_jump_deg,
        max_jump_frame=max_jump_frame + 1 if max_jump_frame >= 0 else -1,  # Report as frame where jump occurs
        max_jump_joint=max_jump_joint,
        jumped_joints=jumped_joints,
        discontinuity_details=discontinuity_details,
    )


def detect_self_collisions(
    collisions_by_frame: List[List[Tuple[str, str, float]]],
    fps: float,
    min_seconds: float = SELF_COLLISION_MIN_SECONDS,
    min_ratio: float = SELF_COLLISION_MIN_RATIO,
) -> SelfCollisionInfo:
    total_frames = len(collisions_by_frame)
    if total_frames == 0:
        return SelfCollisionInfo(
            has_self_collision=False,
            total_frames=0,
            collision_frames=0,
            collision_ratio=0.0,
            max_continuous_collision_frames=0,
            max_continuous_collision_seconds=0.0,
            max_continuous_collision_ratio=0.0,
            total_collision_events=0,
            top_collision_pairs=[],
            violation_reason=None,
        )
    
    collision_mask = np.array([len(frame) > 0 for frame in collisions_by_frame], dtype=bool)
    collision_frames = int(collision_mask.sum())
    collision_ratio = collision_frames / total_frames if total_frames > 0 else 0.0
    
    max_frames, start_idx, end_idx = find_max_continuous_off_ground(collision_mask)
    max_seconds = max_frames / fps if fps > 0 else 0.0
    max_ratio = max_frames / total_frames if total_frames > 0 else 0.0
    
    # Count collision pairs
    pair_counts: Dict[Tuple[str, str], int] = defaultdict(int)
    total_events = 0
    for frame in collisions_by_frame:
        for geom1, geom2, _ in frame:
            key = tuple(sorted((geom1, geom2)))
            pair_counts[key] += 1
            total_events += 1
    
    top_pairs = [
        f"{a} <-> {b} ({count} frames)"
        for (a, b), count in sorted(pair_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    ]
    
    has_self_collision = (collision_ratio >= min_ratio) or (max_seconds >= min_seconds)
    violation_reason = None
    if has_self_collision:
        reason_parts = []
        if collision_ratio >= min_ratio:
            reason_parts.append(f"collision ratio {collision_ratio:.2%} ≥ {min_ratio:.2%}")
        if max_seconds >= min_seconds:
            reason_parts.append(f"continuous {max_seconds:.2f}s ≥ {min_seconds:.2f}s")
        violation_reason = "; ".join(reason_parts)
    
    return SelfCollisionInfo(
        has_self_collision=has_self_collision,
        total_frames=total_frames,
        collision_frames=collision_frames,
        collision_ratio=collision_ratio,
        max_continuous_collision_frames=max_frames,
        max_continuous_collision_seconds=max_seconds,
        max_continuous_collision_ratio=max_ratio,
        total_collision_events=total_events,
        top_collision_pairs=top_pairs,
        violation_reason=violation_reason,
    )


def check_motion(
    motion_file: str,
    robot_type: str,
    foot_names: List[str] = None,
    height_threshold: float = OFF_GROUND_THRESHOLD,
    min_seconds: float = MIN_CONTINUOUS_SECONDS,
    min_ratio: float = MIN_CONTINUOUS_RATIO,
    joint_limit_tolerance: float = JOINT_LIMIT_TOLERANCE,
    min_joint_violation_ratio: float = MIN_JOINT_VIOLATION_RATIO,
    max_joint_jump: float = MAX_JOINT_JUMP,
    min_jump_ratio: float = MIN_JOINT_JUMP_RATIO,
    severe_joint_jump: float = SEVERE_JOINT_JUMP,
) -> Optional[CheckReport]:
    """Check a single motion file for floating and joint limit violations."""
    if foot_names is None:
        foot_names = DEFAULT_FOOT_KEYS
    
    # Load motion data
    try:
        (
            motion_data,
            fps,
            root_pos,
            root_rot,
            dof_pos,
            local_body_pos,
            link_body_list,
        ) = load_robot_motion(motion_file)
    except Exception as e:
        print(f"[WARN] Failed to load {motion_file}: {e}")
        return None
    
    # Render through MuJoCo to get actual data (joint angles may be clipped, body positions from MuJoCo)
    try:
        (
            actual_dof_pos,
            actual_body_pos,
            mujoco_body_names,
            collisions_by_frame,
        ) = get_mujoco_rendered_data(root_pos, root_rot, dof_pos, robot_type)
        
        # For floating detection, use MuJoCo world body positions directly
        # calculate_foot_world_heights will detect if it's world positions and use them directly
        actual_body_pos_for_floating = actual_body_pos  # (T, M, 3) world positions from MuJoCo
    except Exception as e:
        print(f"[WARN] Failed to render through MuJoCo for {motion_file}: {e}")
        # Fallback to original data
        actual_dof_pos = dof_pos
        actual_body_pos_for_floating = local_body_pos  # Local positions
        mujoco_body_names = link_body_list
        use_world_positions = False
        collisions_by_frame = [[] for _ in range(len(dof_pos))]
    else:
        use_world_positions = True
    
    # Detect floating using MuJoCo rendered body positions (world frame from data.xpos)
    floating_info = detect_floating(
        root_pos,
        actual_body_pos_for_floating,  # MuJoCo world positions (data.xpos) or local positions (fallback)
        mujoco_body_names,
        fps,
        foot_names=foot_names,
        height_threshold=height_threshold,
        min_seconds=min_seconds,
        min_ratio=min_ratio,
        is_world_positions=use_world_positions,  # True if from MuJoCo, False if fallback
    )
    
    # Joint limit detection disabled per user request
    joint_limit_info = JointLimitInfo(
        has_limit_violation=False,
        total_frames=len(actual_dof_pos),
        num_violation_frames=0,
        violation_ratio=0.0,
        violated_joints=[],
        max_violation_per_joint={},
        violation_details="Joint limit detection disabled",
    )
    
    # Detect joint discontinuities using MuJoCo rendered joint angles
    joint_discontinuity_info = detect_joint_discontinuity(
        actual_dof_pos,
        fps,
        max_jump=max_joint_jump,
        min_jump_ratio=min_jump_ratio,
        severe_jump=severe_joint_jump,
    )
    
    # Detect self-collisions using collision data
    self_collision_info = detect_self_collisions(
        collisions_by_frame,
        fps,
        min_seconds=SELF_COLLISION_MIN_SECONDS,
        min_ratio=SELF_COLLISION_MIN_RATIO,
    )
    
    # Determine if motion is abnormal
    is_abnormal = (
        floating_info.is_floating
        or joint_discontinuity_info.has_discontinuity
        or self_collision_info.has_self_collision
    )
    
    # Use relative path for motion_file
    return CheckReport(
        motion_file=motion_file,
        is_abnormal=is_abnormal,
        floating=floating_info,
        joint_limits=joint_limit_info,
        joint_discontinuity=joint_discontinuity_info,
        self_collision=self_collision_info,
    )


def scan_folder(
    motion_folder: str,
    robot_type: str,
    height_threshold: float = OFF_GROUND_THRESHOLD,
    min_seconds: float = MIN_CONTINUOUS_SECONDS,
    min_ratio: float = MIN_CONTINUOUS_RATIO,
    foot_names: List[str] = None,
    joint_limit_tolerance: float = JOINT_LIMIT_TOLERANCE,
    min_joint_violation_ratio: float = MIN_JOINT_VIOLATION_RATIO,
    max_joint_jump: float = MAX_JOINT_JUMP,
    min_jump_ratio: float = MIN_JOINT_JUMP_RATIO,
) -> List[CheckReport]:
    """Scan folder for abnormal motions."""
    motion_folder = Path(motion_folder)
    if not motion_folder.exists():
        raise FileNotFoundError(f"Motion folder does not exist: {motion_folder}")
    
    reports = []
    motion_files = []
    
    # Collect all pkl files
    for root, _, files in os.walk(motion_folder):
        for file in files:
            if file.endswith(".pkl"):
                motion_files.append(Path(root) / file)
    
    print(f"Found {len(motion_files)} motion files, scanning...")
    
    for motion_file in motion_files:
        rel_path = str(motion_file.relative_to(motion_folder))
        report = check_motion(
            str(motion_file),
            robot_type,
            foot_names=foot_names,
            height_threshold=height_threshold,
            min_seconds=min_seconds,
            min_ratio=min_ratio,
            joint_limit_tolerance=joint_limit_tolerance,
            min_joint_violation_ratio=min_joint_violation_ratio,
            max_joint_jump=max_joint_jump,
            min_jump_ratio=min_jump_ratio,
        )
        if report:
            report.motion_file = rel_path
            reports.append(report)
    
    return reports


def main():
    parser = argparse.ArgumentParser(
        description="Auto check robot motions for floating and joint limit violations"
    )
    parser.add_argument(
        "--motion_folder",
        type=str,
        required=True,
        help="Folder containing robot *.pkl files",
    )
    parser.add_argument(
        "--robot_type",
        type=str,
        required=True,
        help=f"Robot type. Available: {list(ROBOT_XML_DICT.keys())}",
    )
    parser.add_argument(
        "--height_threshold",
        type=float,
        default=OFF_GROUND_THRESHOLD,
        help=f"Height above ground to consider off-ground (meters, default: {OFF_GROUND_THRESHOLD})",
    )
    parser.add_argument(
        "--min_seconds",
        type=float,
        default=MIN_CONTINUOUS_SECONDS,
        help=f"Minimum continuous seconds off-ground to flag (default: {MIN_CONTINUOUS_SECONDS})",
    )
    parser.add_argument(
        "--min_ratio",
        type=float,
        default=MIN_CONTINUOUS_RATIO,
        help=f"Minimum ratio of total frames off-ground to flag (default: {MIN_CONTINUOUS_RATIO})",
    )
    parser.add_argument(
        "--foot_names",
        type=str,
        nargs="*",
        default=None,
        help=f"Foot link names to check (default: {DEFAULT_FOOT_KEYS})",
    )
    parser.add_argument(
        "--output_json",
        type=str,
        default=None,
        help="Optional path to save check reports as JSON (default: auto_check_reports.json)",
    )
    parser.add_argument(
        "--motion_file",
        type=str,
        default=None,
        help="Check single motion file instead of folder",
    )
    parser.add_argument(
        "--joint_limit_tolerance",
        type=float,
        default=JOINT_LIMIT_TOLERANCE,
        help=f"Tolerance for joint limit violations in radians - only flag if violation exceeds this (default: {JOINT_LIMIT_TOLERANCE})",
    )
    parser.add_argument(
        "--min_joint_violation_ratio",
        type=float,
        default=MIN_JOINT_VIOLATION_RATIO,
        help=f"Minimum ratio of frames with joint violations to flag as abnormal (default: {MIN_JOINT_VIOLATION_RATIO})",
    )
    parser.add_argument(
        "--max_joint_jump",
        type=float,
        default=MAX_JOINT_JUMP,
        help=f"Maximum allowed joint angle change between consecutive frames in radians (default: {MAX_JOINT_JUMP})",
    )
    parser.add_argument(
        "--min_jump_ratio",
        type=float,
        default=MIN_JOINT_JUMP_RATIO,
        help=f"Minimum ratio of frames with joint jumps to flag as abnormal (default: {MIN_JOINT_JUMP_RATIO})",
    )
    
    args = parser.parse_args()
    
    foot_names = args.foot_names if args.foot_names else DEFAULT_FOOT_KEYS
    
    if args.motion_file:
        # Single file mode - only output if abnormal
        report = check_motion(
            args.motion_file,
            args.robot_type,
            foot_names=foot_names,
            height_threshold=args.height_threshold,
            min_seconds=args.min_seconds,
            min_ratio=args.min_ratio,
            joint_limit_tolerance=args.joint_limit_tolerance,
            min_joint_violation_ratio=args.min_joint_violation_ratio,
            max_joint_jump=args.max_joint_jump,
            min_jump_ratio=args.min_jump_ratio,
        )
        if report:
            if report.is_abnormal:
                print(f"\n[ABNORMAL] Motion: {report.motion_file}")
                if report.floating.is_floating:
                    print(f"  Floating: {report.floating.is_floating}")
                    print(f"    Violation: {report.floating.violation_reason}")
                if report.joint_limits.has_limit_violation:
                    print(f"  Joint limit violation: {report.joint_limits.has_limit_violation}")
                    print(f"    Violated joints: {report.joint_limits.violated_joints}")
                    print(f"    Details: {report.joint_limits.violation_details}")
                if report.joint_discontinuity.has_discontinuity:
                    print(f"  Joint discontinuity: {report.joint_discontinuity.has_discontinuity}")
                    print(f"    Max jump: {report.joint_discontinuity.max_jump_deg:.2f} deg at frame {report.joint_discontinuity.max_jump_frame} (joint {report.joint_discontinuity.max_jump_joint})")
                    print(f"    Details: {report.joint_discontinuity.discontinuity_details}")
            if report.self_collision.has_self_collision:
                print(f"  Self-collision: {report.self_collision.has_self_collision}")
                print(f"    Collision ratio: {report.self_collision.collision_ratio:.2%}")
                print(f"    Max continuous: {report.self_collision.max_continuous_collision_seconds:.2f}s "
                      f"({report.self_collision.max_continuous_collision_ratio:.2%})")
                if report.self_collision.top_collision_pairs:
                    print("    Top pairs:")
                    for pair in report.self_collision.top_collision_pairs:
                        print(f"      - {pair}")
                if report.self_collision.violation_reason:
                    print(f"    Reason: {report.self_collision.violation_reason}")
            else:
                # Normal motion, no output
                pass
        else:
            print(f"Failed to analyze {args.motion_file}")
    else:
        # Folder mode
        reports = scan_folder(
            args.motion_folder,
            args.robot_type,
            height_threshold=args.height_threshold,
            min_seconds=args.min_seconds,
            min_ratio=args.min_ratio,
            foot_names=foot_names,
            joint_limit_tolerance=args.joint_limit_tolerance,
            min_joint_violation_ratio=args.min_joint_violation_ratio,
        )
        
        abnormal_reports = [r for r in reports if r.is_abnormal]
        
        print(f"\n{'='*80}")
        print(f"Check Results")
        print(f"{'='*80}")
        print(f"Total motions scanned: {len(reports)}")
        print(f"Abnormal motions detected: {len(abnormal_reports)}")
        print(f"Percentage: {len(abnormal_reports)/len(reports)*100:.2f}%\n")
        
        # Count by issue type
        floating_count = sum(1 for r in abnormal_reports if r.floating.is_floating)
        joint_limit_count = sum(1 for r in abnormal_reports if r.joint_limits.has_limit_violation)
        discontinuity_count = sum(1 for r in abnormal_reports if r.joint_discontinuity.has_discontinuity)
        self_collision_count = sum(1 for r in abnormal_reports if r.self_collision.has_self_collision)
        
        print(f"Floating issues: {floating_count}")
        print(f"Joint limit violations: {joint_limit_count}")
        print(f"Joint discontinuities: {discontinuity_count}")
        print(f"Self-collisions: {self_collision_count}\n")
        
        if abnormal_reports:
            print("Abnormal Motions:")
            print("-" * 80)
            for report in sorted(
                abnormal_reports,
                key=lambda r: (
                    r.floating.is_floating,
                    r.joint_limits.has_limit_violation,
                    r.joint_discontinuity.has_discontinuity,
                    r.self_collision.has_self_collision,
                ),
                reverse=True,
            ):
                issues = []
                if report.floating.is_floating:
                    issues.append("floating")
                if report.joint_limits.has_limit_violation:
                    issues.append("joint_limit")
                if report.joint_discontinuity.has_discontinuity:
                    issues.append("discontinuity")
                if report.self_collision.has_self_collision:
                    issues.append("self_collision")
                print(f"{report.motion_file}: {', '.join(issues)}")
        else:
            print("No abnormal motions detected.")
        
        # Save abnormal reports to JSON
        output_json = args.output_json
        if output_json is None and abnormal_reports:
            output_json = "auto_check_reports.json"
        
        if output_json:
            output_path = Path(output_json)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Save only abnormal reports
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(
                    [asdict(r) for r in abnormal_reports],
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
            print(f"\nAbnormal reports ({len(abnormal_reports)} motions) saved to: {output_path}")


if __name__ == "__main__":
    main()

