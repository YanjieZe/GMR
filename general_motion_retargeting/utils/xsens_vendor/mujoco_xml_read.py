import mujoco
import numpy as np


pos_list = [list(),list()]
print(pos_list)
model_name_list = [
    [
        "Hips",
        "Chest4",
        "LeftHip",
        "LeftKnee",
        "LeftToe",
        "LeftShoulder",
        "LeftElbow",
        "LeftWrist",
    ],
    [
        "pelvis_link",
        "torso_link",
        "L_hip_roll_link",
        "L_knee_link",
        "L_ankle_roll_link",
        "L_shoulder_pitch_link",
        "L_elbow_link",
        "L_wrist_yaw_link",
    ],
]
err_list = [list(),list()]
# 加载MuJoCo模型

for i in range(2):
    if i == 0:
        xml_path = "/home/hpx/HPX_LOCO_2/GMR/human_skeleton.xml"
    elif i == 1:
        xml_path = "/home/hpx/HPX_LOCO_2/GMR/assets/Q1P01/mjcf/Q1_01.xml"
    model = mujoco.MjModel.from_xml_path(xml_path)
    data = mujoco.MjData(model)

    # 执行一步仿真同步
    mujoco.mj_step(model, data)
    mujoco_all_body_names = [
        mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, j)
        for j in range(model.nbody)
    ]
    # print(mujoco_all_body_names)
    for name in model_name_list[i]:
        idx = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, name)
        xpos = data.xpos[idx, :]
        pos_list[i].append(np.copy(xpos))
        print(f"{idx} {name}:{xpos}")
    for j in range(len(pos_list[i])-1):
        err_list[i].append(pos_list[i][j+1]-pos_list[i][0])

# print(pos_list)
# print(err_list)
print(pos_list[1][0]/(pos_list[0][0]+1e-9))
for j in range(len(err_list[0])):
    print(err_list[1][j]/(err_list[0][j]+1e-9))
# R_shoulder_yaw_link->pelvis_link :[0, -0.23559764, 0.12422979]
# RightShoulder->Hips :[-0.056326, -0.206501, 0.498412]
