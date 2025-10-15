import os
import time
import mujoco as mj
import mujoco.viewer as mjv
import imageio
from scipy.spatial.transform import Rotation as R
from general_motion_retargeting import ROBOT_XML_DICT, ROBOT_BASE_DICT, VIEWER_CAM_DISTANCE_DICT
from loop_rate_limiters import RateLimiter
import numpy as np
from rich import print


def draw_frame(
    pos,
    mat,
    v,
    size,
    joint_name=None,
    orientation_correction=R.from_euler("xyz", [0, 0, 0]),
    pos_offset=np.array([0, 0, 0]),
):
    """Draw coordinate frame with basic error handling"""
    try:
        rgba_list = [[1, 0, 0, 1], [0, 1, 0, 1], [0, 0, 1, 1]]
        for i in range(3):
            # Basic bounds checking to prevent crashes
            if v.user_scn.ngeom >= v.user_scn.maxgeom:
                print(f"Warning: Maximum number of geometries reached ({v.user_scn.maxgeom})")
                break
                
            geom = v.user_scn.geoms[v.user_scn.ngeom]
            mj.mjv_initGeom(
                geom,
                type=mj.mjtGeom.mjGEOM_ARROW,
                size=[0.01, 0.01, 0.01],
                pos=pos + pos_offset,
                mat=mat.flatten(),
                rgba=rgba_list[i],
            )
            if joint_name is not None:
                geom.label = joint_name
            fix = orientation_correction.as_matrix()
            mj.mjv_connector(
                v.user_scn.geoms[v.user_scn.ngeom],
                type=mj.mjtGeom.mjGEOM_ARROW,
                width=0.005,
                from_=pos + pos_offset,
                to=pos + pos_offset + size * (mat @ fix)[:, i],
            )
            v.user_scn.ngeom += 1
    except Exception as e:
        print(f"Error in draw_frame: {e}")


class RobotMotionViewer:
    def __init__(self,
                robot_type,
                camera_follow=True,
                motion_fps=30,
                transparent_robot=0,
                # video recording
                record_video=False,
                video_path=None,
                video_width=640,
                video_height=480,
                **kwargs):
        
        self.robot_type = robot_type
        self.motion_fps = motion_fps
        self.camera_follow = camera_follow
        self.record_video = record_video
        
        # Initialize MuJoCo model
        self.xml_path = ROBOT_XML_DICT[robot_type]
        print(f"Loading robot model from: {self.xml_path}")
        self.model = mj.MjModel.from_xml_path(str(self.xml_path))
        self.data = mj.MjData(self.model)
        self.robot_base = ROBOT_BASE_DICT[robot_type]
        self.viewer_cam_distance = VIEWER_CAM_DISTANCE_DICT[robot_type]
        
        # Initial simulation step
        mj.mj_step(self.model, self.data)
        print(f"Model loaded successfully. DOF: {self.model.nq}")
        
        # Initialize rate limiter
        self.rate_limiter = RateLimiter(frequency=self.motion_fps, warn=False)
        
        # Initialize viewer
        print("Initializing MuJoCo viewer...")
        self.viewer = mjv.launch_passive(
            model=self.model,
            data=self.data,
            show_left_ui=False,
            show_right_ui=False
        )
        
        if self.viewer is None:
            raise RuntimeError("Failed to create MuJoCo viewer")
            
        self.viewer.opt.flags[mj.mjtVisFlag.mjVIS_TRANSPARENT] = transparent_robot
        print("Viewer initialized successfully")
        
        # Initialize video recording if requested
        if self.record_video:
            self._init_video_recording(video_path, video_width, video_height)
    
    def _init_video_recording(self, video_path, video_width, video_height):
        """Initialize video recording"""
        assert video_path is not None, "Please provide video path for recording"
        self.video_path = video_path
        video_dir = os.path.dirname(self.video_path)
        
        if not os.path.exists(video_dir):
            os.makedirs(video_dir)
            
        self.mp4_writer = imageio.get_writer(
            self.video_path, 
            fps=self.motion_fps,
            macro_block_size=None
        )
        print(f"Recording video to {self.video_path}")
        
        # Initialize renderer for video recording
        self.renderer = mj.Renderer(
            self.model, 
            height=video_height, 
            width=video_width
        )
    
    def step(self, 
            # robot data
            root_pos, root_rot, dof_pos, 
            # human data
            human_motion_data=None, 
            show_human_body_name=False,
            # scale for human point visualization
            human_point_scale=0.1,
            # human pos offset add for visualization    
            human_pos_offset=np.array([0.0, 0.0, 0]),
            # rate limit
            rate_limit=True, 
            follow_camera=True,
            ):
        """
        Step the motion viewer with basic input validation
        """
        
        try:
            # Basic input validation to prevent crashes
            if len(root_pos) != 3 or len(root_rot) != 4:
                print(f"Invalid input dimensions: root_pos={len(root_pos)}, root_rot={len(root_rot)}")
                return False
                
            expected_dof = self.model.nq - 7
            if len(dof_pos) != expected_dof:
                print(f"Invalid dof_pos dimension: expected {expected_dof}, got {len(dof_pos)}")
                return False
            
            # Check for NaN values that would crash the simulation
            if not (np.all(np.isfinite(root_pos)) and np.all(np.isfinite(root_rot)) and np.all(np.isfinite(dof_pos))):
                print("Warning: NaN or infinite values detected in input data")
                return False
            
            # Update simulation state
            self.data.qpos[:3] = root_pos
            self.data.qpos[3:7] = root_rot
            self.data.qpos[7:] = dof_pos
            
            # Forward dynamics
            mj.mj_forward(self.model, self.data)
            
            # Update camera
            if follow_camera and self.camera_follow:
                self.viewer.cam.lookat = self.data.xpos[self.model.body(self.robot_base).id]
                self.viewer.cam.distance = self.viewer_cam_distance
                self.viewer.cam.elevation = -10
            
            # Handle human motion visualization
            if human_motion_data is not None:
                # Clean custom geometry
                self.viewer.user_scn.ngeom = 0
                
                # Draw human motion frames
                for human_body_name, (pos, rot) in human_motion_data.items():
                    # Basic bounds check to prevent geometry overflow
                    if self.viewer.user_scn.ngeom >= self.viewer.user_scn.maxgeom - 3:
                        break
                        
                    draw_frame(
                        pos,
                        R.from_quat(rot, scalar_first=True).as_matrix(),
                        self.viewer,
                        human_point_scale,
                        pos_offset=human_pos_offset,
                        joint_name=human_body_name if show_human_body_name else None
                    )
            
            # Sync viewer
            self.viewer.sync()
            
            # Handle video recording
            if self.record_video:
                try:
                    self.renderer.update_scene(self.data, camera=self.viewer.cam)
                    img = self.renderer.render()
                    self.mp4_writer.append_data(img)
                except Exception as e:
                    print(f"Video recording error: {e}")
            
            # Rate limiting
            if rate_limit:
                self.rate_limiter.sleep()
            
            return True
            
        except Exception as e:
            print(f"Error in viewer step: {e}")
            return False
    
    def is_alive(self):
        """Check if the viewer is still alive"""
        try:
            return hasattr(self, 'viewer') and self.viewer is not None
        except:
            return False
    
    def close(self):
        """Close the viewer and clean up resources"""
        try:
            if hasattr(self, 'viewer') and self.viewer is not None:
                self.viewer.close()
                
            if self.record_video and hasattr(self, 'mp4_writer'):
                self.mp4_writer.close()
                print(f"Video saved to {self.video_path}")
                
        except Exception as e:
            print(f"Error during cleanup: {e}")
    
    def __del__(self):
        """Destructor to ensure cleanup"""
        self.close()