python scripts/bvh_to_robot_dataset.py --src_folder lafan_bvh/ --tgt_folder retargeting_data/Q1/lafan_bvh/ --robot Q1 --num_cpus 16

python general_motion_retargeting/utils/xsens_vendor/pkls_to_csvs.py --retargeting_data_folder retargeting_data/Q1/lafan_bvh/ --csv_folder lafan_Q1/lafan_bvh/