import general_motion_retargeting.utils.lafan_vendor.utils as utils
from general_motion_retargeting.utils.xsens_vendor.BVHParser import BVHParser, Anim
import numpy as np
from general_motion_retargeting.utils.xsens_vendor.bvh_edit.CurveEditor import (
    OffsetManager,
)


def bvh_parse(args):
    parser = BVHParser(axis_order="zxy", scale=args.scale)
    with open(args.bvh_file, "r") as f:
        bvh_text = f.read()
    rotations, positions = parser.parse(
        bvh_text, start=args.start, end=args.end, reset_to_zero=args.reset_to_zero
    )
    offset_manager = OffsetManager(default_path="offsets.json")
    loaded_offsets = offset_manager.load_offsets()
    offsets = offset_manager.parse_to_window_format(parser.names, loaded_offsets)
    new_rotations = np.zeros_like(rotations)
    joint_offset = np.zeros((new_rotations.shape[1], 3))
    for i in range(new_rotations.shape[1]):
        for j in range(3):
            joint_offset[i, j] = offsets[(i, j)]
    new_rotations = rotations + joint_offset
    positions = np.copy(parser.positions)
    _quats, _positions, _offsets, _parents = parser._MOTION_data_post_processing(
        new_rotations, positions, reset_to_zero=True
    )
    print("MOTION_data_post_processing")
    anim = Anim(_quats, _positions, _offsets, _parents, parser.names)
    global_data = utils.quat_fk(anim.quats, anim.pos, anim.parents)
    return anim, global_data, parser.frame_time


def load_xsens_file(args):
    """
    Must return a dictionary with the following structure:
    {
        "Hips": (position, orientation),
        "Spine": (position, orientation),
        ...
    }
    """
    anim, global_data, frame_time = bvh_parse(args)
    frames = []
    for frame in range(anim.pos.shape[0]):
        result = {}
        for i, bone in enumerate(anim.bones):
            orientation = global_data[0][frame, i]
            position = global_data[1][frame, i]
            result[bone] = (position, orientation)

        # Add modified foot pose
        # To make the config file more universal,
        # here the descriptions of the key points of the bvh file
        # that xsens may obtain are aligned with Lafan1
        if args.bvh_format == "3DSM":
            result["LeftFootMod"] = (
                np.array(
                    [
                        result["LeftAnkle"][0][0],
                        result["LeftAnkle"][0][1],
                        result["LeftAnkle"][0][2],
                        # result["LeftToe"][0][2],
                    ]
                ),
                result["LeftAnkle"][1],
                # result["LeftToe_end_site"][1],
            )
            result["RightFootMod"] = (
                np.array(
                    [
                        result["RightAnkle"][0][0],
                        result["RightAnkle"][0][1],
                        result["RightAnkle"][0][2],
                        # result["RightToe"][0][2],
                    ]
                ),
                result["RightAnkle"][1],
                # result["RightToe_end_site"][1],
            )

            # result["Spine2"] = result.pop("Chest4")

        frames.append(result)

    human_height = result["Head_end_site"][0][2] - min(
        result["LeftToe_end_site"][0][2], result["LeftToe_end_site"][0][2]
    )
    return frames, human_height, frame_time
