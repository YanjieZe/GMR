import os
import json
import argparse
import sys

# Add the current directory to Python path to find poselib module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from poselib.skeleton.skeleton3d import SkeletonMotion

def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(description='Import FBX file and convert to PoseLib format')
    parser.add_argument('--input', '-i', required=True, help='Input FBX file path')
    parser.add_argument('--output', '-o', required=True, help='Output file path for the converted motion')
    parser.add_argument('--root-joint', '-r', default='Hips', help='Root joint name (default: Hips)')
    parser.add_argument('--fps', '-f', type=int, default=120, help='FPS for the motion (default: 120)')
    
    args = parser.parse_args()
    
    # Check if input file exists
    if not os.path.exists(args.input):
        print(f"Error: Input file '{args.input}' does not exist")
        return
    
    # Create output directory if it doesn't exist
    output_dir = os.path.dirname(args.output)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Import fbx file
    motion = SkeletonMotion.from_fbx(
        fbx_file_path=args.input,
        root_joint=args.root_joint,
        fps=args.fps
    )
    
    # Save motion in the specified format
    motion.to_retarget_motion_file(args.output)
    print(f"Successfully converted '{args.input}' to '{args.output}'")

if __name__ == "__main__":
    main()
