# Retargeting Guide

All retargeting scripts are in `scripts/`. Each pipeline outputs a `.pkl` file containing robot motion data.

**Common flags:**
- `--rate_limit` — match playback speed to original human motion (remove for max speed)
- `--record_video` + `--video_path <path.mp4>` — save visualization as video
- `--robot <robot_key>` — see [Supported Robots](SUPPORTED_ROBOTS.md) for valid keys

---

## SMPL-X → Robot

*Sources: [AMASS](https://amass.is.tue.mpg.de/), [OMOMO](https://github.com/lijiaman/omomo_release)*

```bash
# Single motion
python scripts/smplx_to_robot.py \
  --smplx_file <path_to_smplx_data> \
  --robot <robot_key> \
  --save_path <output.pkl> \
  --rate_limit

# Batch (folder → folder, no visualization)
python scripts/smplx_to_robot_dataset.py \
  --src_folder <smplx_dir> \
  --tgt_folder <output_dir> \
  --robot <robot_key>
```

---

## BVH → Robot

*Sources: [LAFAN1](https://github.com/ubisoft/ubisoft-laforge-animation-dataset), [Nokov](https://www.nokov.com/)*

```bash
# Single motion
python scripts/bvh_to_robot.py \
  --bvh_file <path_to_bvh> \
  --robot <robot_key> \
  --save_path <output.pkl> \
  --rate_limit \
  --format <lafan1|nokov>

# Batch
python scripts/bvh_to_robot_dataset.py \
  --src_folder <bvh_dir> \
  --tgt_folder <output_dir> \
  --robot <robot_key>
```

---

## Xsens BVH → Robot

*Source: [Xsens](https://www.xsens.com/) MVN offline BVH export*

### Step 1: Calibrate with the visual tool

This launches a UI to adjust joint angle offsets. It generates an `offset.json` file that **must exist** before retargeting.

```bash
python general_motion_retargeting/utils/xsens_vendor/mujoco_xsens_bvh_view.py \
  --bvh_file <path_to_bvh> \
  --scale <displacement_scale> \
  --reset_to_zero
```

Click **"Apply and Preview"** when done — this saves `offset.json` and previews in MuJoCo.

### Step 2: Retarget

```bash
python scripts/xsens_bvh_to_robot.py \
  --bvh_file <path_to_bvh> \
  --robot <robot_key> \
  --save_path <output.pkl> \
  --scale <displacement_scale> \
  --bvh_format 3DSM \
  --reset_to_zero \
  --rate_limit
```

<details>
<summary><b>Xsens-specific flags</b></summary>

| Flag | Description |
|------|-------------|
| `--scale` | Displacement scaling (depends on dataset units vs meters) |
| `--start` / `--end` | Frame range to process |
| `--reset_to_zero` | Reset displacement and Z-rotation to zero (useful with `--start` to skip bad initial frames) |
| `--bvh_format` | Export format from Xsens MVN. **Recommended: `3DSM`** (3D Studio Max). Other formats are not yet fully supported. |

Output quaternions are in **wxyz** format.
</details>

---

## GVHMR → Robot

*Source: monocular video via [GVHMR](https://github.com/zju3dv/GVHMR)*

```bash
# 1. Extract human pose (in GVHMR repo)
cd path/to/GVHMR
python tools/demo/demo.py --video=docs/example_video/tennis.mp4 -s
# → outputs: GVHMR/outputs/demo/tennis/hmr4d_results.pt

# 2. Retarget (in GMR repo)
python scripts/gvhmr_to_robot.py \
  --gvhmr_pred_file <path_to_hmr4d_results.pt> \
  --robot unitree_g1 \
  --record_video
```

---

## FBX (OptiTrack) → Robot

*Source: [OptiTrack](https://www.optitrack.com/) offline FBX export*

Requires `fbx_sdk` — see [Installation](INSTALLATION.md).

```bash
# 1. Extract motion data (in fbx_sdk conda env)
cd third_party
python poselib/fbx_importer.py \
  --input <motion.fbx> \
  --output <motion_data.pkl> \
  --root-joint <root_joint_name> \
  --fps <fps>

# 2. Retarget (in gmr conda env)
conda activate gmr
python scripts/fbx_offline_to_robot.py \
  --motion_file <motion_data.pkl> \
  --robot <robot_key> \
  --save_path <output.pkl> \
  --rate_limit
```

---

## GMR PKL → CSV

Convert retargeted data to CSV for [BeyondMimic](https://github.com/):

```bash
python scripts/batch_gmr_pkl_to_csv.py
```

---

## Visualization

```bash
# Single motion
python scripts/vis_robot_motion.py --robot <robot_key> --robot_motion_path <output.pkl>

# Folder of motions
python scripts/vis_robot_motion_dataset.py --robot <robot_key> --robot_motion_folder <output_dir>
```

**Keyboard controls** (click the MuJoCo window first):
- `[` / `]` — previous / next motion
- `Space` — play / pause