from rich import print

try:
    import xrobotoolkit_sdk as xrt
except:
    print("[bold red]xrobotoolkit_sdk not found, skip for now. If you do not use XRobotStreamer, it's fine.[/bold red]")
import time
import numpy as np
from .rot_utils import quat_mul_np
from scipy.spatial.transform import Rotation as R
import json
import cv2
import os

class XRobotStreamer:
    def __init__(self):
        xrt.init()

        # Joint names for reference
        self.body_joint_names = [
                "Pelvis", "Left_Hip", "Right_Hip", "Spine1", "Left_Knee", "Right_Knee",
                "Spine2", "Left_Ankle", "Right_Ankle", "Spine3", "Left_Foot", "Right_Foot",
                "Neck", "Left_Collar", "Right_Collar", "Head", "Left_Shoulder", "Right_Shoulder",
                "Left_Elbow", "Right_Elbow", "Left_Wrist", "Right_Wrist", "Left_Hand", "Right_Hand"
            ]


        self.hand_joint_names = [
            "Wrist", "Palm",
            "ThumbMetacarpal", "ThumbProximal", "ThumbDistal", "ThumbTip",
            "IndexMetacarpal", "IndexProximal", "IndexIntermediate", "IndexDistal", "IndexTip",
            "MiddleMetacarpal", "MiddleProximal", "MiddleIntermediate", "MiddleDistal", "MiddleTip", 
            "RingMetacarpal", "RingProximal", "RingIntermediate", "RingDistal", "RingTip",
            "LittleMetacarpal", "LittleProximal", "LittleIntermediate", "LittleDistal", "LittleTip"
        ]

        self.last_left_hand_data = {}
        self.last_right_hand_data = {}

    
    def get_controller_data(self):
        left_trigger = xrt.get_left_trigger()
        right_trigger = xrt.get_right_trigger()

        left_grip = xrt.get_left_grip()
        right_grip = xrt.get_right_grip()

        # Buttons
        a_button_pressed = xrt.get_A_button()
        b_button_pressed = xrt.get_B_button()
        x_button_pressed = xrt.get_X_button()
        y_button_pressed = xrt.get_Y_button()

        # Axes
        left_axis = xrt.get_left_axis()
        right_axis = xrt.get_right_axis()

        left_axis_click = xrt.get_left_axis_click()
        right_axis_click = xrt.get_right_axis_click()

        # Timestamp
        timestamp = xrt.get_time_stamp_ns()

        # return
        return {
            'LeftController': {
                'index_trig': left_trigger,
                'grip': left_grip,
                'key_one': x_button_pressed,
                'key_two': y_button_pressed,
                'axis': left_axis,
                'axis_click': left_axis_click,
            },
            'RightController': {
                'index_trig': right_trigger,
                'grip': right_grip,
                'key_one': a_button_pressed,
                'key_two': b_button_pressed,
                'axis': right_axis,
                'axis_click': right_axis_click,
            },
            'timestamp': timestamp,
        }


    def get_headset_pose(self):
        headset_pose = xrt.get_headset_pose()
        return headset_pose
    
    def get_left_controller_pose(self):
        left_pose = xrt.get_left_controller_pose()
        return left_pose
    
    def get_right_controller_pose(self):
        right_pose = xrt.get_right_controller_pose()
        return right_pose

    def get_left_hand_data(self):
        left_hand_tracking_state = xrt.get_left_hand_tracking_state()
        left_hand_is_active = xrt.get_left_hand_is_active()
        hand_data_dict = {}
        for i, joint_name in enumerate(self.hand_joint_names):
            pos = [left_hand_tracking_state[i][0], left_hand_tracking_state[i][1], left_hand_tracking_state[i][2]] # xyz
            rot = [left_hand_tracking_state[i][6], left_hand_tracking_state[i][3], left_hand_tracking_state[i][4], left_hand_tracking_state[i][5]] # scalar first wxyz
            hand_data_dict["LeftHand" + joint_name] = [pos, rot]
        hand_data_dict = self.coordinate_transform_unity_data(hand_data_dict).copy()
        return left_hand_is_active, hand_data_dict
    
    def get_right_hand_data(self):
        right_hand_tracking_state = xrt.get_right_hand_tracking_state()
        right_hand_is_active = xrt.get_right_hand_is_active()
        hand_data_dict = {}
        for i, joint_name in enumerate(self.hand_joint_names):
            pos = [right_hand_tracking_state[i][0], right_hand_tracking_state[i][1], right_hand_tracking_state[i][2]] # xyz
            rot = [right_hand_tracking_state[i][6], right_hand_tracking_state[i][3], right_hand_tracking_state[i][4], right_hand_tracking_state[i][5]] # scalar first wxyz
            hand_data_dict["RightHand" + joint_name] = [pos, rot]
        hand_data_dict = self.coordinate_transform_unity_data(hand_data_dict).copy()
        return right_hand_is_active, hand_data_dict

    def get_raw_body_data(self):

        if not xrt.is_body_data_available():
            # print("No body tracking data. return None", end="\r")
            return None, None, None, None, None

        if xrt.is_body_data_available():
            
            body_poses = xrt.get_body_joints_pose() # list of [x, y, z, qx, qy, qz, qw]
            body_velocities = xrt.get_body_joints_velocity() # vx, vy, vz, wx, wy, wz
            body_accelerations = xrt.get_body_joints_acceleration() # ax, ay, az, wax, way, waz
            imu_timestamps = xrt.get_body_joints_timestamp() # list of [timestamp]
            body_timestamp = xrt.get_body_timestamp_ns() # timestamp in ns

            return body_poses, body_velocities, body_accelerations, imu_timestamps, body_timestamp
        else:
            raise Exception("Body tracking data is not available!")
    
    def get_processed_body_data(self, use_hands=False):

        body_poses, body_velocities, body_accelerations, imu_timestamps, body_timestamp = self.get_raw_body_data()

        if body_poses is None:
            return None
        
        # convert to body_pose_dict
        body_pose_dict = {}
        for i, joint_name in enumerate(self.body_joint_names):
            pos = [body_poses[i][0], body_poses[i][1], body_poses[i][2]] # xyz
            rot = [body_poses[i][6], body_poses[i][3], body_poses[i][4], body_poses[i][5]] # scalar first wxyz
            body_pose_dict[joint_name] = [pos, rot]

        # from unity coordinate to right-hand coordinate
        body_pose_dict = self.coordinate_transform_unity_data(body_pose_dict).copy()

        if use_hands:
            left_hand_is_active, left_hand_data = self.get_left_hand_data()
            right_hand_is_active, right_hand_data = self.get_right_hand_data()
            if left_hand_is_active:
                body_pose_dict.update(left_hand_data)
                self.last_left_hand_data = left_hand_data
            else:
                # use last frame's hand data
                body_pose_dict.update(self.last_left_hand_data)
                
            if right_hand_is_active:
                body_pose_dict.update(right_hand_data)
                self.last_right_hand_data = right_hand_data
            else:
                # use last frame's hand data
                body_pose_dict.update(self.last_right_hand_data)

        return body_pose_dict


    def coordinate_transform_unity_data(self, body_pose_dict):

        for body_name, value in body_pose_dict.items():
                x, y, z = value[0]
                qw, qx, qy, qz = value[1]

                # from unity coordinate to right-hand coordinate
                rotation_matrix = np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]])
                rotation_quat = R.from_matrix(rotation_matrix).as_quat(scalar_first=True)
                orientation = quat_mul_np(rotation_quat, np.array([qw, qx, qy, qz]), scalar_first=True)
                position = np.array([x, y, z]) @ rotation_matrix.T  # cm to m

                body_pose_dict[body_name][0] = position.tolist()
                body_pose_dict[body_name][1] = orientation.tolist()

        return body_pose_dict
    
    def get_current_frame(self):
        body_pose_dict = self.get_processed_body_data()
        left_hand_data = self.get_left_hand_data()
        right_hand_data = self.get_right_hand_data()
        controller_data = self.get_controller_data()
        headset_pose = self.get_headset_pose()
        return body_pose_dict, left_hand_data, right_hand_data, controller_data, headset_pose


class XRobotRecorder:
    """
    Load and process recorded XRobot data from MP4 and TXT files.
    Similar to XRobotStreamer but for recorded data instead of real-time streaming.
    Data is preprocessed during initialization for better performance.
    """
    
    def __init__(self, mp4_path, txt_path):
        """
        Initialize the recorder with paths to MP4 and TXT files.
        All data is preprocessed during initialization.
        
        Args:
            mp4_path: Path to the MP4 video file
            txt_path: Path to the tracking data TXT file
        """
        self.mp4_path = mp4_path
        self.txt_path = txt_path
        
        # Joint names (same as XRobotStreamer)
        self.body_joint_names = [
            "Pelvis", "Left_Hip", "Right_Hip", "Spine1", "Left_Knee", "Right_Knee",
            "Spine2", "Left_Ankle", "Right_Ankle", "Spine3", "Left_Foot", "Right_Foot",
            "Neck", "Left_Collar", "Right_Collar", "Head", "Left_Shoulder", "Right_Shoulder",
            "Left_Elbow", "Right_Elbow", "Left_Wrist", "Right_Wrist", "Left_Hand", "Right_Hand"
        ]
        
        self.hand_joint_names = [
            "Wrist", "Palm",
            "ThumbMetacarpal", "ThumbProximal", "ThumbDistal", "ThumbTip",
            "IndexMetacarpal", "IndexProximal", "IndexIntermediate", "IndexDistal", "IndexTip",
            "MiddleMetacarpal", "MiddleProximal", "MiddleIntermediate", "MiddleDistal", "MiddleTip", 
            "RingMetacarpal", "RingProximal", "RingIntermediate", "RingDistal", "RingTip",
            "LittleMetacarpal", "LittleProximal", "LittleIntermediate", "LittleDistal", "LittleTip"
        ]
        
        # Load raw data
        self.video_frames = []
        self.tracking_data = []
        self.camera_params = None
        self.initial_timestamp = 0
        
        # Preprocessed data (indexed by frame)
        self.processed_body_data = []
        self.processed_left_hand_data = []
        self.processed_right_hand_data = []
        self.processed_controller_data = []
        self.processed_headset_poses = []
        
        self._load_and_process_data()
        
        # Initialize legacy support for backwards compatibility
        self.__init_legacy_support()
    
    def _load_and_process_data(self):
        """Load MP4 and TXT data, then preprocess all frames"""
        print(f"Loading MP4: {self.mp4_path}")
        print(f"Loading TXT: {self.txt_path}")
        
        # Load video
        self._load_mp4()
        
        # Load tracking data
        self._load_tracking_data()
        
        print(f"Loaded {len(self.video_frames)} video frames and {len(self.tracking_data)} tracking frames")
        
        # Preprocess all data
        self._preprocess_all_data()
        
        print(f"Preprocessed {len(self.processed_body_data)} frames")
    
    def _load_mp4(self):
        """Load MP4 video file"""
        cap = cv2.VideoCapture(self.mp4_path)
        if not cap.isOpened():
            raise ValueError(f"Could not open video file: {self.mp4_path}")
        
        frames = []
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frames.append(frame)
        
        cap.release()
        self.video_frames = frames
    
    def _load_tracking_data(self):
        """Load and parse tracking data from TXT file"""
        if not os.path.exists(self.txt_path):
            raise FileNotFoundError(f"Tracking data file not found: {self.txt_path}")
        
        with open(self.txt_path, 'r') as f:
            lines = f.readlines()
        
        # First line contains camera parameters and initial timestamp
        if lines:
            try:
                self.camera_params = json.loads(lines[0].strip())
                # Extract initial timestamp for video frame alignment
                self.initial_timestamp = self.camera_params.get("timeStampNs", 0)
            except json.JSONDecodeError:
                print("Warning: Could not parse camera parameters from first line")
                self.camera_params = {}
                self.initial_timestamp = 0
        
        # Remaining lines contain frame tracking data
        for line_idx, line in enumerate(lines[1:], 1):
            line = line.strip()
            if line:
                try:
                    frame_data = json.loads(line)
                    self.tracking_data.append(frame_data)
                except json.JSONDecodeError as e:
                    print(f"Warning: Could not parse tracking data on line {line_idx + 1}: {e}")
    
    def _find_nearest_mocap_frame(self, video_frame_timestamp):
        """Find the nearest mocap frame for a given video frame timestamp"""
        if not self.tracking_data:
            return None
            
        min_diff = float('inf')
        nearest_frame = None
        
        for frame_data in self.tracking_data:
            frame_timestamp = frame_data.get("timeStampNs", 0)
            diff = abs(frame_timestamp - video_frame_timestamp)
            
            if diff < min_diff:
                min_diff = diff
                nearest_frame = frame_data
        
        return nearest_frame
    
    def _preprocess_all_data(self):
        """Preprocess all tracking data for all frames with timestamp alignment"""
        total_video_frames = len(self.video_frames)
        
        # Initialize preprocessed data lists
        self.processed_body_data = []
        self.processed_left_hand_data = []
        self.processed_right_hand_data = []
        self.processed_controller_data = []
        self.processed_headset_poses = []
        
        # Video frame duration in nanoseconds (30 fps = 33.33ms per frame)
        frame_duration_ns = int(1e9 / 30)  # 33,333,333 ns per frame
        
        # Process each video frame
        for video_frame_idx in range(total_video_frames):
            # Calculate expected timestamp for this video frame
            video_frame_timestamp = self.initial_timestamp + (video_frame_idx * frame_duration_ns)
            
            # Find the nearest mocap frame for this video frame timestamp
            nearest_mocap_frame = self._find_nearest_mocap_frame(video_frame_timestamp)
            
            if nearest_mocap_frame is None:
                # If no mocap data available, use empty data
                self.processed_body_data.append({})
                self.processed_left_hand_data.append({})
                self.processed_right_hand_data.append({})
                self.processed_controller_data.append({
                    'LeftController': {
                        'index_trig': 0.0, 'grip': 0.0, 'key_one': False,
                        'axis': [0.0, 0.0], 'axis_click': False,
                    },
                    'RightController': {
                        'index_trig': 0.0, 'grip': 0.0, 'key_one': False,
                        'axis': [0.0, 0.0], 'axis_click': False,
                    },
                    'timestamp': video_frame_timestamp,
                })
                self.processed_headset_poses.append(None)
                continue
            
            # Process body data
            body_data = self._process_body_data(nearest_mocap_frame)
            self.processed_body_data.append(body_data)
            
            # Process hand data (with fallback logic)
            left_hand_data = self._process_left_hand_data(nearest_mocap_frame, video_frame_idx)
            right_hand_data = self._process_right_hand_data(nearest_mocap_frame, video_frame_idx)
            self.processed_left_hand_data.append(left_hand_data)
            self.processed_right_hand_data.append(right_hand_data)
            
            # Process controller data
            controller_data = self._process_controller_data(nearest_mocap_frame)
            self.processed_controller_data.append(controller_data)
            
            # Process headset pose
            headset_pose = self._process_headset_pose(nearest_mocap_frame)
            self.processed_headset_poses.append(headset_pose)
    
    def get_total_frames(self):
        """Get total number of frames (based on video frames since we align to video timing)"""
        return len(self.video_frames)
    
    def get_video_frame(self, idx):
        """Get video frame at specific index"""
        if 0 <= idx < len(self.video_frames):
            return self.video_frames[idx]
        return None
    
    def _process_body_data(self, frame_data):
        """Process body data for a single frame"""
        body_pose_dict = {}
        
        # Extract body joint data
        if "Body" in frame_data:
            body_data = frame_data["Body"]
            if "joints" in body_data:
                joints = body_data["joints"]
                
                # Parse each joint
                for i, joint_name in enumerate(self.body_joint_names):
                    if i < len(joints):
                        joint_data = joints[i]
                        
                        # Extract position and rotation from 'p' field
                        if "p" in joint_data:
                            p_str = joint_data["p"]
                            # Format: "px,py,pz,qx,qy,qz,qw" (position first, then rotation)
                            try:
                                values = [float(x) for x in p_str.split(',')]
                                if len(values) >= 7:
                                    px, py, pz, qx, qy, qz, qw = values[:7]
                                    pos = [px, py, pz]
                                    rot = [qw, qx, qy, qz]  # scalar first
                                    
                                    body_pose_dict[joint_name] = [pos, rot]
                            except (ValueError, IndexError) as e:
                                print(f"Warning: Could not parse joint {i} ({joint_name}): {e}")
                                continue
        
        # Apply coordinate transformation
        body_pose_dict = self.coordinate_transform_unity_data(body_pose_dict).copy()
        return body_pose_dict
    
    def get_processed_body_data(self, idx, use_hands=False):
        """Get processed body data for specific frame index"""
        if not (0 <= idx < len(self.processed_body_data)):
            return {}
        
        body_data = self.processed_body_data[idx].copy()
        
        # Add hand data if requested
        if use_hands:
            left_hand_data = self.get_left_hand_data(idx)
            right_hand_data = self.get_right_hand_data(idx)
            body_data.update(left_hand_data)
            body_data.update(right_hand_data)
        else:
            left_hand_data = {}
            right_hand_data = {}
        
        return body_data, left_hand_data, right_hand_data
    
    def _process_left_hand_data(self, frame_data, frame_idx):
        """Process left hand data for a single frame with fallback to previous frame"""
        hand_data_dict = {}
        
        if "Hand" not in frame_data:
            # Use previous frame's data if available
            if frame_idx > 0 and frame_idx - 1 < len(self.processed_left_hand_data):
                return self.processed_left_hand_data[frame_idx - 1].copy()
            return {}
        
        hand_data = frame_data["Hand"]
        
        if "leftHand" in hand_data and "HandJointLocations" in hand_data["leftHand"]:
            joint_locations = hand_data["leftHand"]["HandJointLocations"]
            is_active = hand_data["leftHand"].get("isActive", True)
            
            # If hand is not active, use previous frame's data
            if not is_active:
                if frame_idx > 0 and frame_idx - 1 < len(self.processed_left_hand_data):
                    return self.processed_left_hand_data[frame_idx - 1].copy()
                # If no previous frame, continue with empty data
                return {}
            
            for i, joint_name in enumerate(self.hand_joint_names):
                if i < len(joint_locations):
                    joint_data = joint_locations[i]
                    
                    if "p" in joint_data:
                        p_str = joint_data["p"]
                        # Format: "px,py,pz,qx,qy,qz,qw" (position first, then rotation)
                        try:
                            values = [float(x) for x in p_str.split(',')]
                            if len(values) >= 7:
                                px, py, pz, qx, qy, qz, qw = values[:7]
                                pos = [px, py, pz]
                                rot = [qw, qx, qy, qz]  # scalar first
                                
                                hand_data_dict["LeftHand" + joint_name] = [pos, rot]
                        except (ValueError, IndexError) as e:
                            print(f"Warning: Could not parse left hand joint {i} ({joint_name}): {e}")
                            continue
        
        hand_data_dict = self.coordinate_transform_unity_data(hand_data_dict).copy()
        return hand_data_dict
    
    def get_left_hand_data(self, idx):
        """Get left hand tracking data for specific frame index"""
        if 0 <= idx < len(self.processed_left_hand_data):
            return self.processed_left_hand_data[idx].copy()
        return {}
    
    def _process_right_hand_data(self, frame_data, frame_idx):
        """Process right hand data for a single frame with fallback to previous frame"""
        hand_data_dict = {}
        
        if "Hand" not in frame_data:
            # Use previous frame's data if available
            if frame_idx > 0 and frame_idx - 1 < len(self.processed_right_hand_data):
                return self.processed_right_hand_data[frame_idx - 1].copy()
            return {}
        
        hand_data = frame_data["Hand"]
        
        if "rightHand" in hand_data and "HandJointLocations" in hand_data["rightHand"]:
            joint_locations = hand_data["rightHand"]["HandJointLocations"]
            is_active = hand_data["rightHand"].get("isActive", True)
            
            # If hand is not active, use previous frame's data
            if not is_active:
                if frame_idx > 0 and frame_idx - 1 < len(self.processed_right_hand_data):
                    return self.processed_right_hand_data[frame_idx - 1].copy()
                # If no previous frame, continue with empty data
                return {}
            
            for i, joint_name in enumerate(self.hand_joint_names):
                if i < len(joint_locations):
                    joint_data = joint_locations[i]
                    
                    if "p" in joint_data:
                        p_str = joint_data["p"]
                        # Format: "px,py,pz,qx,qy,qz,qw" (position first, then rotation)
                        try:
                            values = [float(x) for x in p_str.split(',')]
                            if len(values) >= 7:
                                px, py, pz, qx, qy, qz, qw = values[:7]
                                pos = [px, py, pz]
                                rot = [qw, qx, qy, qz]  # scalar first
                                
                                hand_data_dict["RightHand" + joint_name] = [pos, rot]
                        except (ValueError, IndexError) as e:
                            print(f"Warning: Could not parse right hand joint {i} ({joint_name}): {e}")
                            continue
        
        hand_data_dict = self.coordinate_transform_unity_data(hand_data_dict).copy()
        return hand_data_dict
    
    def get_right_hand_data(self, idx):
        """Get right hand tracking data for specific frame index"""
        if 0 <= idx < len(self.processed_right_hand_data):
            return self.processed_right_hand_data[idx].copy()
        return {}
    
    def _process_controller_data(self, frame_data):
        """Process controller data for a single frame"""
        if "Controller" not in frame_data:
            return {
                'LeftController': {
                    'index_trig': 0.0,
                    'grip': 0.0,
                    'key_one': False,
                    'axis': [0.0, 0.0],
                    'axis_click': False,
                },
                'RightController': {
                    'index_trig': 0.0,
                    'grip': 0.0,
                    'key_one': False,
                    'axis': [0.0, 0.0],
                    'axis_click': False,
                },
                'timestamp': 0,
            }
        
        controller_data = frame_data["Controller"]
        
        # Parse controller data structure
        result = {
            'LeftController': {
                'index_trig': 0.0,
                'grip': 0.0,
                'key_one': False,
                'axis': [0.0, 0.0],
                'axis_click': False,
            },
            'RightController': {
                'index_trig': 0.0,
                'grip': 0.0,
                'key_one': False,
                'axis': [0.0, 0.0],
                'axis_click': False,
            },
            'timestamp': frame_data.get("timeStampNs", 0),
        }
        
        # Parse left controller
        if "leftController" in controller_data:
            left_ctrl = controller_data["leftController"]
            if "inputState" in left_ctrl:
                input_state = left_ctrl["inputState"]
                result['LeftController']['index_trig'] = input_state.get("indexTrigger", 0.0)
                result['LeftController']['grip'] = input_state.get("handTrigger", 0.0)
                result['LeftController']['key_one'] = input_state.get("menuButton", False)
                thumbstick = input_state.get("thumbstick", {})
                result['LeftController']['axis'] = [thumbstick.get("x", 0.0), thumbstick.get("y", 0.0)]
                result['LeftController']['axis_click'] = input_state.get("thumbstickClick", False)
        
        # Parse right controller
        if "rightController" in controller_data:
            right_ctrl = controller_data["rightController"]
            if "inputState" in right_ctrl:
                input_state = right_ctrl["inputState"]
                result['RightController']['index_trig'] = input_state.get("indexTrigger", 0.0)
                result['RightController']['grip'] = input_state.get("handTrigger", 0.0)
                result['RightController']['key_one'] = input_state.get("menuButton", False)
                thumbstick = input_state.get("thumbstick", {})
                result['RightController']['axis'] = [thumbstick.get("x", 0.0), thumbstick.get("y", 0.0)]
                result['RightController']['axis_click'] = input_state.get("thumbstickClick", False)
        
        return result
    
    def get_controller_data(self, idx):
        """Get controller data for specific frame index"""
        if 0 <= idx < len(self.processed_controller_data):
            return self.processed_controller_data[idx].copy()
        return {
            'LeftController': {
                'index_trig': 0.0,
                'grip': 0.0,
                'key_one': False,
                'axis': [0.0, 0.0],
                'axis_click': False,
            },
            'RightController': {
                'index_trig': 0.0,
                'grip': 0.0,
                'key_one': False,
                'axis': [0.0, 0.0],
                'axis_click': False,
            },
            'timestamp': 0,
        }
    
    def _process_headset_pose(self, frame_data):
        """Process headset pose for a single frame"""
        if "Head" not in frame_data:
            return None
        
        head_data = frame_data["Head"]
        if "pose" in head_data:
            pose_str = head_data["pose"]
            # Parse pose string format: "pos:(x,y,z) rot:(x,y,z,w)"
            try:
                pos_part, rot_part = pose_str.split(" rot:")
                pos_str = pos_part.replace("pos:(", "").replace(")", "")
                rot_str = rot_part.replace("(", "").replace(")", "")
                
                pos = [float(x.strip()) for x in pos_str.split(",")]
                rot = [float(x.strip()) for x in rot_str.split(",")]
                
                return {"position": pos, "rotation": rot}
            except:
                return None
        
        return None
    
    def get_headset_pose(self, idx):
        """Get headset pose for specific frame index"""
        if 0 <= idx < len(self.processed_headset_poses):
            return self.processed_headset_poses[idx]
        return None
    
    def coordinate_transform_unity_data(self, body_pose_dict):
        """
        Transform coordinates from Unity to right-hand coordinate system.
        Same as XRobotStreamer.coordinate_transform_unity_data()
        """
        for body_name, value in body_pose_dict.items():
            x, y, z = value[0]
            qw, qx, qy, qz = value[1]

            # from unity coordinate to right-hand coordinate
            rotation_matrix = np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]])
            rotation_quat = R.from_matrix(rotation_matrix).as_quat(scalar_first=True)
            orientation = quat_mul_np(rotation_quat, np.array([qw, qx, qy, qz]), scalar_first=True)
            position = np.array([x, y, z]) @ rotation_matrix.T

            body_pose_dict[body_name][0] = position.tolist()
            body_pose_dict[body_name][1] = orientation.tolist()

        return body_pose_dict
    
    def get_frame_data(self, idx):
        """Get all data for specific frame index"""
        if not (0 <= idx < self.get_total_frames()):
            return None
        
        body_pose_dict = self.get_processed_body_data(idx, use_hands=True)
        left_hand_data = self.get_left_hand_data(idx)
        right_hand_data = self.get_right_hand_data(idx)
        controller_data = self.get_controller_data(idx)
        video_frame = self.get_video_frame(idx)
        headset_pose = self.get_headset_pose(idx)
        
        return {
            'body_data': body_pose_dict,
            'left_hand_data': left_hand_data,
            'right_hand_data': right_hand_data,
            'controller_data': controller_data,
            'video_frame': video_frame,
            'headset_pose': headset_pose,
            'frame_index': idx
        }
    
    # Legacy methods for backwards compatibility
    def __init_legacy_support(self):
        """Initialize legacy support for current frame index"""
        self.current_frame_index = 0
    
    def set_frame_index(self, index):
        """Set current frame index (legacy method)"""
        if 0 <= index < self.get_total_frames():
            self.current_frame_index = index
        else:
            raise IndexError(f"Frame index {index} out of range [0, {self.get_total_frames()-1}]")
    
    def get_current_frame_data(self):
        """Get current frame's tracking data (legacy method)"""
        if hasattr(self, 'current_frame_index'):
            return self.get_frame_data(self.current_frame_index)
        return self.get_frame_data(0)
    
    def get_current_video_frame(self):
        """Get current video frame (legacy method)"""
        if hasattr(self, 'current_frame_index'):
            return self.get_video_frame(self.current_frame_index)
        return self.get_video_frame(0)
    
    def get_current_frame(self):
        """Get all data for current frame (legacy method)"""
        if hasattr(self, 'current_frame_index'):
            return self.get_frame_data(self.current_frame_index)
        return self.get_frame_data(0)
    
    def next_frame(self):
        """Move to next frame (legacy method)"""
        if not hasattr(self, 'current_frame_index'):
            self.current_frame_index = 0
        if self.current_frame_index < self.get_total_frames() - 1:
            self.current_frame_index += 1
            return True
        return False
    
    def prev_frame(self):
        """Move to previous frame (legacy method)"""
        if not hasattr(self, 'current_frame_index'):
            self.current_frame_index = 0
        if self.current_frame_index > 0:
            self.current_frame_index -= 1
            return True
        return False
    
    def reset(self):
        """Reset to first frame (legacy method)"""
        self.current_frame_index = 0
    
    def get_human_height(self):
        """
        Estimate human height by analyzing all body frames.
        Calculates the max difference between highest and lowest body parts for each frame,
        then returns the maximum height found across all frames.
        
        Returns:
            float: Estimated human height in meters
        """
        if not self.processed_body_data:
            print("Warning: No body data available for height estimation")
            return 1.7  # Default height
        
        max_height = 0.0
        valid_frames = 0
        
        for body_data in self.processed_body_data:
            if not body_data:
                continue
                
            # Extract Y coordinates (height) from all body joints
            y_positions = []
            for joint_data in body_data.values():
                if joint_data and len(joint_data) >= 1 and len(joint_data[0]) >= 3:
                    # joint_data format: [position, rotation]
                    # position format: [x, y, z]
                    y_pos = joint_data[0][1]  # Y coordinate
                    y_positions.append(y_pos)
            
            if len(y_positions) >= 2:  # Need at least 2 joints for height calculation
                frame_height = max(y_positions) - min(y_positions)
                if frame_height > max_height:
                    max_height = frame_height
                valid_frames += 1
        
        if valid_frames == 0:
            print("Warning: No valid frames found for height estimation")
            return 1.7  # Default height
        
        # Add some tolerance since we might not capture the full span (e.g., feet to head)
        estimated_height = max_height * 1.1  # Add 10% buffer
        
        # Clamp to reasonable human height range (1.4m to 2.2m)
        estimated_height = max(1.4, min(2.2, estimated_height))
        
        print(f"Estimated human height: {estimated_height:.2f}m (from {valid_frames} valid frames)")
        return estimated_height
