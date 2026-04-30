import argparse
import json
import os
import re
from pathlib import Path
from typing import Dict, List


def normalize_key(name: str) -> str:
    name = name.lower()
    for token in ["0-", "stageii", "stagei", "stage", "_poses", "poses", ".pkl", ".npz", ".npy", ".json"]:
        name = name.replace(token, "")
    name = re.sub(r"[^a-z0-9]", "", name)
    return name


def load_description_keys(description_json: Path) -> Dict[str, List[str]]:
    with description_json.open("r") as f:
        data = json.load(f)
    mapping: Dict[str, List[str]] = {}
    for key in data.keys():
        norm = normalize_key(key)
        mapping.setdefault(norm, []).append(key)
    return mapping


def collect_motion_files(motion_folder: Path) -> List[Path]:
    motion_paths: List[Path] = []
    for path in motion_folder.rglob("*.pkl"):
        if path.is_file():
            motion_paths.append(path)
    motion_paths.sort()
    return motion_paths


def build_mapping(motion_folder: Path, description_json: Path) -> Dict[str, str]:
    description_lookup = load_description_keys(description_json)
    motion_paths = collect_motion_files(motion_folder)

    if not description_lookup:
        raise ValueError(f"No entries found in description json: {description_json}")

    mapping: Dict[str, str] = {}
    unmatched: List[str] = []
    ambiguous: Dict[str, List[str]] = {}

    for motion_path in motion_paths:
        rel_path = motion_path.relative_to(motion_folder).as_posix()
        norm = normalize_key(rel_path)
        candidates = description_lookup.get(norm)
        if not candidates:
            unmatched.append(rel_path)
            continue
        if len(candidates) > 1:
            ambiguous[rel_path] = candidates
        mapping[rel_path] = candidates[0]

    if unmatched:
        print("[WARN] Unmatched motion files (no description found):")
        for item in unmatched[:20]:
            print(f"  - {item}")
        if len(unmatched) > 20:
            print(f"  ... and {len(unmatched) - 20} more")

    if ambiguous:
        print("[WARN] Ambiguous matches (multiple descriptions share the same normalized key):")
        for rel_path, candidates in ambiguous.items():
            sample = candidates[:3]
            print(f"  - {rel_path} -> {sample}" + (" ..." if len(candidates) > 3 else ""))

    print(f"[INFO] Matched {len(mapping)} motions out of {len(motion_paths)}")
    return mapping


def save_mapping(mapping: Dict[str, str], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w") as f:
        json.dump(mapping, f, indent=2, ensure_ascii=False)
    print(f"[INFO] Mapping saved to {output_path}")


def parse_args():
    parser = argparse.ArgumentParser(description="Build mapping between motion files and description keys")
    parser.add_argument("--motion_folder", type=Path, required=True, help="Root folder containing motion .pkl files")
    parser.add_argument("--description_json", type=Path, required=True, help="Path to description json (e.g., videofn_info.json)")
    parser.add_argument("--output", type=Path, default=Path("motion_description_mapping.json"), help="Output mapping json path")
    return parser.parse_args()


def main():
    args = parse_args()
    mapping = build_mapping(args.motion_folder, args.description_json)
    save_mapping(mapping, args.output)


if __name__ == "__main__":
    main()
