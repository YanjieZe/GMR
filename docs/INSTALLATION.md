# Installation

> ![NOTE]
> Tested on Ubuntu 22.04 / 20.04.

## Base Install

```bash
conda create -n gmr python=3.10 -y
conda activate gmr
pip install -e .
conda install -c conda-forge libstdcxx-ng -y
```

## SMPL-X Fix

After installing SMPL-X, change `ext` in `smplx/body_models.py` from `npz` to `pkl` if you are using SMPL-X pkl files.

## Optional Dependencies

<details>
<summary><b>FBX support (OptiTrack)</b></summary>

Install `fbx_sdk` by following:
1. [ASE poselib instructions](https://github.com/nv-tlabs/ASE/tree/main/ase/poselib#importing-from-fbx)
2. [This issue comment](https://github.com/nv-tlabs/ASE/issues/61#issuecomment-2670315114)

You may need a **separate conda environment** for the FBX extraction step.
</details>

<details>
<summary><b>GVHMR support (monocular video)</b></summary>

Follow the [official GVHMR install guide](https://github.com/zju3dv/GVHMR/blob/main/docs/INSTALL.md).
</details>

<details>
<summary><b>Xsens BVH visualization (PyQt6)</b></summary>

```bash
pip install PyQt6 PyQt6-Qt6 PyQt6-sip
```
</details>

<details>
<summary><b>PICO VR streaming (TWIST2)</b></summary>

See the full [Streaming setup guide](STREAMING.md).
</details>