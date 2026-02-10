# Data Preparation

## SMPL-X Body Model (required for SMPL-X retargeting)

Download SMPL-X body models from [smpl-x.is.tue.mpg.de](https://smpl-x.is.tue.mpg.de/) and place them as:

```
assets/body_models/smplx/
├── SMPLX_NEUTRAL.pkl
├── SMPLX_FEMALE.pkl
└── SMPLX_MALE.pkl
```

## Motion Datasets

| Dataset | Source | Notes |
|---------|--------|-------|
| **AMASS** | [amass.is.tue.mpg.de](https://amass.is.tue.mpg.de/) | Download **SMPL-X** data (not SMPL+H) |
| **OMOMO** | [Google Drive](https://drive.google.com/file/d/1tZVqLB7II0whI-Qjz-z-AU3ponSEyAmm/view?usp=sharing) | Convert with `scripts/convert_omomo_to_smplx.py` |
| **LAFAN1** | [GitHub](https://github.com/ubisoft/ubisoft-laforge-animation-dataset) → [lafan1.zip](https://github.com/ubisoft/ubisoft-laforge-animation-dataset/blob/master/lafan1/lafan1.zip) | Raw BVH files |