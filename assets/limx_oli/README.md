# LimX Oli (HU_D04_01)

MuJoCo model of the LimX Dynamics Oli humanoid, taken from
[limxdynamics/humanoid-description](https://github.com/limxdynamics/humanoid-description)
at commit `80fbd2d650c43c38916979c2a6eab7a4c79e38de`:

- `HU_D04_01.xml` is `HU_D04_description/xml/HU_D04_01_vis.xml`, with `meshdir` changed from
  `../meshes/HU_D04_01/` to `meshes/`. Nothing else is modified.
- `meshes/` holds the 44 meshes that file references, copied unchanged from
  `HU_D04_description/meshes/HU_D04_01/`.

`HU_D04_01_vis.xml` is the serial-chain variant of the model: the ankle and waist linkages are
present as visual geometry only, so the model has 31 plain hinge joints (12 leg, 3 waist, 2 head,
14 arm) on a free base, no equality constraints, and needs no parallel-mechanism handling in the IK.

The model is licensed under the Apache License 2.0; see `LICENSE` in this folder.
