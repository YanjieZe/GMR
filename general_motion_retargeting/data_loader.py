
import pickle
import numpy as np

def load_robot_motion(motion_file):
    """
    Load robot motion data from a pickle file.
    """
    with open(motion_file, "rb") as f:
        motion_data = pickle.load(f)
        
        # Handle fps: check for 'fps', 'mocap_frame_rate', or use default
        if "fps" in motion_data:
            motion_fps = motion_data["fps"]
        elif "mocap_frame_rate" in motion_data:
            motion_fps = motion_data["mocap_frame_rate"]
            if isinstance(motion_fps, np.ndarray):
                motion_fps = motion_fps.item() if motion_fps.size == 1 else float(motion_fps[0])
        else:
            # Default to 30 fps if not found
            motion_fps = 30
            print(f"Warning: 'fps' not found in {motion_file}, using default 30 fps")
        
        motion_root_pos = motion_data["root_pos"]
        motion_root_rot = motion_data["root_rot"][:, [3, 0, 1, 2]] # from xyzw to wxyz
        motion_dof_pos = motion_data["dof_pos"]
        motion_local_body_pos = motion_data["local_body_pos"]
        motion_link_body_list = motion_data["link_body_list"]
    return motion_data, motion_fps, motion_root_pos, motion_root_rot, motion_dof_pos, motion_local_body_pos, motion_link_body_list


