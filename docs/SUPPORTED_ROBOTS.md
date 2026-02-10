# Supported Robots & Data Formats

GMR currently supports **17 humanoid robots** and **6+ motion data formats**.

## Robots

| ID | Robot | Key | DoF | SMPLX | BVH LAFAN1 | FBX OptiTrack | BVH Nokov | PICO |
|----|-------|-----|-----|:-----:|:----------:|:-------------:|:---------:|:----:|
| 0 | Unitree G1 | `unitree_g1` | 29 | ✅ | ✅ | ✅ | ✅ | ✅ |
| 1 | Unitree G1 + Hands | `unitree_g1_with_hands` | 43 | ✅ | ✅ | ✅ | — | — |
| 2 | Unitree H1 | `unitree_h1` | 19 | ✅ | — | — | — | — |
| 3 | Unitree H1 2 | `unitree_h1_2` | 27 | ✅ | — | — | — | — |
| 4 | Booster T1 | `booster_t1` | — | ✅ | — | — | — | — |
| 5 | Booster T1 29dof | `booster_t1_29dof` | — | ✅ | ✅ | — | — | — |
| 6 | Booster K1 | `booster_k1` | 22 | ✅ | — | — | — | — |
| 7 | Stanford ToddlerBot | `stanford_toddy` | — | ✅ | ✅ | — | — | — |
| 8 | Fourier N1 | `fourier_n1` | — | ✅ | ✅ | — | — | — |
| 9 | ENGINEAI PM01 | `engineai_pm01` | — | ✅ | ✅ | — | — | — |
| 10 | HighTorque Hi | `hightorque_hi` | 25 | ✅ | — | — | — | — |
| 11 | Galaxea R1 Pro *(wheeled)* | `galaxea_r1pro` | 24 | ✅ | — | — | — | — |
| 12 | Kuavo S45 | `kuavo_s45` | 28 | ✅ | — | — | — | — |
| 13 | Berkeley Humanoid Lite | `berkeley_humanoid_lite` | 22 | ✅ | — | — | — | — |
| 14 | PND Adam Lite | `pnd_adam_lite` | 25 | ✅ | — | — | — | — |
| 15 | Tienkung | `tienkung` | 20 | ✅ | — | — | — | — |
| 16 | PAL Robotics Talos | `pal_talos` | 30 | — | ✅ | — | — | — |
| 17 | Fourier GR3 | `fourier_gr3` | 31 | ✅ | — | — | — | — |

### Coming Soon

| ID | Robot | Key |
|----|-------|-----|
| 18 | AgiBot A2 | `agibot_a2` |
| 19 | OpenLoong | `openloong` |

> ![NOTE]
> **Want your robot here?** Send robot files (`.xml`, `.urdf`, meshes) to [Yanjie Ze](mailto:lastyanjieze@gmail.com) or [open an issue](https://github.com/YanjieZe/GMR/issues).

## Input Formats

| Format | Source | Script |
|--------|--------|--------|
| **SMPL-X** | [AMASS](https://amass.is.tue.mpg.de/), [OMOMO](https://github.com/lijiaman/omomo_release) | `smplx_to_robot.py` |
| **BVH** | [LAFAN1](https://github.com/ubisoft/ubisoft-laforge-animation-dataset), [Nokov](https://www.nokov.com/) | `bvh_to_robot.py` |
| **BVH (Xsens)** | [Xsens](https://www.xsens.com/) MVN offline export | `xsens_bvh_to_robot.py` |
| **FBX** | [OptiTrack](https://www.optitrack.com/) offline export | `fbx_offline_to_robot.py` |
| **GVHMR** | Monocular video via [GVHMR](https://github.com/zju3dv/GVHMR) | `gvhmr_to_robot.py` |
| **PICO VR** | [XRoboToolkit](https://github.com/XR-Robotics/XRoboToolkit-PC-Service) streaming | See [Streaming docs](STREAMING.md) |
| **CSV** | [BeyondMimic](https://github.com/) export | `batch_gmr_pkl_to_csv.py` |