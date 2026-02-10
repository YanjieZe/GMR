import numpy as np
from scipy.spatial.transform import Rotation as R

def get_human_neck_orientation(head_pose=None):
      """
      从XRoboToolkit SDK获取头戴设备姿态并计算neck的roll, pitch, yaw角度
      
      Returns:
          tuple: (roll, pitch, yaw) 以度为单位
      """
      # 提取四元数 [x, y, z, w] 格式 (scipy要求的格式)
      quat_xyzw = np.array([head_pose[3], head_pose[4], head_pose[5], head_pose[6]])

      # 直接转换为欧拉角
      rotation = R.from_quat(quat_xyzw)
      roll, pitch, yaw = rotation.as_euler('xyz', degrees=True)

      return roll, pitch, yaw

def human_head_to_robot_neck(smplx_data=None):
    """
    Extract neck angle from smplx_data for our designed head
    dof 0: yaw
    dof 1: pitch
    """
    if smplx_data is None:
        return 0.0, 0.0
    spine_rotation = smplx_data['Spine3'][1] # wxyz
    # spine_rotation = smplx_data['Neck'][1] # wxyz # not work, as neck is kind aligned to head.
    head_rotation = smplx_data['Head'][1] # wxyz

    # Convert to rotation objects
    spine_rotation = R.from_quat(spine_rotation, scalar_first=True)
    head_rotation = R.from_quat(head_rotation, scalar_first=True)
    
    # compute the rpy of the head in local frame (relative to spine)
    # Get the relative rotation: head relative to spine
    relative_rotation = spine_rotation.inv() * head_rotation
    
    # Convert to Euler angles (roll, pitch, yaw)
    roll, pitch, yaw = relative_rotation.as_euler('xyz', degrees=True)

    

    # print(f"roll: {roll:.0f}, pitch: {pitch:.0f}, yaw: {yaw:.0f}", end="\r")
    # return float(roll), float(pitch), float(yaw)
    neck_yaw = - pitch # 10~150, middlle 90
    neck_pitch = roll # 8~125, middle 60


    # offset
    # neck_yaw -= 10
    # neck_pitch -= 8

    # clip to above 0   
    # neck_yaw = max(neck_yaw, 0)
    # neck_pitch = max(neck_pitch, 0)

    # degree to radian
    neck_yaw = np.deg2rad(neck_yaw)
    neck_pitch = np.deg2rad(neck_pitch)

    return neck_yaw, neck_pitch
