import argparse
import os
import pathlib


HERE = pathlib.Path(__file__).parent
DEFAULT_HARD_MOTIONS_FOLDER = HERE / ".." / "assets" / "hard_motions"
DEFAULT_EXCLUDE_FILE_CONTENT = ["BMLrub", "EKUT", "crawl", "_lie", "upstairs", "downstairs"]
DEFAULT_EXCLUDE_FILE_CONTENT_LOWER = [item.lower() for item in DEFAULT_EXCLUDE_FILE_CONTENT]


def build_motion_key(file_path, root_folder):
    rel_path = os.path.relpath(file_path, root_folder)
    rel_no_ext = os.path.splitext(rel_path)[0]
    return rel_no_ext.replace(os.sep, "_")


def load_hard_motions(hard_motions_folder):
    hard_motions_paths = [
        hard_motions_folder / "0.txt",
        hard_motions_folder / "1.txt",
    ]
    hard_motions = set()

    for hard_motions_path in hard_motions_paths:
        with open(hard_motions_path, "r") as file:
            for line in file:
                if "Motion:" not in line:
                    continue
                motion_path = line.split(":", 1)[1].strip()
                motion_path = motion_path.split(",", 1)[0].strip()
                motion_key = os.path.splitext(motion_path)[0]
                hard_motions.add(motion_key)

    return hard_motions


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--target_folder",
        type=str,
        default="dataset/amass/robot_motion/unitree_g1_29dof",
    )
    parser.add_argument(
        "--hard_motions_folder",
        type=str,
        default=str(DEFAULT_HARD_MOTIONS_FOLDER),
    )
    parser.add_argument("--dry_run", action="store_true", default=False)
    args = parser.parse_args()

    target_folder = os.path.abspath(args.target_folder)
    hard_motions_folder = pathlib.Path(args.hard_motions_folder)

    hard_motions = load_hard_motions(hard_motions_folder)
    print(f"Loaded hard motions: {len(hard_motions)}")

    candidates = []
    for dirpath, _, filenames in os.walk(target_folder):
        for filename in sorted(filenames):
            if filename.endswith(".pkl"):
                file_path = os.path.join(dirpath, filename)
                motion_key = build_motion_key(file_path, target_folder)
                motion_key_lower = motion_key.lower()

                matched_hard = motion_key in hard_motions
                matched_exclude = any(content in motion_key_lower for content in DEFAULT_EXCLUDE_FILE_CONTENT_LOWER)

                if matched_hard or matched_exclude:
                    candidates.append((file_path, motion_key, matched_hard, matched_exclude))

    print(f"Matched files to delete: {len(candidates)}")

    hard_match_count = sum(1 for _, _, matched_hard, _ in candidates if matched_hard)
    exclude_match_count = sum(1 for _, _, _, matched_exclude in candidates if matched_exclude)
    print(f"- matched by hard_motions: {hard_match_count}")
    print(f"- matched by exclude_file_content: {exclude_match_count}")

    if args.dry_run:
        print("Dry run mode: no files deleted.")
        preview_num = min(20, len(candidates))
        for file_path, motion_key, matched_hard, matched_exclude in candidates[:preview_num]:
            print(
                f"[DRY-RUN] {file_path} | key={motion_key} | hard={matched_hard} | exclude={matched_exclude}"
            )
        if len(candidates) > preview_num:
            print(f"... and {len(candidates) - preview_num} more")
        return

    deleted = 0
    for file_path, _, _, _ in candidates:
        if os.path.exists(file_path):
            os.remove(file_path)
            deleted += 1

    print(f"Deleted files: {deleted}")


if __name__ == "__main__":
    main()
