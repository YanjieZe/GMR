import numpy as np
import smplx
import torch
from scipy.spatial.transform import Rotation as R
from smplx.joint_names import JOINT_NAMES
from scipy.interpolate import interp1d


# Joints names for finger joints and fingertips in SMPLH model
FINGER_JOINT_NAMES = [
    "left_index1", "left_index2", "left_index3",
    "left_middle1", "left_middle2", "left_middle3",
    "left_pinky1", "left_pinky2", "left_pinky3",
    "left_ring1", "left_ring2", "left_ring3",
    "left_thumb1", "left_thumb2", "left_thumb3",
    "right_index1", "right_index2", "right_index3",
    "right_middle1", "right_middle2", "right_middle3",
    "right_pinky1", "right_pinky2", "right_pinky3",
    "right_ring1", "right_ring2", "right_ring3",
    "right_thumb1", "right_thumb2", "right_thumb3"  
]
FINGERTIP_NAMES = [
    "left_thumb", "left_index", "left_middle", "left_ring", "left_pinky",
    "right_thumb", "right_index", "right_middle", "right_ring", "right_pinky"
]


def load_smpl_file(smpl_file):
    smpl_data = np.load(smpl_file, allow_pickle=True)
    return smpl_data


def load_smplx_file(smplx_file, smplx_body_model_path):
    smplx_data = np.load(smplx_file, allow_pickle=True)
    is_smplh = "left_hand_pose" in smplx_data.keys()
    body_model = smplx.create(
        smplx_body_model_path,
        "smplx",
        gender=str(smplx_data["gender"]),
        use_pca=False,
        ext="pkl",
        flat_hand_mean=is_smplh,
    )
    num_frames = smplx_data["pose_body"].shape[0]

    if is_smplh:
        print(f"Using SMPLH model.")
        left_hand_pose = torch.tensor(smplx_data["left_hand_pose"]).float()
        right_hand_pose = torch.tensor(smplx_data["right_hand_pose"]).float()
    else:
        left_hand_pose = torch.zeros(num_frames, 45).float()
        right_hand_pose = torch.zeros(num_frames, 45).float()

    smplx_output = body_model(
        betas=torch.tensor(smplx_data["betas"]).float().view(1, -1),    # (16,)
        global_orient=torch.tensor(smplx_data["root_orient"]).float(),  # (N, 3)
        body_pose=torch.tensor(smplx_data["pose_body"]).float(),        # (N, 63)
        transl=torch.tensor(smplx_data["trans"]).float(),               # (N, 3)
        left_hand_pose=left_hand_pose,                                  # (N, 45)
        right_hand_pose=right_hand_pose,                                # (N, 45)
        jaw_pose=torch.zeros(num_frames, 3).float(),
        leye_pose=torch.zeros(num_frames, 3).float(),
        reye_pose=torch.zeros(num_frames, 3).float(),
        return_full_pose=True,
    )
    
    if len(smplx_data["betas"].shape)==1:
        human_height = 1.66 + 0.1 * smplx_data["betas"][0]
    else:
        human_height = 1.66 + 0.1 * smplx_data["betas"][0, 0]
    
    return smplx_data, body_model, smplx_output, human_height, is_smplh


def get_smplx_data(smplx_data, body_model, smplx_output, curr_frame):
    """
    Must return a dictionary with the following structure:
    {
        "Hips": (position, orientation),
        "Spine": (position, orientation),
        ...
    }
    """
    global_orient = smplx_output.global_orient[curr_frame].squeeze()
    full_body_pose = smplx_output.full_pose[curr_frame].reshape(-1, 3)
    joints = smplx_output.joints[curr_frame].detach().numpy().squeeze()
    joint_names = JOINT_NAMES[: len(body_model.parents)]
    parents = body_model.parents

    result = {}
    joint_orientations = []
    for i, joint_name in enumerate(joint_names):
        if i == 0:
            rot = R.from_rotvec(global_orient)
        else:
            rot = joint_orientations[parents[i]] * R.from_rotvec(
                full_body_pose[i].squeeze()
            )
        joint_orientations.append(rot)
        result[joint_name] = (joints[i], rot.as_quat(scalar_first=True))

  
    return result


def slerp(rot1, rot2, t):
    """Spherical linear interpolation between two rotations."""
    # Convert to quaternions
    q1 = rot1.as_quat()
    q2 = rot2.as_quat()
    
    # Normalize quaternions
    q1 = q1 / np.linalg.norm(q1)
    q2 = q2 / np.linalg.norm(q2)
    
    # Compute dot product
    dot = np.sum(q1 * q2)
    
    # If the dot product is negative, slerp won't take the shorter path
    if dot < 0.0:
        q2 = -q2
        dot = -dot
    
    # If the inputs are too close, linearly interpolate
    if dot > 0.9995:
        return R.from_quat(q1 + t * (q2 - q1))
    
    # Perform SLERP
    theta_0 = np.arccos(dot)
    theta = theta_0 * t
    sin_theta = np.sin(theta)
    sin_theta_0 = np.sin(theta_0)
    
    s0 = np.cos(theta) - dot * sin_theta / sin_theta_0
    s1 = sin_theta / sin_theta_0
    q = s0 * q1 + s1 * q2
    
    return R.from_quat(q)


def FK(global_orient, full_pose, parents):
    print(f"Computing FK...")
    all_rots = []
    T, J, _ = full_pose.shape
    for t in range(T):
        cur_pose = full_pose[t]
        orientations = [R.from_rotvec(global_orient[t])]
        for j in range(1, J):
            rot = orientations[parents[j]] * R.from_rotvec(cur_pose[j])
            orientations.append(rot)
        
        orientations = np.stack([o.as_quat(scalar_first=True) for o in orientations])
        all_rots.append(orientations)

    all_rots = np.stack(all_rots)
    return all_rots


def get_smplx_data_offline_fast(smplx_data, body_model, smplx_output, tgt_fps=30, is_smplh=False):
    """
    Must return a dictionary with the following structure:
    {
        "Hips": (position, orientation),
        "Spine": (position, orientation),
        ...
    }
    """
    src_fps = smplx_data["mocap_frame_rate"].item()
    frame_skip = int(src_fps / tgt_fps)
    num_frames = smplx_data["pose_body"].shape[0]
    global_orient = smplx_output.global_orient.squeeze()
    full_body_pose = smplx_output.full_pose.reshape(num_frames, -1, 3)
    joint_names = JOINT_NAMES[:len(body_model.parents)]
    if is_smplh:
        joint_names += FINGERTIP_NAMES
    joints = get_joints_from_names(smplx_output, joint_names)
    parents = body_model.parents
    
    if tgt_fps < src_fps:
        # perform fps alignment with proper interpolation
        new_num_frames = num_frames // frame_skip
        
        # Create time points for interpolation
        original_time = np.arange(num_frames)
        target_time = np.linspace(0, num_frames-1, new_num_frames)
        
        # Interpolate global orientation using SLERP
        global_orient_interp = []
        for i in range(len(target_time)):
            t = target_time[i]
            idx1 = int(np.floor(t))
            idx2 = min(idx1 + 1, num_frames - 1)
            alpha = t - idx1
            
            rot1 = R.from_rotvec(global_orient[idx1])
            rot2 = R.from_rotvec(global_orient[idx2])
            interp_rot = slerp(rot1, rot2, alpha)
            global_orient_interp.append(interp_rot.as_rotvec())
        global_orient = np.stack(global_orient_interp, axis=0)
        
        # Interpolate full body pose using SLERP
        full_body_pose_interp = []
        for i in range(full_body_pose.shape[1]):  # For each joint
            joint_rots = []
            for j in range(len(target_time)):
                t = target_time[j]
                idx1 = int(np.floor(t))
                idx2 = min(idx1 + 1, num_frames - 1)
                alpha = t - idx1
                
                rot1 = R.from_rotvec(full_body_pose[idx1, i])
                rot2 = R.from_rotvec(full_body_pose[idx2, i])
                interp_rot = slerp(rot1, rot2, alpha)
                joint_rots.append(interp_rot.as_rotvec())
            full_body_pose_interp.append(np.stack(joint_rots, axis=0))
        full_body_pose = np.stack(full_body_pose_interp, axis=1)
        
        # Interpolate joint positions using linear interpolation
        joints_interp = []
        for i in range(joints.shape[1]):  # For each joint
            for j in range(3):  # For each coordinate
                interp_func = interp1d(original_time, joints[:, i, j], kind='linear')
                joints_interp.append(interp_func(target_time))
        joints = np.stack(joints_interp, axis=1).reshape(new_num_frames, -1, 3)
        aligned_fps = len(global_orient) / num_frames * src_fps
    else:
        aligned_fps = tgt_fps

    joint_rots = FK(global_orient=global_orient, full_pose=full_body_pose, parents=parents)
    if is_smplh:
        # Finger rotations in GRAB dataset are offset from expected directions.
        # This recomputes finger rotations based on finger/fingertip joint positions
        joint_rots = correct_finger_joint_rots(joints, joint_rots, joint_names, parents)
        joint_rots = append_fingertip_rots(joint_rots)
    
    smplx_data_frames = [
        {joint_name: (joints[i, j], joint_rots[i, j]) for j, joint_name in enumerate(joint_names)}
        for i in range(len(global_orient))
    ]
    return smplx_data_frames, aligned_fps


def get_joints_from_names(smplx_output, joint_names):
    joints = smplx_output.joints.detach().cpu().numpy().squeeze()
    idxs = [JOINT_NAMES.index(name) for name in joint_names]
    return joints[:, idxs]


def correct_finger_joint_rots(joints, joint_rots, joint_names, parents):
    print(f"Correcting finger joint rotations...")

    # Augment parents to include fingertips
    fingertip_parents = [JOINT_NAMES.index(name + "3") for name in FINGERTIP_NAMES]
    parents = np.concatenate([parents, fingertip_parents], axis=0)
    assert joints.shape[1] == len(parents) and joints.shape[1] == len(joint_names)

    # This array only returns the first child for each joint
    children = []
    for j in range(len(parents)):
        if j in parents:
            children.append(np.where(parents == j)[0][0])
        else:
            children.append(-1)
    children = np.array(children)

    finger_idxs = [joint_names.index(name) for name in FINGER_JOINT_NAMES]
    assert all([idx != -1 for idx in children[finger_idxs]]), "All joints computing rotations must have children"
    finger_joint_rots = []
    for t in range(joints.shape[0]):
        rots = []
        for name, j in zip(FINGER_JOINT_NAMES, finger_idxs):
            cur_pos = joints[t, j]
            child_pos = joints[t, children[j]]
            cur_rot = R.from_quat(joint_rots[t, j], scalar_first=True)
            negate_x = 'right' in name
            rot = rotation_from_two_points(
                cur_pos, child_pos,
                up=cur_rot.as_matrix()[:, 1], # Keep y axis as up direction
                negate_x=negate_x
            ).as_quat(scalar_first=True)
            rots.append(rot)

        rots = np.stack(rots)
        finger_joint_rots.append(rots)

    finger_joint_rots = np.stack(finger_joint_rots)
    joint_rots[:, finger_idxs] = finger_joint_rots
    return joint_rots


def append_fingertip_rots(joint_rots):
    fingertip_parents = [JOINT_NAMES.index(name + "3") for name in FINGERTIP_NAMES]
    joint_rots = np.concatenate([
        joint_rots,
        joint_rots[:, fingertip_parents]
    ], axis=1)
    return joint_rots


def rotation_from_two_points(p0, p1, up=(0,0,1), negate_x=False):
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    x = (p1 - p0) * int(-1 if negate_x else 1)
    nx = np.linalg.norm(x)
    if nx < 1e-9:
        raise ValueError("Points are coincident.")
    x = x / nx

    u = np.asarray(up, float)
    u = u / np.linalg.norm(u)
    if abs(np.dot(x, u)) > 0.99:
        u = np.array([0.0, 1.0, 0.0])  # fallback

    y = u - np.dot(u, x) * x
    y /= np.linalg.norm(y)
    z = np.cross(x, y)
    Rmat = np.column_stack([x, y, z])
    return R.from_matrix(Rmat)