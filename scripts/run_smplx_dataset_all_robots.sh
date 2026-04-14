#!/usr/bin/env bash
set -uo pipefail

SRC_FOLDER="dataset/amass/AMASS_smplx"
BASE_TGT_FOLDER="dataset/amass/robot_motion"
DONE_ROBOT="unitree_g1_29dof"
NUM_CPUS="${NUM_CPUS:-8}"
PYTHON_BIN="${PYTHON_BIN:-/home/xsuper/miniconda3/envs/gmr/bin/python}"

LOG_DIR="logs"
mkdir -p "$LOG_DIR"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
LOG_FILE="$LOG_DIR/smplx_dataset_all_robots_${TIMESTAMP}.log"

echo "[INFO] Start time: $(date)" | tee -a "$LOG_FILE"
echo "[INFO] Python: $PYTHON_BIN" | tee -a "$LOG_FILE"
echo "[INFO] Source folder: $SRC_FOLDER" | tee -a "$LOG_FILE"
echo "[INFO] Base target folder: $BASE_TGT_FOLDER" | tee -a "$LOG_FILE"
echo "[INFO] Skip completed robot: $DONE_ROBOT" | tee -a "$LOG_FILE"
echo "[INFO] NUM_CPUS: $NUM_CPUS" | tee -a "$LOG_FILE"

mapfile -t ROBOTS < <(
  "$PYTHON_BIN" - <<'PY'
import ast
from pathlib import Path

params_path = Path('general_motion_retargeting/params.py')
source = params_path.read_text(encoding='utf-8')
module = ast.parse(source)

ik_config_dict = None
for node in module.body:
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == 'IK_CONFIG_DICT':
                ik_config_dict = node.value
                break

if ik_config_dict is None or not isinstance(ik_config_dict, ast.Dict):
    raise RuntimeError('IK_CONFIG_DICT not found in params.py')

smplx_dict = None
for key_node, value_node in zip(ik_config_dict.keys, ik_config_dict.values):
    if isinstance(key_node, ast.Constant) and key_node.value == 'smplx':
        smplx_dict = value_node
        break

if smplx_dict is None or not isinstance(smplx_dict, ast.Dict):
    raise RuntimeError('IK_CONFIG_DICT["smplx"] not found in params.py')

robots = []
for key_node in smplx_dict.keys:
    if isinstance(key_node, ast.Constant) and isinstance(key_node.value, str):
        robots.append(key_node.value)

for robot in robots:
    print(robot)
PY
)

echo "[INFO] Total robots from IK_CONFIG_DICT['smplx']: ${#ROBOTS[@]}" | tee -a "$LOG_FILE"

for robot in "${ROBOTS[@]}"; do
  if [[ "$robot" == "$DONE_ROBOT" ]]; then
    echo "[SKIP] $robot already completed" | tee -a "$LOG_FILE"
    continue
  fi

  tgt_folder="$BASE_TGT_FOLDER/$robot"
  echo "[RUN] $(date) robot=$robot tgt=$tgt_folder" | tee -a "$LOG_FILE"

  MAX_RETRIES=5
  attempt=0
  success=false
  while [[ $attempt -lt $MAX_RETRIES ]]; do
    attempt=$((attempt + 1))
    echo "[ATTEMPT] $attempt/$MAX_RETRIES for robot=$robot at $(date)" | tee -a "$LOG_FILE"
    if "$PYTHON_BIN" scripts/smplx_to_robot_dataset.py \
        --src_folder "$SRC_FOLDER" \
        --tgt_folder "$tgt_folder" \
        --robot "$robot" \
        --num_cpus "$NUM_CPUS" 2>&1 | tee -a "$LOG_FILE"; then
      success=true
      break
    else
      EXIT_CODE=${PIPESTATUS[0]}
      echo "[WARN] robot=$robot attempt $attempt failed (exit $EXIT_CODE), retrying in 30s..." | tee -a "$LOG_FILE"
      sleep 30
    fi
  done

  if $success; then
    echo "[DONE] $(date) robot=$robot" | tee -a "$LOG_FILE"
  else
    echo "[FAILED] $(date) robot=$robot after $MAX_RETRIES attempts, skipping." | tee -a "$LOG_FILE"
  fi
done

echo "[INFO] All robots finished at $(date)" | tee -a "$LOG_FILE"
echo "[INFO] Log file: $LOG_FILE"
