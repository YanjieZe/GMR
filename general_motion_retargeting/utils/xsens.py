import general_motion_retargeting.utils.lafan_vendor.utils as utils
from general_motion_retargeting.utils.xsens_vendor.BVHParser import BVHParser


def load_xsens_file(args):
    """
    Must return a dictionary with the following structure:
    {
        "Hips": (position, orientation),
        "Spine": (position, orientation),
        ...
    }
    """
    parser = BVHParser(axis_order="zxy", scale=args.scale)
    with open(args.bvh_file, "r") as f:
        bvh_text = f.read()
    data = parser.parse(
        bvh_text, start=args.start, end=args.end, reset_to_zero=args.reset_to_zero
    )
    global_data = utils.quat_fk(data.quats, data.pos, data.parents)

    frames = []
    for frame in range(data.pos.shape[0]):
        result = {}
        for i, bone in enumerate(data.bones):
            orientation = global_data[0][frame, i]
            position = global_data[1][frame, i]
            result[bone] = (position, orientation)

        # Add modified foot pose
        # To make the config file more universal, 
        # here the descriptions of the key points of the bvh file 
        # that xsens may obtain are aligned with Lafan1
        if args.bvh_format == "3DSM" or args.bvh_format == "MB":
            result["LeftFootMod"] = (result["LeftAnkle"][0], result["LeftToe"][1])
            result["RightFootMod"] = (result["RightAnkle"][0], result["RightToe"][1])
            result["Spine2"] = result.pop("Chest4")

            
        else:
            result["LeftFootMod"] = (result["LeftAnkle"][0], result["lToe"][1])
            result["RightFootMod"] = (result["RightAnkle"][0], result["rToe"][1])
            result["Spine2"] = result.pop("Chest")

        result["LeftUpLeg"] = result.pop("LeftHip")
        result["LeftLeg"] = result.pop("LeftKnee")

        result["RightUpLeg"] = result.pop("RightHip")
        result["RightLeg"] = result.pop("RightKnee")

        result["LeftArm"] = result.pop("LeftShoulder")
        result["LeftForeArm"] = result.pop("LeftElbow")
        result["LeftHand"] = result.pop("LeftWrist")

        result["RightArm"] = result.pop("RightShoulder")
        result["RightForeArm"] = result.pop("RightElbow")
        result["RightHand"] = result.pop("RightWrist")
        frames.append(result)

    # human_height = result["Head"][0][2] - min(
    #     result["LeftFootMod"][0][2], result["RightFootMod"][0][2]
    # )
    # human_height = human_height + 0.2  # cm to m
    human_height = 1.75  # cm to m

    return frames, human_height
