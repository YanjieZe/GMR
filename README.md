# GMR: General Motion Retargeting

[![arXiv](https://img.shields.io/badge/paper-arXiv%3A2505.02833-b31b1b.svg)](https://arxiv.org/abs/2505.02833)
[![arXiv](https://img.shields.io/badge/paper-arXiv%3A2510.02252-b31b1b.svg)](https://arxiv.org/abs/2510.02252)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Version](https://img.shields.io/badge/version-0.2.0-blue.svg)](https://github.com/YanjieZe/GMR/releases)
[![Twitter](https://img.shields.io/badge/twitter-ZeYanjie-blue.svg)](https://x.com/ZeYanjie/status/1952446745696469334)
[![Blog](https://img.shields.io/badge/blog-GMR-blue.svg)](https://yanjieze.github.io/humanoid-foundation/#GMR)
[![Tutorial](https://img.shields.io/badge/tutorial-BILIBILI-blue.svg)](https://www.bilibili.com/video/BV1p1nazeEzC/?share_source=copy_web&vd_source=c76e3ab14ac3f7219a9006b96b4b0f76)

![Banner for GMR](./assets/GMR.png)

**Real-time, high-quality motion retargeting from human to humanoid robots.** Retarget motions from SMPL-X, BVH, FBX, or live VR streams to **17+ humanoid robots** with a single config change.

![GMR Pipeline](./assets/GMR_pipeline.png)

## Key Features

- **Real-time retargeting** — powers whole-body teleoperation via [TWIST](https://github.com/YanjieZe/TWIST) / [TWIST2](https://yanjieze.com/TWIST2)
- **17+ robots supported** — Unitree G1/H1, Booster T1/K1, Fourier GR3, PAL Talos, and [more →](docs/SUPPORTED_ROBOTS.md)
- **Multiple input formats** — SMPL-X (AMASS, OMOMO), BVH (LAFAN1, Nokov, Xsens), FBX (OptiTrack), PICO VR streaming
- **RL-ready** — carefully tuned for downstream RL motion tracking policies

> ![NOTE]
> **Want support for a new robot or data format?** Send robot files (`.xml`, `.urdf`, meshes) or motion data to [Yanjie Ze](mailto:lastyanjieze@gmail.com) or [open an issue](https://github.com/YanjieZe/GMR/issues). Please ensure files can be open-sourced.

## Quick Start

```bash
# 1. Create environment
conda create -n gmr python=3.10 -y && conda activate gmr

# 2. Install GMR
pip install -e .

# 3. Fix potential rendering issues
conda install -c conda-forge libstdcxx-ng -y
```

> ![NOTE]
> After installing SMPL-X, change `ext` in `smplx/body_models.py` from `npz` to `pkl` if you are using SMPL-X pkl files.

Then retarget your first motion:

```bash
# SMPL-X → Robot
python scripts/smplx_to_robot.py --smplx_file <path> --robot unitree_g1 --save_path output.pkl --rate_limit

# BVH → Robot
python scripts/bvh_to_robot.py --bvh_file <path> --robot unitree_g1 --save_path output.pkl --rate_limit --format lafan1

# Visualize result
python scripts/vis_robot_motion.py --robot unitree_g1 --robot_motion_path output.pkl
```

## Documentation

| Doc | Description |
|-----|-------------|
| [**Supported Robots & Formats**](docs/SUPPORTED_ROBOTS.md) | Full compatibility table (17+ robots, 6+ formats) |
| [**Installation**](docs/INSTALLATION.md) | Detailed setup, dependencies, and troubleshooting |
| [**Data Preparation**](docs/DATA_PREPARATION.md) | Downloading SMPL-X models, AMASS, OMOMO, LAFAN1 data |
| [**Retargeting Guide**](docs/RETARGETING.md) | All retargeting pipelines: SMPL-X, BVH, FBX, GVHMR, Xsens |
| [**Live Streaming**](docs/STREAMING.md) | Real-time retargeting via OptiTrack and PICO (TWIST2) |
| [**IK Configuration**](docs/IK_CONFIG.md) | Inverse kinematics config reference |
| [**Known Issues**](docs/TEST_MOTIONS.md) | Collection of motions with known retargeting issues |

## Motion Data Format

<details>
<summary><b>Human motion data</b></summary>

Each frame is a dict of `(human_body_name, 3D global translation + global rotation)`. Rotations are quaternions in **wxyz** order (aligned with MuJoCo).
</details>

<details>
<summary><b>Robot motion data</b></summary>

Each frame is a tuple of `(robot_base_translation, robot_base_rotation, robot_joint_positions)`.
</details>

## Demos

<details>
<summary><b>Click to expand demo videos</b></summary>

<table>
  <tr>
    <td align="center" width="20%">
      <b>LAFAN1 → 5 robots</b><br>
      <video src="https://github.com/user-attachments/assets/23566fa5-6335-46b9-957b-4b26aed11b9e" width="200" controls></video>
    </td>
    <td align="center" width="20%">
      <b>Galaxea R1 Pro</b><br>
      <video src="https://github.com/user-attachments/assets/903ed0b0-0ac5-4226-8f82-5a88631e9b7c" width="200" controls></video>
    </td>
    <td align="center" width="20%">
      <b>Switch robots in 1 arg</b><br>
      <video src="https://github.com/user-attachments/assets/03f10902-c541-40b1-8104-715a5759fd5e" width="200" controls></video>
    </td>
    <td align="center" width="20%">
      <b>HighTorque twist dance</b><br>
      <video src="https://github.com/user-attachments/assets/1d3e663b-f29e-41b1-8e15-5c0deb6a4a5c" width="200" controls></video>
    </td>
  </tr>
  <tr>
    <td align="center">
      <b>Kuavo picking up box</b><br>
      <video src="https://github.com/user-attachments/assets/02fc8f41-c363-484b-a329-4f4e83ed5b80" width="200" controls></video>
    </td>
    <td align="center">
      <b>Unitree H1 ChaCha</b><br>
      <video src="https://github.com/user-attachments/assets/28ee6f0f-be30-42bb-8543-cf1152d97724" width="200" controls></video>
    </td>
    <td align="center">
      <b>Booster T1 jumping</b><br>
      <video src="https://github.com/user-attachments/assets/2c75a146-e28f-4327-930f-5281bfc2ca9c" width="200" controls></video>
    </td>
    <td align="center">
      <b>Unitree H1-2 jumping</b><br>
      <video src="https://github.com/user-attachments/assets/2382d8ce-7902-432f-ab45-348a11eeb312" width="200" controls></video>
    </td>
  </tr>
  <tr>
    <td align="center">
      <b>PND Adam Lite</b><br>
      <video src="https://github.com/user-attachments/assets/a8ef1409-88f1-4393-9cd0-d2b14216d2a4" width="200" controls></video>
    </td>
    <td align="center">
      <b>Tienkung walking</b><br>
      <video src="https://github.com/user-attachments/assets/7a775ecc-4254-450c-a3eb-49e843b8e331" width="200" controls></video>
    </td>
    <td align="center">
      <b>GVHMR + GMR</b><br>
      <a href="https://www.bilibili.com/video/BV1Tnpmz9EaE">▶ Watch on Bilibili</a>
    </td>
    <td align="center">
      <b>PAL Talos fighting</b><br>
      <video src="https://github.com/user-attachments/assets/3ec0bf80-80c1-4181-a623-dc2b072c2ca2" width="200" controls></video>
    </td>
  </tr>
</table>

</details>

## Speed Benchmark

| CPU | Retargeting Speed |
|-----|-------------------|
| AMD Ryzen Threadripper 7960X 24-Cores | 60–70 FPS |
| 13th Gen Intel Core i9-13900K 24-Cores | 35–45 FPS |

## Community

Join our WeChat group for discussions: add [Yanjie Ze](https://yanjieze.com/TWIST2/images/my_wechat.jpg) with info like `[GMR] [Your Name] [Your Affiliation]`.

[MimicKit](https://github.com/xbpeng/MimicKit/tree/main/tools/gmr_to_mimickit) from Jason Peng now supports GMR format.

## Citation

<details>
<summary><b>BibTeX</b></summary>

```bibtex
@article{joao2025gmr,
  title   = {Retargeting Matters: General Motion Retargeting for Humanoid Motion Tracking},
  author  = {Joao Pedro Araujo and Yanjie Ze and Pei Xu and Jiajun Wu and C. Karen Liu},
  year    = {2025},
  journal = {arXiv preprint arXiv:2510.02252}
}

@article{ze2025twist,
  title   = {TWIST: Teleoperated Whole-Body Imitation System},
  author  = {Yanjie Ze and Zixuan Chen and João Pedro Araújo and Zi-ang Cao and Xue Bin Peng and Jiajun Wu and C. Karen Liu},
  year    = {2025},
  journal = {arXiv preprint arXiv:2505.02833}
}

@software{ze2025gmr,
  title = {GMR: General Motion Retargeting},
  author = {Yanjie Ze and João Pedro Araújo and Jiajun Wu and C. Karen Liu},
  year  = {2025},
  url   = {https://github.com/YanjieZe/GMR},
  note  = {GitHub repository}
}
```

</details>

## Acknowledgement

<details>
<summary><b>Dependencies and robot model sources</b></summary>

IK solver built on [mink](https://github.com/kevinzakka/mink) and [MuJoCo](https://github.com/google-deepmind/mujoco). Human motion data from [AMASS](https://amass.is.tue.mpg.de/), [OMOMO](https://github.com/lijiaman/omomo_release), and [LAFAN1](https://github.com/ubisoft/ubisoft-laforge-animation-dataset).

Robot models sourced from:
[Berkeley Humanoid Lite](https://github.com/HybridRobotics/Berkeley-Humanoid-Lite-Assets) (CC-BY-SA-4.0) · [Booster K1](https://www.boosterobotics.com/) · [Booster T1](https://booster.feishu.cn/wiki/UvowwBes1iNvvUkoeeVc3p5wnUg) · [EngineAI PM01](https://github.com/engineai-robotics/engineai_ros2_workspace) · [Fourier N1](https://github.com/FFTAI/Wiki-GRx-Gym) · [Galaxea R1 Pro](https://galaxea-dynamics.com/) (MIT) · [HighTorque Hi](https://www.hightorquerobotics.com/hi/) · [LEJU Kuavo S45](https://gitee.com/leju-robot/kuavo-ros-opensource) (MIT) · [PAL Talos](https://github.com/google-deepmind/mujoco_menagerie) · [Toddlerbot](https://github.com/hshi74/toddlerbot) · [Unitree G1](https://github.com/unitreerobotics/unitree_ros)

</details>

## License

This project is licensed under the [MIT License](LICENSE).