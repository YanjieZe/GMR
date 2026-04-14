# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Installation and Setup

This is a Python package for motion retargeting to humanoid robots. Install in development mode:

```bash
conda create -n gmr python=3.10 -y
conda activate gmr
pip install -e .
conda install -c conda-forge libstdcxx-ng -y
```

## Code Architecture

### Core Components

- **`GeneralMotionRetargeting`** (`general_motion_retargeting/motion_retarget.py`): Main class for motion retargeting using inverse kinematics (IK) solver built on mink/mujoco
- **`KinematicsModel`** (`general_motion_retargeting/kinematics_model.py`): Handles robot kinematics calculations
- **`RobotMotionViewer`** (`general_motion_retargeting/robot_motion_viewer.py`): MuJoCo-based visualization for robot motions
- **Configuration System** (`general_motion_retargeting/params.py`): Simplified robot definitions and IK config mappings - cleaned to focus on core supported robots

### Data Flow

1. **Human Motion Input**: SMPL-X (AMASS/OMOMO) or BVH (LAFAN1) format
2. **Motion Format**: Each frame = dict of (human_body_name, 3D translation + rotation)
3. **Robot Output**: Tuple of (base_translation, base_rotation, joint_positions)
4. **IK Configs**: JSON files in `general_motion_retargeting/ik_configs/` define human-to-robot body mappings

### Supported Robots

Core robot models in `assets/` directory:
- Unitree G1 (`unitree_g1`) - 29 DOF humanoid
- Booster T1 (`booster_t1`) - Full-body humanoid 
- Booster K1 (`booster_k1`) - 22 DOF humanoid
- Stanford ToddlerBot (`stanford_toddy`) - Research humanoid
- Fourier N1 (`fourier_n1`) - Commercial humanoid
- ENGINEAI PM01 (`engineai_pm01`) - Industrial humanoid
- Kuavo S45 (`kuavo_s45`) - 28 DOF humanoid
- HighTorque Hi (`hightorque_hi`) - 25 DOF humanoid
- Galaxea R1 Pro (`galaxea_r1pro`) - 24 DOF wheeled humanoid

Additional models retained in ROBOT_BASE_DICT for compatibility:
- `unitree_g1_with_hands` (43 DOF with dexterous hands)
- `dex31_left_hand`, `dex31_right_hand` (hand components)

## Common Commands

### Single Motion Retargeting
```bash
# SMPL-X to robot
python scripts/smplx_to_robot.py --smplx_file "dataset/amass/AMASS_Complete/ACCAD/Female1Running_c3d/C7 -  run backwards_poses.npz" --robot unitree_g1 --save_path dataset/amass/robot_motion/female1running_unitree_g1.pkl

python scripts/smplx_to_robot_dataset.py --src_folder <path_to_dir_of_smplx_data> --tgt_folder <path_to_dir_to_save_robot_data> --robot <robot_name>

# BVH to robot  
python scripts/bvh_to_robot.py --bvh_file dataset/lafan1/BVH/fallAndGetUp1_subject1.bvh --robot unitree_g1 --save_path dataset/lafan1/robot_motion/fallAndGetUp1_subject1.pkl

python scripts/bvh_to_robot.py --bvh_file dataset/lafan1/BVH/fallAndGetUp1_subject1.bvh --robot booster_k1 --save_path dataset/lafan1/robot_motion/booster_k1/fallAndGetUp1_subject1.pkl

python scripts/bvh_to_robot.py --bvh_file dataset/lafan1/BVH/fallAndGetUp1_subject1.bvh --robot pnd_adam_lite --save_path dataset/lafan1/robot_motion/pnd_adam_lite/fallAndGetUp1_subject1.pkl

# BVHs to robot dataset 
python scripts/bvh_to_robot_dataset.py --src_folder dataset/lafan1/BVH --tgt_folder dataset/lafan1/robot_motion/unitree_g1 --robot unitree_g1

python scripts/bvh_to_robot_dataset.py --src_folder dataset/lafan1/BVH --tgt_folder dataset/lafan1/robot_motion/unitree_h1_2 --robot unitree_h1_2
python scripts/bvh_to_robot_dataset.py --src_folder dataset/lafan1/BVH --tgt_folder dataset/lafan1/robot_motion/booster_t1_29dof --robot booster_t1_29dof
python scripts/bvh_to_robot_dataset.py --src_folder dataset/lafan1/BVH --tgt_folder dataset/lafan1/robot_motion/stanford_toddy --robot stanford_toddy
python scripts/bvh_to_robot_dataset.py --src_folder dataset/lafan1/BVH --tgt_folder dataset/lafan1/robot_motion/fourier_n1 --robot fourier_n1
python scripts/bvh_to_robot_dataset.py --src_folder dataset/lafan1/BVH --tgt_folder dataset/lafan1/robot_motion/pal_talos --robot pal_talos

python scripts/bvh_to_robot_dataset.py --src_folder dataset/lafan1/BVH --tgt_folder dataset/lafan1/robot_motion/engineai_pm01 --robot engineai_pm01
python scripts/bvh_to_robot_dataset.py --src_folder dataset/lafan1/BVH --tgt_folder dataset/lafan1/robot_motion/berkeley_humanoid_lite --robot berkeley_humanoid_lite
python scripts/bvh_to_robot_dataset.py --src_folder dataset/lafan1/BVH --tgt_folder dataset/lafan1/robot_motion/unitree_h1 --robot unitree_h1
python scripts/bvh_to_robot_dataset.py --src_folder dataset/lafan1/BVH --tgt_folder dataset/lafan1/robot_motion/booster_t1 --robot booster_t1
python scripts/bvh_to_robot_dataset.py --src_folder dataset/lafan1/BVH --tgt_folder dataset/lafan1/robot_motion/hightorque_hi --robot hightorque_hi
python scripts/bvh_to_robot_dataset.py --src_folder dataset/lafan1/BVH --tgt_folder dataset/lafan1/robot_motion/booster_k1 --robot booster_k1
python scripts/bvh_to_robot_dataset.py --src_folder dataset/lafan1/BVH --tgt_folder dataset/lafan1/robot_motion/pnd_adam_lite --robot pnd_adam_lite
python scripts/bvh_to_robot_dataset.py --src_folder dataset/lafan1/BVH --tgt_folder dataset/lafan1/robot_motion/tienkung --robot tienkung
python scripts/bvh_to_robot_dataset.py --src_folder dataset/lafan1/BVH --tgt_folder dataset/lafan1/robot_motion/fourier_gr3 --robot fourier_gr3
```

### Batch Processing
```bash
# Process datasets
python scripts/smplx_to_robot_dataset.py
python scripts/bvh_to_robot_dataset.py
```

### Visualization
```bash
# Visualize saved robot motion
python scripts/vis_robot_motion.py --robot unitree_g1 --robot_motion_path dataset/lafan1/robot_motion/dance1_subject3.pkl

python scripts/vis_robot_motion.py --robot fourier_gr3 --robot_motion_path dataset/lafan1/robot_motion/fourier_gr3/jumps1_subject2.pkl
```

Add `--record_video --video_path <output.mp4>` to any visualization command to record video.

## Key Technical Details

- **IK Solver**: Uses mink library with configurable solver (default: "daqp") and damping (default: 5e-1)
- **Human Height Scaling**: Automatic scaling based on `actual_human_height` parameter vs config assumptions
- **Real-time Performance**: Optimized for 60-70 FPS on high-end CPUs for teleoperation use cases
- **Body Model Dependencies**: Requires SMPL-X body models in `assets/body_models/smplx/`

## File Organization

- `scripts/`: Entry point scripts for different retargeting workflows
- `general_motion_retargeting/`: Core library code
- `assets/`: Robot models (MuJoCo XML) and body models (SMPL-X)
- `general_motion_retargeting/ik_configs/`: JSON configuration files for human-to-robot body mappings:
  - SMPL-X configs: `smplx_to_{g1,t1,k1,toddy,n1,pm01,kuavo,hi,r1pro}.json`
  - BVH configs: `bvh_to_{g1,t1,toddy,n1,pm01}.json`
  - FBX configs: `fbx_to_g1.json`

## Project Status & Features

**Current State**: Production-ready motion retargeting system with extensive robot support

**Key Capabilities**:
- **Multi-format Input**: SMPL-X (AMASS/OMOMO), BVH (LAFAN1), FBX (OptiTrack)
- **Real-time Performance**: 60-70 FPS on high-end hardware for teleoperation
- **9 Robot Models**: From research platforms to commercial humanoids
- **Robust IK**: Mink-based solver with automatic human height scaling
- **Visualization**: MuJoCo-based viewer with video recording capabilities
- **Batch Processing**: Dataset-level retargeting workflows

**Use Cases**:
- Real-time whole-body teleoperation (see [TWIST](https://github.com/YanjieZe/TWIST))
- RL policy training data generation
- Motion capture to robot deployment
- Cross-platform humanoid motion transfer

**Recent Additions** (2025):
- Booster K1 support (9th robot)
- Dexterous hand integration (G1 + Dex31)
- Wheeled humanoid support (Galaxea R1 Pro)
- Enhanced OptiTrack real-time streaming