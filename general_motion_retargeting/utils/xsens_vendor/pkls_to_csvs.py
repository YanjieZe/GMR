import numpy as np
import mujoco
import mujoco.viewer
import time
from BVHParser import BVHParser, euler_to_quat, Anim, quat_fk
from scipy.spatial.transform import Rotation
from typing import Union, List, Dict, Tuple
import pickle
import os
import csv
from functools import partial
import multiprocessing as mp


class cfg:
    only_leg_flag = False  # True, False
    with_wrist_flag = True  # True, False

class pkl_load_and_csv_save:
    def __init__(self, _rtg_data_file_path):
        with open(_rtg_data_file_path, "rb") as f:
            self.data_collection = pickle.load(f)
        #     self.data_collection['root_pos'] = np.delete(self.data_collection['root_pos'] ,[0,1],axis=0)
        #     self.data_collection['root_rot'] = np.delete(self.data_collection['root_rot'] ,[0,1],axis=0)
        #     self.data_collection['dof_pos'] = np.delete(self.data_collection['dof_pos'] ,[0,1],axis=0)
        # self.data_collection['root_pos'] = self.compensate_displacements(self.data_collection['root_rot'],self.data_collection['root_pos'])
        # self.data_collection['root_pos'][:,0:2] -=self.data_collection['root_pos'][0,0:2]
        # self.data_collection['root_rot'] = self.compensate_z_rotation(self.data_collection['root_rot'])

    def save_as_csv(self, _csv_file):
        csv_file = _csv_file
        os.makedirs(os.path.dirname(csv_file), exist_ok=True)

        if os.path.exists(csv_file):
            os.remove(csv_file)
        frames_len = int(self.data_collection["root_pos"].shape[0])
        with open(csv_file, "w", newline="") as file:
            writer = csv.writer(file)
            result = np.concatenate(
                (
                    self.data_collection["root_pos"],
                    self.data_collection["root_rot"],
                    self.data_collection["dof_pos"],
                ),
                axis=1,
            )
            for idx in range(frames_len):
                row = result[idx, :]
                writer.writerow(row)

        print(f"数据已写入 {csv_file}")
        return True


def process_pkl(pkl_path, retargeting_data_folder, csv_folder):
    rel_path = os.path.relpath(pkl_path, retargeting_data_folder)
    csv_path = os.path.join(csv_folder, rel_path.replace('.pkl', '.csv'))
    converter = pkl_load_and_csv_save(pkl_path)
    converter.save_as_csv(csv_path)


import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--retargeting_data_folder",
        help="文件夹路径，包含要转换的.pkl文件。",
        default="",
        type=str,
    )
    parser.add_argument(
        "--csv_folder",
        help="输出文件夹路径，用于保存转换后的.csv文件。",
        default="",
        type=str,
    )
    parser.add_argument("--num_cpus", default=4, type=int)
    args = parser.parse_args()

    if not args.retargeting_data_folder or not args.csv_folder:
        raise ValueError("必须指定 --retargeting_data_folder 和 --csv_folder 参数。")

    print(f"总CPU数量: {mp.cpu_count()}")
    print(f"使用 {args.num_cpus} 个CPU。")

    # 收集所有.pkl文件路径
    pkl_paths = []
    for root, dirs, files in os.walk(args.retargeting_data_folder):
        for file in files:
            if file.endswith('.pkl'):
                pkl_paths.append(os.path.join(root, file))

    if not pkl_paths:
        print("输入文件夹中未找到任何.pkl文件。")
    else:
        print(f"找到 {len(pkl_paths)} 个.pkl文件，开始转换...")

        # 使用多进程处理
        with mp.Pool(args.num_cpus) as pool:
            pool.map(
                partial(process_pkl, retargeting_data_folder=args.retargeting_data_folder, csv_folder=args.csv_folder),
                pkl_paths
            )

        print("所有.pkl文件已转换为.csv文件。")