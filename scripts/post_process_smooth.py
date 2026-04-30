#!/usr/bin/env python3
"""
后处理平滑脚本：对重定向后的机器人动作数据进行时间平滑，减少动作不连续和抖动。

支持：
1. 关节角度平滑（dof_pos）
2. 根位置平滑（root_pos）
3. 根旋转平滑（root_rot）
4. 极端跳跃检测和修正
"""

import argparse
import pickle
import numpy as np
from pathlib import Path
from scipy.signal import savgol_filter
from scipy.interpolate import interp1d
from typing import Tuple, Optional

def detect_extreme_jumps(dof_pos: np.ndarray, threshold: float = 2.0) -> np.ndarray:
    """
    检测极端跳跃（>threshold rad）。
    
    Args:
        dof_pos: (T, N) 关节角度数组
        threshold: 跳跃阈值（弧度）
    
    Returns:
        jump_mask: (T-1,) bool数组，True表示该帧有极端跳跃
    """
    dof_vel = np.diff(dof_pos, axis=0)
    max_jump_per_frame = np.max(np.abs(dof_vel), axis=1)
    jump_mask = max_jump_per_frame > threshold
    return jump_mask


def detect_joint_jitter(dof_pos: np.ndarray, joint_idx: int, frame_range: Optional[slice] = None) -> dict:
    """
    检测单个关节的抖动程度。
    
    Args:
        dof_pos: (T, N) 关节角度数组
        joint_idx: 关节索引
        frame_range: 可选的帧范围切片，用于检测特定帧范围的抖动
    
    Returns:
        dict with 'has_jitter', 'oscillation_ratio', 'velocity_std', 'mean_velocity', 'jitter_level'
    """
    dof_vel = np.diff(dof_pos, axis=0)
    joint_vel = np.abs(dof_vel[:, joint_idx])
    
    if frame_range is not None:
        joint_vel = joint_vel[frame_range]
    
    if len(joint_vel) < 3:
        return {'has_jitter': False, 'oscillation_ratio': 0.0, 'velocity_std': 0.0, 'mean_velocity': 0.0, 'jitter_level': 'None'}
    
    # Calculate oscillation (acceleration sign changes)
    joint_acc = np.diff(joint_vel)
    sign_changes = np.sum(np.diff(np.sign(joint_acc)) != 0)
    oscillation_ratio = sign_changes / len(joint_acc) if len(joint_acc) > 0 else 0
    
    mean_vel = np.mean(joint_vel)
    std_vel = np.std(joint_vel)
    max_vel = np.max(joint_vel)
    
    # More sensitive jitter detection
    # Jitter criteria: 
    # 1. High oscillation (>0.4, lowered from 0.5)
    # 2. High relative variability (std > 1.2 * mean, lowered from 1.5)
    # 3. High absolute velocity with variability
    has_jitter = False
    jitter_level = 'None'
    
    if oscillation_ratio > 0.7:
        has_jitter = True
        jitter_level = 'Severe'
    elif oscillation_ratio > 0.5:
        has_jitter = True
        jitter_level = 'High'
    elif oscillation_ratio > 0.4:
        has_jitter = True
        jitter_level = 'Medium'
    elif std_vel > mean_vel * 1.2 and mean_vel > 0.005:
        has_jitter = True
        jitter_level = 'Medium'
    elif std_vel > mean_vel * 1.5 and mean_vel > 0.01:
        has_jitter = True
        jitter_level = 'Low'
    
    return {
        'has_jitter': has_jitter,
        'oscillation_ratio': oscillation_ratio,
        'velocity_std': std_vel,
        'mean_velocity': mean_vel,
        'max_velocity': max_vel,
        'jitter_level': jitter_level
    }


def smooth_dof_pos(dof_pos: np.ndarray, 
                   window_length: int = 5,
                   polyorder: int = 2,
                   fix_extreme_jumps: bool = True,
                   jump_threshold: float = 2.0,
                   aggressive_smoothing: bool = True,
                   per_joint_smoothing: bool = True) -> Tuple[np.ndarray, dict]:
    """
    对关节角度进行时间平滑，消除抖动噪音。
    
    Args:
        dof_pos: (T, N) 关节角度数组
        window_length: Savitzky-Golay滤波器窗口长度（必须是奇数）
        polyorder: 多项式阶数
        fix_extreme_jumps: 是否修正极端跳跃
        jump_threshold: 极端跳跃阈值（弧度）
        aggressive_smoothing: 是否使用更强的平滑（针对抖动）
    
    Returns:
        smoothed_dof_pos: 平滑后的关节角度
        info: 处理信息字典
    """
    T, N = dof_pos.shape
    
    info = {
        'original_max_jump': 0.0,
        'extreme_jumps_detected': 0,
        'extreme_jumps_fixed': 0,
        'jitter_detected': False
    }
    
    # 检测抖动（高频小幅度振荡）
    dof_vel = np.diff(dof_pos, axis=0)
    joint_velocities = np.abs(dof_vel)
    
    # 计算每个关节的振荡率（加速度符号变化率）
    has_jitter = False
    for joint_idx in range(N):
        joint_vel = joint_velocities[:, joint_idx]
        if len(joint_vel) > 2:
            joint_acc = np.diff(joint_vel)
            sign_changes = np.sum(np.diff(np.sign(joint_acc)) != 0)
            oscillation_ratio = sign_changes / len(joint_acc) if len(joint_acc) > 0 else 0
            # 如果振荡率 > 0.5 且平均速度较小，说明有抖动
            if oscillation_ratio > 0.5 and np.mean(joint_vel) < 0.1:
                has_jitter = True
                break
    
    info['jitter_detected'] = has_jitter
    
    # 如果检测到抖动，使用更强的平滑
    if aggressive_smoothing and has_jitter:
        # 增加窗口长度以更好地消除抖动
        effective_window = min(window_length * 2 + 1, T if T % 2 == 1 else T - 1)
        if effective_window < 5:
            effective_window = 5
        if effective_window % 2 == 0:
            effective_window += 1
    else:
        effective_window = window_length
        if effective_window % 2 == 0:
            effective_window += 1
        if effective_window >= T:
            effective_window = T if T % 2 == 1 else T - 1
        if effective_window < 3:
            effective_window = 3
    
    # 检测极端跳跃
    if fix_extreme_jumps:
        jump_mask = detect_extreme_jumps(dof_pos, jump_threshold)
        info['extreme_jumps_detected'] = np.sum(jump_mask)
        
        if info['extreme_jumps_detected'] > 0:
            max_jump_per_frame = np.max(joint_velocities, axis=1)
            info['original_max_jump'] = float(np.max(max_jump_per_frame))
            
            # 对极端跳跃进行插值修正
            smoothed_dof_pos = dof_pos.copy()
            jump_indices = np.where(jump_mask)[0]
            
            for idx in jump_indices:
                # 在跳跃帧前后进行插值
                start_idx = max(0, idx - 2)
                end_idx = min(T - 1, idx + 3)
                
                if end_idx - start_idx > 1:
                    # 使用线性插值修正跳跃帧
                    for joint_idx in range(N):
                        if abs(dof_pos[idx + 1, joint_idx] - dof_pos[idx, joint_idx]) > jump_threshold:
                            # 创建插值函数（跳过跳跃帧）
                            valid_indices = np.concatenate([
                                np.arange(start_idx, idx),
                                np.arange(idx + 2, end_idx)
                            ])
                            if len(valid_indices) >= 2:
                                interp_func = interp1d(
                                    valid_indices,
                                    smoothed_dof_pos[valid_indices, joint_idx],
                                    kind='linear',
                                    fill_value='extrapolate'
                                )
                                smoothed_dof_pos[idx:idx+2, joint_idx] = interp_func([idx, idx+1])
                                info['extreme_jumps_fixed'] += 1
            
            dof_pos = smoothed_dof_pos
    
    # 使用Savitzky-Golay滤波器进行平滑
    smoothed_dof_pos = dof_pos.copy()
    
    # 对每个关节单独检测抖动并应用不同强度的滤波
    if per_joint_smoothing:
        jitter_info = {}
        jittered_joints_list = []
        
        for joint_idx in range(N):
            # 首先检测全帧范围的抖动
            jitter_info[joint_idx] = detect_joint_jitter(dof_pos, joint_idx)
            
            # 如果全帧检测没有抖动，检查特定帧范围（如24-62）
            if not jitter_info[joint_idx]['has_jitter'] and T > 30:
                # 检查24-62范围（如果存在）
                if T > 62:
                    frame_range = slice(24, 62)
                    jitter_info_range = detect_joint_jitter(dof_pos, joint_idx, frame_range)
                    if jitter_info_range['has_jitter']:
                        jitter_info[joint_idx] = jitter_info_range
                        jitter_info[joint_idx]['frame_range'] = (24, 62)
                # 也检查后半段
                elif T > 40:
                    frame_range = slice(max(0, T//2 - 10), T-1)
                    jitter_info_range = detect_joint_jitter(dof_pos, joint_idx, frame_range)
                    if jitter_info_range['has_jitter']:
                        jitter_info[joint_idx] = jitter_info_range
                        jitter_info[joint_idx]['frame_range'] = (frame_range.start, frame_range.stop)
            
            # 根据抖动程度选择滤波强度
            if jitter_info[joint_idx]['has_jitter']:
                jittered_joints_list.append(joint_idx)
                # 严重抖动：使用更大的窗口
                if jitter_info[joint_idx]['oscillation_ratio'] > 0.7:
                    joint_window = min(15, T if T % 2 == 1 else T - 1)
                    joint_poly = 3
                elif jitter_info[joint_idx]['oscillation_ratio'] > 0.5:
                    joint_window = min(11, T if T % 2 == 1 else T - 1)
                    joint_poly = 3
                else:
                    joint_window = min(9, T if T % 2 == 1 else T - 1)
                    joint_poly = 2
                
                if joint_window % 2 == 0:
                    joint_window += 1
                if joint_window < 5:
                    joint_window = 5
                
                try:
                    # 对该关节单独平滑
                    joint_data = smoothed_dof_pos[:, joint_idx:joint_idx+1]
                    joint_smoothed = savgol_filter(
                        joint_data,
                        window_length=joint_window,
                        polyorder=joint_poly,
                        axis=0,
                        mode='nearest'
                    )
                    smoothed_dof_pos[:, joint_idx] = joint_smoothed[:, 0]
                    
                    # 如果抖动严重，进行第二次平滑
                    if jitter_info[joint_idx]['oscillation_ratio'] > 0.7:
                        second_window = max(7, joint_window - 4)
                        if second_window % 2 == 0:
                            second_window += 1
                        if second_window < T:
                            joint_smoothed = savgol_filter(
                                joint_smoothed,
                                window_length=second_window,
                                polyorder=2,
                                axis=0,
                                mode='nearest'
                            )
                            smoothed_dof_pos[:, joint_idx] = joint_smoothed[:, 0]
                    
                    info['jitter_detected'] = True
                except Exception as e:
                    # 如果失败，使用默认平滑
                    pass
        
        # 统计抖动关节数量
        jittered_joints = sum(1 for j in jitter_info.values() if j['has_jitter'])
        info['jittered_joints'] = jittered_joints
        info['jitter_info'] = {k: v for k, v in jitter_info.items() if v['has_jitter']}
        
        # 对没有抖动的关节使用默认平滑
        try:
            # 整体平滑（只对非抖动关节有效，因为抖动关节已经单独处理）
            # 为了保持一致性，对所有关节再应用一次轻量平滑
            if not has_jitter:  # 如果没有整体抖动，使用默认窗口
                smoothed_dof_pos = savgol_filter(
                    smoothed_dof_pos,
                    window_length=effective_window,
                    polyorder=polyorder,
                    axis=0,
                    mode='nearest'
                )
        except Exception:
            pass
    else:
        # 原来的整体平滑方法
        try:
            smoothed_dof_pos = savgol_filter(
                smoothed_dof_pos,
                window_length=effective_window,
                polyorder=polyorder,
                axis=0,
                mode='nearest'
            )
            
            if aggressive_smoothing and has_jitter:
                if effective_window >= 11:
                    second_window = max(7, effective_window - 4)
                else:
                    second_window = max(5, effective_window - 2)
                if second_window % 2 == 0:
                    second_window += 1
                if second_window < T:
                    smoothed_dof_pos = savgol_filter(
                        smoothed_dof_pos,
                        window_length=second_window,
                        polyorder=max(2, polyorder - 1),
                        axis=0,
                        mode='nearest'
                    )
        except Exception as e:
            print(f"Warning: Savitzky-Golay filter failed: {e}, using original data")
            smoothed_dof_pos = dof_pos
    
    return smoothed_dof_pos, info


def smooth_root_pos_func(root_pos: np.ndarray,
                         window_length: int = 5,
                         polyorder: int = 2) -> np.ndarray:
    """对根位置进行时间平滑。"""
    T = root_pos.shape[0]
    
    if window_length % 2 == 0:
        window_length += 1
    if window_length >= T:
        window_length = T if T % 2 == 1 else T - 1
    if window_length < 3:
        window_length = 3
    
    try:
        smoothed_root_pos = savgol_filter(
            root_pos,
            window_length=window_length,
            polyorder=polyorder,
            axis=0,
            mode='nearest'
        )
    except Exception as e:
        print(f"Warning: Root position smoothing failed: {e}, using original data")
        smoothed_root_pos = root_pos
    
    return smoothed_root_pos


def smooth_root_rot_func(root_rot: np.ndarray,
                         window_length: int = 5,
                         polyorder: int = 2) -> np.ndarray:
    """
    对根旋转（四元数）进行时间平滑。
    注意：四元数不能直接平滑，需要先转换为旋转矩阵或欧拉角。
    这里使用简化的方法：对四元数的前三个分量进行平滑，然后归一化。
    """
    T = root_rot.shape[0]
    
    if window_length % 2 == 0:
        window_length += 1
    if window_length >= T:
        window_length = T if T % 2 == 1 else T - 1
    if window_length < 3:
        window_length = 3
    
    # 四元数归一化
    norm = np.linalg.norm(root_rot, axis=1, keepdims=True)
    root_rot_normalized = root_rot / (norm + 1e-8)
    
    try:
        # 对四元数进行平滑（简单方法：直接平滑后归一化）
        smoothed_root_rot = savgol_filter(
            root_rot_normalized,
            window_length=window_length,
            polyorder=polyorder,
            axis=0,
            mode='nearest'
        )
        # 归一化四元数
        norm = np.linalg.norm(smoothed_root_rot, axis=1, keepdims=True)
        smoothed_root_rot = smoothed_root_rot / (norm + 1e-8)
    except Exception as e:
        print(f"Warning: Root rotation smoothing failed: {e}, using original data")
        smoothed_root_rot = root_rot_normalized
    
    return smoothed_root_rot


def smooth_motion_file(pkl_path: Path,
                       output_path: Optional[Path] = None,
                       smooth_dof: bool = True,
                       smooth_root_pos: bool = True,
                       smooth_root_rot: bool = False,
                       window_length: int = 5,
                       polyorder: int = 2,
                       fix_extreme_jumps: bool = True,
                       jump_threshold: float = 2.0,
                       aggressive_smoothing: bool = True,
                       per_joint_smoothing: bool = True,
                       backup: bool = True) -> dict:
    """
    平滑单个pkl文件。
    
    Args:
        pkl_path: 输入pkl文件路径
        output_path: 输出路径（如果None，覆盖原文件）
        smooth_dof: 是否平滑关节角度
        smooth_root_pos: 是否平滑根位置
        smooth_root_rot: 是否平滑根旋转
        window_length: 平滑窗口长度
        polyorder: 多项式阶数
        fix_extreme_jumps: 是否修正极端跳跃
        jump_threshold: 极端跳跃阈值
        backup: 是否备份原文件
    
    Returns:
        info: 处理信息字典
    """
    pkl_path = Path(pkl_path)
    if not pkl_path.exists():
        raise FileNotFoundError(f"File not found: {pkl_path}")
    
    # 加载数据
    with open(pkl_path, 'rb') as f:
        motion_data = pickle.load(f)
    
    info = {
        'file': str(pkl_path),
        'frames': len(motion_data['dof_pos']),
        'dof_smooth': {},
        'root_pos_smooth': False,
        'root_rot_smooth': False
    }
    
    # 备份原文件
    if backup and output_path is None:
        backup_path = pkl_path.with_suffix('.pkl.bak')
        with open(backup_path, 'wb') as f:
            pickle.dump(motion_data, f)
        info['backup'] = str(backup_path)
    
    # 平滑关节角度
    if smooth_dof:
        smoothed_dof_pos, dof_info = smooth_dof_pos(
            motion_data['dof_pos'],
            window_length=window_length,
            polyorder=polyorder,
            fix_extreme_jumps=fix_extreme_jumps,
            jump_threshold=jump_threshold,
            aggressive_smoothing=aggressive_smoothing,
            per_joint_smoothing=per_joint_smoothing
        )
        motion_data['dof_pos'] = smoothed_dof_pos
        info['dof_smooth'] = dof_info
    
    # 平滑根位置
    if smooth_root_pos:
        # 调用函数（避免与参数名冲突）
        motion_data['root_pos'] = smooth_root_pos_func(
            motion_data['root_pos'],
            window_length=window_length,
            polyorder=polyorder
        )
        info['root_pos_smooth'] = True
    
    # 平滑根旋转
    if smooth_root_rot:
        # 调用函数（避免与参数名冲突）
        motion_data['root_rot'] = smooth_root_rot_func(
            motion_data['root_rot'],
            window_length=window_length,
            polyorder=polyorder
        )
        info['root_rot_smooth'] = True
    
    # 保存
    output_path = Path(output_path) if output_path else pkl_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'wb') as f:
        pickle.dump(motion_data, f)
    
    info['output'] = str(output_path)
    return info


def main():
    parser = argparse.ArgumentParser(description="Smooth robot motion data")
    parser.add_argument("--input", type=str, required=True,
                       help="Input pkl file or directory")
    parser.add_argument("--output", type=str, default=None,
                       help="Output path (default: overwrite input)")
    parser.add_argument("--smooth_dof", action="store_true", default=True,
                       help="Smooth joint angles (default: True)")
    parser.add_argument("--smooth_root_pos", action="store_true", default=True,
                       help="Smooth root position (default: True)")
    parser.add_argument("--smooth_root_rot", action="store_false", default=False,
                       help="Smooth root rotation (default: False)")
    parser.add_argument("--window_length", type=int, default=5,
                       help="Smoothing window length (default: 5, use larger values like 9-15 for heavy jitter)")
    parser.add_argument("--polyorder", type=int, default=2,
                       help="Polynomial order (default: 2, use 3 for smoother results)")
    parser.add_argument("--fix_jumps", action="store_true", default=True,
                       help="Fix extreme jumps (default: True)")
    parser.add_argument("--jump_threshold", type=float, default=2.0,
                       help="Extreme jump threshold in radians (default: 2.0)")
    parser.add_argument("--aggressive", action="store_true", default=True,
                       help="Use aggressive smoothing to remove jitter (default: True)")
    parser.add_argument("--per_joint", action="store_true", default=True,
                       help="Detect and smooth each joint individually (default: True)")
    parser.add_argument("--no_backup", action="store_true",
                       help="Don't backup original files")
    parser.add_argument("--recursive", action="store_true",
                       help="Process directories recursively")
    
    args = parser.parse_args()
    
    input_path = Path(args.input)
    
    # 处理单个文件
    if input_path.is_file():
        if not input_path.suffix == '.pkl':
            print(f"Error: Input must be a .pkl file: {input_path}")
            return
        
        try:
            info = smooth_motion_file(
                input_path,
                output_path=args.output,
                smooth_dof=args.smooth_dof,
                smooth_root_pos=args.smooth_root_pos,
                smooth_root_rot=args.smooth_root_rot,
                window_length=args.window_length,
                polyorder=args.polyorder,
                    fix_extreme_jumps=args.fix_jumps,
                    jump_threshold=args.jump_threshold,
                    aggressive_smoothing=args.aggressive,
                    backup=not args.no_backup
            )
            print(f"✓ Processed: {info['file']}")
            if 'extreme_jumps_detected' in info['dof_smooth']:
                print(f"  Extreme jumps: {info['dof_smooth']['extreme_jumps_detected']} detected, "
                      f"{info['dof_smooth']['extreme_jumps_fixed']} fixed")
        except Exception as e:
            print(f"✗ Error processing {input_path}: {e}")
    
    # 处理目录
    elif input_path.is_dir():
        pkl_files = list(input_path.rglob('*.pkl')) if args.recursive else list(input_path.glob('*.pkl'))
        
        if not pkl_files:
            print(f"No .pkl files found in {input_path}")
            return
        
        print(f"Found {len(pkl_files)} pkl files")
        
        success = 0
        failed = 0
        
        for pkl_file in pkl_files:
            try:
                output_file = None
                if args.output:
                    # 保持相对路径结构
                    rel_path = pkl_file.relative_to(input_path)
                    output_file = Path(args.output) / rel_path
                
                info = smooth_motion_file(
                    pkl_file,
                    output_path=output_file,
                    smooth_dof=args.smooth_dof,
                    smooth_root_pos=args.smooth_root_pos,
                    smooth_root_rot=args.smooth_root_rot,
                    window_length=args.window_length,
                    polyorder=args.polyorder,
                    fix_extreme_jumps=args.fix_jumps,
                    jump_threshold=args.jump_threshold,
                    aggressive_smoothing=args.aggressive,
                    backup=not args.no_backup
                )
                success += 1
                
                if 'extreme_jumps_detected' in info['dof_smooth'] and info['dof_smooth']['extreme_jumps_detected'] > 0:
                    print(f"  {pkl_file.name}: {info['dof_smooth']['extreme_jumps_detected']} jumps fixed")
                
            except Exception as e:
                print(f"✗ Error processing {pkl_file}: {e}")
                failed += 1
        
        print(f"\n✓ Success: {success}, ✗ Failed: {failed}")
    
    else:
        print(f"Error: Input path does not exist: {input_path}")


if __name__ == "__main__":
    main()

