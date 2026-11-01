"""
Water Pipeline Dataset Merger (Roboflow YOLO Object Detection)
---------------------------------------------------------------
1. Put your four Roboflow ZIP files in INPUT_DIR.
2. Run this script once with AUTO_CLASS_MAP empty to inspect class names.
3. Fill AUTO_CLASS_MAP using the exact source names printed in the report.
4. Run again to build the unified dataset.

Final classes:
  0 crack
  1 joint_displacement
  2 corrosion
  3 blockage

"normal" is treated as a background class: its boxes are removed and the
image is retained with an empty label file.

This script supports Roboflow YOLO detection ZIPs containing data.yaml,
images/, and labels/ (train/valid/test folders or a single images/ folder).
It does not support segmentation or pose annotations.
"""

from pathlib import Path
import zipfile
import tempfile
import shutil
import hashlib
import random
import re
import json
from collections import Counter, defaultdict

import yaml
from PIL import Image

# --------------------------- USER SETTINGS ---------------------------

# Use the folder containing this script (your local Dataset folder).
BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR
OUTPUT_DIR = BASE_DIR / "Pipeline_Defect_Dataset"
REPORT_DIR = BASE_DIR / "pipeline_dataset_reports"

ZIP_FILES = None  # None = automatically use every .zip in INPUT_DIR

SEED = 42
TRAIN_RATIO = 0.70
VAL_RATIO = 0.20
TEST_RATIO = 0.10

# Exact target class names in the final dataset.
FINAL_CLASSES = [
    "crack",
    "joint_displacement",
    "corrosion",
    "blockage",
]

# Add exact source class names from the inventory report.
# Example:
# AUTO_CLASS_MAP = {
#     "crack": "crack",
#     "pipe crack": "crack",
#     "longitudinal crack": "crack",
#     "joint fault": "joint_displacement",
#     "joint displacement": "joint_displacement",
#     "rust": "corrosion",
#     "corrosion": "corrosion",
#     "debris": "blockage",
#     "obstruction": "blockage",
#     "normal": "normal",
# }
#
# Mapping to "normal" means keep the image but remove that class's boxes.
# Unmapped classes are excluded from annotations.
AUTO_CLASS_MAP = {}

# Set True only after reviewing/filling AUTO_CLASS_MAP.
BUILD_DATASET = False

# --------------------------------------------------------------------

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
FINAL_ID = {name: i for i, name in enumerate(FINAL_CLASSES)}


def norm_name(value):
    """Normalize class names for matching without changing their meaning."""
    value = str(value).strip().lower()
    value = value.replace("&", " and ")
    value = re.sub(r"[_\-]+", " ", value)
    value = re.sub(r"[^a-z0-9 ]+", "", value)
    return re.sub(r"\s+", " ", value).strip()


def load_names(data_yaml):
    with open(data_yaml, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    names = cfg.get("names")
    if isinstance(names, dict):
        return {int(k): str(v) for k, v in names.items()}
    if isinstance(names, list):
        return {i: str(v) for i, v in enumerate(names)}
    raise ValueError(f"No valid 'names' field found in {data_yaml}")


def safe_extract(zip_path, destination):
    """Extract safely; reject paths attempting to escape destination."""
    destination = destination.resolve()
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.infolist():
            target = (destination / member.filename).resolve()
            if destination not in target.parents and target != destination:
                raise ValueError(f"Unsafe path in ZIP: {member.filename}")
        zf.extractall(destination)


def find_yaml(root):
    candidates = list(root.rglob("data.yaml")) + list(root.rglob("data.yml"))
    if not candidates:
        raise FileNotFoundError(f"No data.yaml/data.yml found under {root}")
    # Prefer the shallowest yaml path.
    return sorted(candidates, key=lambda p: len(p.parts))[0]


def image_label_pairs(dataset_root):
    """Find images and their matching YOLO labels by relative path."""
    pairs = []
    for image_path in dataset_root.rglob("*"):
        if not image_path.is_file() or image_path.suffix.lower() not in IMAGE_EXTS:
            continue
        # Ignore images inside obvious documentation/sample folders.
        if any(part.lower() in {"runs", "output", "outputs"} for part in image_path.parts):
            continue

        parts = list(image_path.parts)
        image_idx = None
        for i, part in enumerate(parts):
            if part.lower() == "images":
                image_idx = i
                break

        label_path = None
        if image_idx is not None:
            label_parts = parts[:]
            label_parts[image_idx] = "labels"
            label_parts[-1] = image_path.stem + ".txt"
            candidate = Path(*label_parts)
            if candidate.exists():
                label_path = candidate
        else:
            candidate = image_path.with_suffix(".txt")
            if candidate.exists():
                label_path = candidate

        pairs.append((image_path, label_path))
    return pairs


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_yolo_label(label_path, source_names, class_map, image_path):
    """
    Parse detection labels: class x_center y_center width height [optional extras].
    Returns retained normalized lines and class set.
    """
    retained = []
    classes_present = set()
    if label_path is None:
        return retained, classes_present

    try:
        text = label_path.read_text(encoding="utf-8-sig").strip()
    except Exception as e:
        raise ValueError(f"Cannot read label {label_path}: {e}")

    if not text:
        return retained, classes_present

    for line_no, line in enumerate(text.splitlines(), start=1):
        fields = line.strip().split()
        if not fields:
            continue
        if len(fields) != 5:
            raise ValueError(
                f"Non-detection or malformed annotation in {label_path}, "
                f"line {line_no}: expected 5 fields, got {len(fields)}. "
                "This script is for YOLO object detection, not segmentation."
            )
        try:
            old_id = int(float(fields[0]))
            coords = [float(x) for x in fields[1:]]
        except ValueError:
            raise ValueError(f"Invalid numeric annotation in {label_path}, line {line_no}")

        if old_id not in source_names:
            raise ValueError(
                f"Class ID {old_id} not present in data.yaml for {label_path}"
            )

        # Reject invalid boxes rather than silently training on them.
        x, y, w, h = coords
        if not all(0.0 <= v <= 1.0 for v in coords) or w <= 0 or h <= 0:
            raise ValueError(f"Invalid normalized box in {label_path}, line {line_no}")

        original_name = source_names[old_id]
        normalized_source = norm_name(original_name)
        mapped = class_map.get(normalized_source)

        # Unmapped / extra classes are intentionally excluded.
        if mapped is None:
            continue

        mapped = norm_name(mapped)
        if mapped == "normal":
            # Normal is background, not a detection class.
            continue
        if mapped not in FINAL_ID:
            raise ValueError(
                f"Mapping for '{original_name}' points to unsupported target '{mapped}'."
            )

        new_id = FINAL_ID[mapped]
        retained.append(
            f"{new_id} " + " ".join(f"{v:.6f}" for v in coords)
        )
        classes_present.add(new_id)

    return retained, classes_present


def inventory(zip_paths, work_root):
    print("\n========== DATASET INVENTORY ==========")
    all_names = defaultdict(set)
    summary = []
    for idx, zip_path in enumerate(zip_paths, start=1):
        extract_dir = work_root / f"dataset_{idx}"
        extract_dir.mkdir(parents=True, exist_ok=True)
        safe_extract(zip_path, extract_dir)
        yaml_path = find_yaml(extract_dir)
        names = load_names(yaml_path)
        pairs = image_label_pairs(yaml_path.parent)
        all_names[zip_path.name].update(names.values())
        summary.append({
            "zip": zip_path.name,
            "yaml": str(yaml_path),
            "classes": names,
            "images_found": len(pairs),
            "labels_found": sum(1 for _, lp in pairs if lp is not None),
        })
        print(f"\n{zip_path.name}")
        print(f"  data.yaml: {yaml_path}")
        print(f"  images found: {len(pairs)}")
        print(f"  matching label files found: {sum(1 for _, lp in pairs if lp is not None)}")
        print("  class IDs:")
        for class_id, name in sorted(names.items()):
            print(f"    {class_id}: {name}")

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "inventory.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )

    print("\n========== REQUIRED CLASS MAPPING ==========")
    unique = sorted({name for names in all_names.values() for name in names},
                    key=lambda x: norm_name(x))
    for name in unique:
        print(f"  {name!r}  ->  add an explicit mapping if it is a core class or Normal")
    print("\nInventory saved to:", REPORT_DIR / "inventory.json")
    return summary


def build_dataset(zip_paths, extracted_roots):
    # Explicit map keys are normalized so capitalization/underscores do not matter.
    class_map = {norm_name(k): norm_name(v) for k, v in AUTO_CLASS_MAP.items()}

    if not class_map:
        raise ValueError("AUTO_CLASS_MAP is empty. Run inventory, then fill the mapping.")

    # Records keyed by exact image content hash. Duplicate images are merged;
    # their retained annotation lines are unioned (exact duplicate boxes removed).
    records = {}
    stats = Counter()
    per_source = []

    for zip_path, root in zip(zip_paths, extracted_roots):
        yaml_path = find_yaml(root)
        source_names = load_names(yaml_path)
        pairs = image_label_pairs(yaml_path.parent)
        source_count = Counter()

        for image_path, label_path in pairs:
            try:
                with Image.open(image_path) as im:
                    im.verify()
            except Exception:
                stats["corrupt_images_skipped"] += 1
                continue

            digest = sha256_file(image_path)
            try:
                mapped_lines, classes_present = parse_yolo_label(
                    label_path, source_names, class_map, image_path
                )
            except Exception as e:
                raise RuntimeError(f"\nAnnotation problem in {image_path}\n{e}")

            # A missing label file is not automatically considered Normal.
            # Retain only if there is an explicit mapped Normal label or a truly
            # empty existing label file. Missing-label images are skipped.
            if label_path is None:
                stats["images_missing_label_skipped"] += 1
                continue

            source_count["images_seen"] += 1
            if not mapped_lines:
                source_count["background_or_no_target"] += 1

            if digest not in records:
                records[digest] = {
                    "image": image_path,
                    "lines": set(mapped_lines),
                    "classes": set(classes_present),
                    "sources": {zip_path.name},
                }
            else:
                records[digest]["lines"].update(mapped_lines)
                records[digest]["classes"].update(classes_present)
                records[digest]["sources"].add(zip_path.name)
                stats["duplicate_images_merged"] += 1

        per_source.append({"zip": zip_path.name, **source_count})

    # Keep only images that have at least one target box or are explicit background
    # examples. An empty label is accepted as background only when it existed in source.
    items = []
    for digest, rec in records.items():
        items.append({
            "hash": digest,
            "image": rec["image"],
            "lines": sorted(rec["lines"]),
            "classes": sorted(rec["classes"]),
        })

    if not items:
        raise RuntimeError("No usable images found. Check ZIP structure and annotations.")

    # Deterministic random split. A report shows class counts in each split.
    rng = random.Random(SEED)
    rng.shuffle(items)
    n = len(items)
    n_train = int(n * TRAIN_RATIO)
    n_val = int(n * VAL_RATIO)
    splits = {
        "train": items[:n_train],
        "valid": items[n_train:n_train + n_val],
        "test": items[n_train + n_val:],
    }

    # Rebuild output from scratch to avoid stale files.
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    for split in splits:
        (OUTPUT_DIR / split / "images").mkdir(parents=True, exist_ok=True)
        (OUTPUT_DIR / split / "labels").mkdir(parents=True, exist_ok=True)

    class_counts = {}
    background_counts = {}
    for split, split_items in splits.items():
        counts = Counter()
        backgrounds = 0
        for index, item in enumerate(split_items):
            source_image = item["image"]
            # Unique, deterministic filename avoids collisions across ZIP files.
            filename = f"{item['hash'][:16]}_{index}{source_image.suffix.lower()}"
            dest_image = OUTPUT_DIR / split / "images" / filename
            dest_label = OUTPUT_DIR / split / "labels" / f"{Path(filename).stem}.txt"

            shutil.copy2(source_image, dest_image)
            label_text = "\n".join(item["lines"])
            dest_label.write_text(label_text + ("\n" if label_text else ""), encoding="utf-8")

            if not item["lines"]:
                backgrounds += 1
            for class_id in item["classes"]:
                counts[FINAL_CLASSES[class_id]] += 1

        class_counts[split] = dict(counts)
        background_counts[split] = backgrounds

    data_yaml = {
        "path": str(OUTPUT_DIR),
        "train": "train/images",
        "val": "valid/images",
        "test": "test/images",
        "nc": len(FINAL_CLASSES),
        "names": FINAL_CLASSES,
    }
    with open(OUTPUT_DIR / "data.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump(data_yaml, f, sort_keys=False, allow_unicode=True)

    report = {
        "input_zip_files": [p.name for p in zip_paths],
        "final_classes": FINAL_CLASSES,
        "total_unique_images": len(items),
        "split_image_counts": {k: len(v) for k, v in splits.items()},
        "background_images_by_split": background_counts,
        "images_with_class_by_split": class_counts,
        "processing_stats": dict(stats),
        "source_stats": per_source,
        "mapping": AUTO_CLASS_MAP,
        "note": "Class counts count images containing a class, not bounding boxes.",
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "build_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )

    # Also create a readable report.
    lines = [
        "PIPELINE DATASET BUILD REPORT",
        f"Unique images: {len(items)}",
        f"Train: {len(splits['train'])}",
        f"Validation: {len(splits['valid'])}",
        f"Test: {len(splits['test'])}",
        f"Background images: {sum(background_counts.values())}",
        "",
        "Images containing each class by split:",
    ]
    for split, counts in class_counts.items():
        lines.append(f"{split}: {counts}")
    lines += ["", f"Processing stats: {dict(stats)}"]
    (REPORT_DIR / "build_report.txt").write_text("\n".join(lines), encoding="utf-8")

    print("\n========== BUILD COMPLETE ==========")
    print("Output:", OUTPUT_DIR)
    print("Unique images:", len(items))
    print("Split counts:", {k: len(v) for k, v in splits.items()})
    print("Background images:", background_counts)
    print("Class image counts:", class_counts)
    print("Report:", REPORT_DIR / "build_report.txt")


def main():
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    if ZIP_FILES is None:
        zip_paths = sorted(INPUT_DIR.glob("*.zip"))
    else:
        zip_paths = [INPUT_DIR / name for name in ZIP_FILES]

    if len(zip_paths) != 4:
        raise RuntimeError(
            f"Expected exactly 4 ZIP files in {INPUT_DIR}, found {len(zip_paths)}. "
            "Upload all four ZIP files there."
        )

    for p in zip_paths:
        if not p.exists():
            raise FileNotFoundError(p)
        if not zipfile.is_zipfile(p):
            raise RuntimeError(f"Not a valid ZIP archive: {p.name}")

    # Windows can fail to extract Roboflow images with long filenames when the
    # default Temp path is already deep. Use a very short temporary path on C:.
    # The extracted files are temporary and are removed automatically afterward.
    temp_parent = Path("C:/") if Path("C:/").exists() else None
    with tempfile.TemporaryDirectory(prefix="pds_", dir=temp_parent) as tmp:
        work_root = Path(tmp)
        extracted_roots = []

        # Extract once, then inventory or build.
        for idx, zip_path in enumerate(zip_paths, start=1):
            extract_dir = work_root / f"dataset_{idx}"
            extract_dir.mkdir(parents=True, exist_ok=True)
            safe_extract(zip_path, extract_dir)
            extracted_roots.append(extract_dir)

        if not BUILD_DATASET:
            # Inventory from already extracted folders.
            print("\n========== DATASET INVENTORY ==========")
            inventory_rows = []
            all_names = set()
            for zip_path, root in zip(zip_paths, extracted_roots):
                yaml_path = find_yaml(root)
                names = load_names(yaml_path)
                pairs = image_label_pairs(yaml_path.parent)
                all_names.update(names.values())
                row = {
                    "zip": zip_path.name,
                    "yaml": str(yaml_path),
                    "classes": names,
                    "images_found": len(pairs),
                    "labels_found": sum(1 for _, lp in pairs if lp is not None),
                    "missing_labels": sum(1 for _, lp in pairs if lp is None),
                    "empty_labels": sum(1 for _, lp in pairs if lp is not None and lp.exists() and lp.stat().st_size == 0),
                }
                inventory_rows.append(row)
                print(f"\n{zip_path.name}")
                print(f"  images: {row['images_found']}; label files: {row['labels_found']}; missing labels: {row['missing_labels']}; empty labels: {row['empty_labels']}")
                print("  classes:")
                for class_id, name in sorted(names.items()):
                    print(f"    {class_id}: {name}")
            REPORT_DIR.mkdir(parents=True, exist_ok=True)
            (REPORT_DIR / "inventory.json").write_text(
                json.dumps(inventory_rows, indent=2), encoding="utf-8"
            )
            print("\nAll source class names (review these before mapping):")
            for name in sorted(all_names, key=norm_name):
                print(" -", name)
            print("\nInventory report:", REPORT_DIR / "inventory.json")
            print("\nNext: fill AUTO_CLASS_MAP, set BUILD_DATASET = True, and run again.")
        else:
            build_dataset(zip_paths, extracted_roots)

if __name__ == "__main__":
    main()
