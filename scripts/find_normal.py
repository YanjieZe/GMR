#把annotations.json中label为normal的motion文件复制到data/normal目录下

import json
import shutil
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    annotation_file = root / "annotations.json"
    dest_dir = root / "data" / "normal"
    dest_dir.mkdir(parents=True, exist_ok=True)

    if not annotation_file.exists():
        print(f"[WARN] Annotation file not found: {annotation_file}")
        return

    with annotation_file.open("r", encoding="utf-8") as f:
        annotations = json.load(f)

    copied = 0
    for motion_file, info in annotations.items():
        if info.get("label") != "normal":
            continue
        src_path = root / info.get("motion_path", "")
        if not src_path.exists():
            print(f"[WARN] Missing source file: {src_path}")
            continue
        dest_path = dest_dir / Path(motion_file).name
        shutil.copy2(src_path, dest_path)
        copied += 1
        print(f"Copied {src_path} -> {dest_path}")

    print(f"Done. Copied {copied} normal files to {dest_dir}")


if __name__ == "__main__":
    main()

