from __future__ import annotations

import argparse
from pathlib import Path

import joblib
import numpy as np


def _decode_scalar(value: object, default: str = "neutral") -> str:
    if value is None:
        return default
    if isinstance(value, np.ndarray):
        if value.shape == ():
            value = value.item()
        elif value.size == 1:
            value = value.reshape(-1)[0].item()
        else:
            value = value.reshape(-1)[0]
    if isinstance(value, bytes):
        value = value.decode("utf-8")
    return str(value)


def _iter_source_files(source: Path) -> list[Path]:
    if source.is_file():
        return [source]
    return sorted(path for path in source.rglob("*seq_joints24.p") if path.is_file())


def _convert_sequence(payload: dict, source_path: Path, output_path: Path, *, fps: float, overwrite: bool) -> Path:
    if output_path.exists() and not overwrite:
        return output_path

    required = {"seq_name", "pose_body", "root_orient", "trans", "betas"}
    missing = sorted(required - set(payload))
    if missing:
        raise ValueError(f"OMOMO sequence in {source_path} missing keys: {missing}")

    pose_body = np.asarray(payload["pose_body"], dtype=np.float32)
    root_orient = np.asarray(payload["root_orient"], dtype=np.float32)
    trans = np.asarray(payload["trans"], dtype=np.float32)
    betas = np.asarray(payload["betas"], dtype=np.float32)
    if betas.ndim == 0:
        betas = betas.reshape(1)
    elif betas.ndim > 1:
        betas = betas.reshape(-1, betas.shape[-1])[0]

    num_frames = pose_body.shape[0]
    if pose_body.shape != (num_frames, 63):
        raise ValueError(f"pose_body in {source_path} must have shape [T, 63], got {pose_body.shape}")
    if root_orient.shape != (num_frames, 3):
        raise ValueError(f"root_orient in {source_path} must have shape [T, 3], got {root_orient.shape}")
    if trans.shape != (num_frames, 3):
        raise ValueError(f"trans in {source_path} must have shape [T, 3], got {trans.shape}")

    zeros = np.zeros((num_frames, 99), dtype=np.float32)
    poses = np.concatenate((root_orient, pose_body, zeros), axis=1)
    gender = _decode_scalar(payload.get("gender"), default="neutral")
    seq_name = _decode_scalar(payload["seq_name"], default=output_path.stem)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        output_path,
        gender=np.array(gender),
        surface_model_type=np.array("smplx"),
        mocap_frame_rate=np.array(float(payload.get("mocap_frame_rate", fps)), dtype=np.float32),
        mocap_time_length=np.array((num_frames - 1) / float(payload.get("mocap_frame_rate", fps)), dtype=np.float32),
        num_betas=np.array(betas.shape[-1], dtype=np.int32),
        pose_body=pose_body,
        root_orient=root_orient,
        trans=trans,
        betas=betas.astype(np.float32),
        poses=poses,
        seq_name=np.array(seq_name),
        source_path=np.array(str(source_path.resolve())),
        source_format=np.array("omomo"),
    )
    return output_path


def convert_omomo_to_smplx(source: Path, output_dir: Path, *, fps: float = 30.0, overwrite: bool = False) -> list[Path]:
    source_files = _iter_source_files(source.expanduser().resolve())
    if not source_files:
        raise ValueError(f"No OMOMO .p files found under {source}")

    outputs: list[Path] = []
    for source_path in source_files:
        motion_data = joblib.load(source_path)
        if not isinstance(motion_data, dict):
            raise ValueError(f"OMOMO source {source_path} did not load as a dict")
        split_dir = output_dir / source_path.stem
        for payload in motion_data.values():
            if not isinstance(payload, dict):
                continue
            seq_name = _decode_scalar(payload.get("seq_name"), default="sequence")
            output_path = split_dir / f"{seq_name}.npz"
            outputs.append(_convert_sequence(payload, source_path, output_path, fps=fps, overwrite=overwrite))
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert raw OMOMO .p files into GMR-ready SMPL-X npz clips.")
    parser.add_argument("source", type=Path, help="OMOMO .p file or directory containing them")
    parser.add_argument("output_dir", type=Path, help="Directory for converted per-sequence npz clips")
    parser.add_argument("--fps", type=float, default=30.0, help="Fallback mocap frame rate")
    parser.add_argument("--overwrite", action="store_true", default=False)
    args = parser.parse_args()

    outputs = convert_omomo_to_smplx(
        args.source.expanduser().resolve(),
        args.output_dir.expanduser().resolve(),
        fps=args.fps,
        overwrite=args.overwrite,
    )
    print(f"converted={len(outputs)}")


if __name__ == "__main__":
    main()
