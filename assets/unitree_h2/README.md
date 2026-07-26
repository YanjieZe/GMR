# Unitree H2 Description (MJCF)

## Overview

MJCF description for the [Unitree H2](https://www.unitree.com/), developed by
[Unitree Robotics](https://www.unitree.com/).

| file | contents |
| ---- | -------- |
| `h2.xml` | robot model, 29 actuated DoF: Leg (2\*6) + Waist (3) + Arm (2\*7). The head is fixed in this MJCF. |
| `h2_mocap.xml` | `h2.xml` plus a ground plane and lighting — this is the file registered in `params.py` |
| `meshes/` | 32 collision/visual STL meshes |

## Provenance

Taken from [`unitreerobotics/unitree_rl_mjlab`](https://github.com/unitreerobotics/unitree_rl_mjlab)
(`src/assets/robots/unitree_h2/xmls/`), which is Apache-2.0 licensed; see `LICENSE`
in this directory.

`h2.xml` is a verbatim copy except for a single attribute — `meshdir="assets"` was
changed to `meshdir="meshes"` to match the directory layout used by every other
robot in this repo.

No URDF is included: Unitree does not currently publish one for the H2
(`unitreerobotics/unitree_model` ships USD only). The retargeting pipeline only
needs the MJCF; `scripts/vis_robot_urdf.py` is therefore not usable for this robot,
as is already the case for several other robots here.

## Visualization with [MuJoCo](https://github.com/google-deepmind/mujoco)

```bash
pip install mujoco
python -m mujoco.viewer
```

Then drag and drop `h2_mocap.xml` into the viewer.
