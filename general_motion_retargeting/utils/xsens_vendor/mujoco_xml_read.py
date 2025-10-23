import mujoco
import numpy as np

# 加载MuJoCo模型
# model = mujoco.MjModel.from_xml_path(
#     "/home/hpx/HPX_LOCO_2/GMR/assets/unitree_h1_2/h1_2_handless.xml"
# )  # 替换为实际的XML文件路径
model = mujoco.MjModel.from_xml_path("/home/hpx/HPX_LOCO_2/GMR/human_skeleton.xml")  # 替换为实际的XML文件路径
data = mujoco.MjData(model)

# 执行一步仿真同步
mujoco.mj_step(model, data)
mujoco_all_body_names = [
    mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, i) for i in range(model.nbody)
]
mujoco_body_names_wo_hand = [
    s for s in mujoco_all_body_names if not (s.startswith("R_") or s.startswith("L_"))
]
for name in mujoco_body_names_wo_hand:
    idx = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, name)
    xpos = data.xpos[idx, :]
    if name == "Hips" or name == "RightShoulder" or name == "LeftShoulder":
        print(f"Body: {name}, xpos: {xpos}")
    if (
        name == "torso_link"
        or name == "left_shoulder_roll_link"
        or name == "right_shoulder_roll_link"
    ):
        print(f"Body: {name}, xpos: {xpos}")
