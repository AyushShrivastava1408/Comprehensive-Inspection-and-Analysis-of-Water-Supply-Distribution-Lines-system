"""
Water Pipeline Dataset Merger
Combines four Roboflow YOLO datasets into a four-class YOLO object-detection dataset.

Target classes:
0: crack
1: joint_displacement
2: corrosion
3: blockage

Supports YOLO detection labels (class x_center y_center width height) and
YOLO segmentation polygons (class x1 y1 x2 y2 ...). Segmentation polygons
are converted to their enclosing bounding boxes.
"""

from pathlib import Path
from collections import Counter, defaultdict
import hashlib
import json
import random
import re
import shutil
import tempfile
import zipfile

import yaml
from PIL import Image


# --------------------------- USER SETTINGS ---------------------------

BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR
OUTPUT_DIR = BASE_DIR / "Pipeline_Defect_Dataset"
REPORT_DIR = BASE_DIR / "pipeline_dataset_reports"

# Automatically use ZIP files in INPUT_DIR. Exactly four are expected.
ZIP_FILES = None

SEED = 42
TRAIN_RATIO = 0.70
VAL_RATIO = 0.20
TEST_RATIO = 0.10

FINAL_CLASSES = [
    "crack",
    "joint_displacement",
    "corrosion",
    "blockage",
]

# Source class names are normalized before matching (case and separators
# such as spaces, underscores and hyphens are ignored).
# Unlisted source classes are excluded.
AUTO_CLASS_MAP = {
    # Dataset 1: my pipeline
    "Crack": "crack",
    "Corrode": "corrosion",
    "Joint offset": "joint_displacement",
    "Debris": "blockage",
    "Deposit": "blockage",
    "Obstacle": "blockage",
    "Root": "blockage",
    "Utility intrusion": "blockage",

    # Datasets 2 and 3
    "rust": "corrosion",

    # Dataset 4: PipeLine v4
    "CJ": "blockage",       # sediment/deposition
    "CQBG": "blockage",     # visually observed obstruction
    "PL": "crack",          # visually observed pipe rupture/breakage
    "SG": "blockage",       # visually observed root intrusion
    "YWCR": "blockage",     # visually observed foreign-object intrusion
    "ZAW": "blockage",      # visually observed obstacle
}

# Intentionally excluded for now:
# Bucking, Hole, Leak, Infiltration, Standing water, BX, FZ, JG,
# CKTJ, JKCL, SL, ZGAJ, and any other unlisted classes.
#
# Note: CKTJ and JKCL have not been mapped because their precise defect
# meanings were not conclusively established from the supplied examples.

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
NORMALIZED_FINAL_ID = {
    re.sub(r"[^a-z0-9]+", "", name.lower()): i
    for i, name in enumerate(FINAL_CLASSES)
}


# --------------------------- HELPERS ---------------------------------

def norm_name(value):
    """Normalize source names and target names consistently."""
    return re.sub(r"[^a-z0-9]+", "", str(value).strip().lower())


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
    """Extract ZIP contents while preventing path traversal."""
    destination = destination.resolve()
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.infolist():
            target = (destination / member.filename).resolve()
            if target != destination and destination not in target.parents:
                raise ValueError(f"Unsafe path in ZIP: {member.filename}")
        zf.extractall(destination)


def find_yaml(root):
    candidates = list(root.rglob("data.yaml")) + list(root.rglob("data.yml"))
    if not candidates:
        raise FileNotFoundError(f"No data.yaml/data.yml found under {root}")
    return sorted(candidates, key=lambda p: len(p.parts))[0]


def image_label_pairs(dataset_root):
    """Find images and matching labels in Roboflow images/labels folders."""
    pairs = []
    for image_path in dataset_root.rglob("*"):
        if not image_path.is_file() or image_path.suffix.lower() not in IMAGE_EXTS:
            continue
        if any(part.lower() in {"runs", "output", "outputs"} for part in image_path.parts):
            continue

        parts = list(image_path.parts)
        image_idx = next(
            (i for i, part in enumerate(parts) if part.lower() == "images"),
            None,
        )

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
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_yolo_label(label_path, source_names, class_map, stats):
    """
    Parse YOLO detection boxes or segmentation polygons.
    Returns (retained_label_lines, target_classes_present, had_source_annotations).
    """
    retained = []
    classes_present = set()

    if label_path is None:
        return retained, classes_present, False

    try:
        text = label_path.read_text(encoding="utf-8-sig").strip()
    except Exception as exc:
        raise ValueError(f"Cannot read label {label_path}: {exc}") from exc

    if not text:
        return retained, classes_present, False

    for line_no, line in enumerate(text.splitlines(), start=1):
        fields = line.strip().split()
        if not fields:
            continue

        try:
            old_id = int(float(fields[0]))
            values = [float(v) for v in fields[1:]]
        except ValueError as exc:
            raise ValueError(
                f"Invalid numeric annotation in {label_path}, line {line_no}"
            ) from exc

        if old_id not in source_names:
            raise ValueError(
                f"Class ID {old_id} is not present in data.yaml for {label_path}"
            )

        # Standard YOLO detection: x_center, y_center, width, height.
        if len(values) == 4:
            x, y, w, h = values

        # YOLO segmentation: x1, y1, x2, y2, ... (at least 3 points).
        elif len(values) >= 6 and len(values) % 2 == 0:
            xs = values[0::2]
            ys = values[1::2]
            if not all(0.0 <= v <= 1.0 for v in values):
                raise ValueError(
                    f"Polygon coordinate outside [0, 1] in {label_path}, line {line_no}"
                )
            xmin, xmax = min(xs), max(xs)
            ymin, ymax = min(ys), max(ys)
            x = (xmin + xmax) / 2.0
            y = (ymin + ymax) / 2.0
            w = xmax - xmin
            h = ymax - ymin
            stats["segmentation_polygons_converted"] += 1
        else:
            raise ValueError(
                f"Malformed YOLO annotation in {label_path}, line {line_no}: "
                f"expected 4 box values or an even polygon coordinate list; "
                f"received {len(values)} values"
            )

        # Validate normalized YOLO values first.
        if (
            not all(0.0 <= v <= 1.0 for v in [x, y, w, h])
            or w <= 0.0
            or h <= 0.0
        ):
            raise ValueError(
                f"Invalid normalized bounding-box values in {label_path}, line {line_no}"
            )

        # Roboflow exports can occasionally exceed an image boundary by a
        # few millionths because of floating-point rounding.
        xmin = x - w / 2.0
        ymin = y - h / 2.0
        xmax = x + w / 2.0
        ymax = y + h / 2.0
        tolerance = 0.0001

        if (
            xmin < -tolerance
            or ymin < -tolerance
            or xmax > 1.0 + tolerance
            or ymax > 1.0 + tolerance
        ):
            raise ValueError(
                f"Bounding box extends beyond image boundaries in "
                f"{label_path}, line {line_no}: "
                f"xmin={xmin:.9f}, ymin={ymin:.9f}, "
                f"xmax={xmax:.9f}, ymax={ymax:.9f}"
            )

        # Clip only tiny boundary overflows; substantially invalid
        # annotations are still rejected.
        clipped_edges = (
            xmin < 0.0 or ymin < 0.0 or xmax > 1.0 or ymax > 1.0
        )
        xmin = max(0.0, xmin)
        ymin = max(0.0, ymin)
        xmax = min(1.0, xmax)
        ymax = min(1.0, ymax)

        x = (xmin + xmax) / 2.0
        y = (ymin + ymax) / 2.0
        w = xmax - xmin
        h = ymax - ymin

        if w <= 0.0 or h <= 0.0:
            raise ValueError(
                f"Bounding box has zero area after boundary clipping in "
                f"{label_path}, line {line_no}"
            )

        if clipped_edges:
            stats["bbox_boundary_rounding_clipped"] += 1

        coords = [x, y, w, h]

        original_name = source_names[old_id]
        mapped = class_map.get(norm_name(original_name))

        if mapped is None:
            stats["annotations_excluded_unmapped"] += 1
            continue

        mapped_key = norm_name(mapped)
        if mapped_key == "normal":
            continue

        if mapped_key not in NORMALIZED_FINAL_ID:
            raise ValueError(
                f"Mapping for '{original_name}' points to unsupported target '{mapped}'."
            )

        new_id = NORMALIZED_FINAL_ID[mapped_key]
        retained.append(
            f"{new_id} " + " ".join(f"{v:.6f}" for v in coords)
        )
        classes_present.add(new_id)

    return retained, classes_present, True


# --------------------------- DATASET BUILD ----------------------------

def build_dataset(zip_paths, extracted_roots):
    class_map = {norm_name(k): v for k, v in AUTO_CLASS_MAP.items()}
    if not class_map:
        raise ValueError("AUTO_CLASS_MAP is empty.")

    records = {}
    stats = Counter()
    per_source = []

    for zip_path, root in zip(zip_paths, extracted_roots):
        yaml_path = find_yaml(root)
        source_names = load_names(yaml_path)
        pairs = image_label_pairs(yaml_path.parent)
        source_count = Counter()

        print(f"\nProcessing: {zip_path.name}")
        print(f"Images found: {len(pairs)}")

        for image_path, label_path in pairs:
            try:
                with Image.open(image_path) as im:
                    im.verify()
            except Exception:
                stats["corrupt_images_skipped"] += 1
                continue

            if label_path is None:
                stats["images_missing_label_skipped"] += 1
                continue

            mapped_lines, classes_present, had_annotations = parse_yolo_label(
                label_path, source_names, class_map, stats
            )
            source_count["images_seen"] += 1

            # An image with annotations only from excluded classes must not
            # become a false background image.
            if had_annotations and not mapped_lines:
                stats["images_only_excluded_classes_skipped"] += 1
                source_count["images_only_excluded_classes_skipped"] += 1
                continue

            if not mapped_lines:
                source_count["empty_label_background_images"] += 1

            digest = sha256_file(image_path)
            if digest not in records:
                records[digest] = {
                    "image": image_path,
                    "lines": set(mapped_lines),
                    "classes": set(classes_present),
                }
            else:
                records[digest]["lines"].update(mapped_lines)
                records[digest]["classes"].update(classes_present)
                stats["duplicate_images_merged"] += 1

        per_source.append({"zip": zip_path.name, **source_count})

    items = []
    for digest, rec in records.items():
        items.append({
            "hash": digest,
            "image": rec["image"],
            "lines": sorted(rec["lines"]),
            "classes": sorted(rec["classes"]),
        })

    if not items:
        raise RuntimeError("No usable images found. Check ZIP structure and mappings.")

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

    if OUTPUT_DIR.exists():
        raise FileExistsError(
            f"Output folder already exists: {OUTPUT_DIR}\n"
            "Rename it before building again. The script will not delete it."
        )

    for split in splits:
        (OUTPUT_DIR / split / "images").mkdir(parents=True, exist_ok=True)
        (OUTPUT_DIR / split / "labels").mkdir(parents=True, exist_ok=True)

    class_image_counts = {}
    background_counts = {}

    for split, split_items in splits.items():
        counts = Counter()
        backgrounds = 0

        for index, item in enumerate(split_items):
            source_image = item["image"]
            filename = f"{item['hash'][:16]}_{index}{source_image.suffix.lower()}"
            dest_image = OUTPUT_DIR / split / "images" / filename
            dest_label = OUTPUT_DIR / split / "labels" / f"{Path(filename).stem}.txt"

            shutil.copy2(source_image, dest_image)
            label_text = "\n".join(item["lines"])
            dest_label.write_text(
                label_text + ("\n" if label_text else ""),
                encoding="utf-8",
            )

            if not item["lines"]:
                backgrounds += 1
            for class_id in item["classes"]:
                counts[FINAL_CLASSES[class_id]] += 1

        class_image_counts[split] = dict(counts)
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
        "images_containing_each_class_by_split": class_image_counts,
        "processing_stats": dict(stats),
        "source_stats": per_source,
        "mapping": AUTO_CLASS_MAP,
        "note": (
            "Class counts are images containing a class, not object counts. "
            "Segmentation polygons were converted to enclosing detection boxes. "
            "The split is deterministic random and not class-stratified."
        ),
    }

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "build_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )

    report_lines = [
        "PIPELINE DATASET BUILD REPORT",
        f"Unique images: {len(items)}",
        f"Train: {len(splits['train'])}",
        f"Validation: {len(splits['valid'])}",
        f"Test: {len(splits['test'])}",
        f"Background images: {sum(background_counts.values())}",
        f"Segmentation polygons converted: {stats.get('segmentation_polygons_converted', 0)}",
        f"Bounding boxes clipped for tiny boundary rounding: {stats.get('bbox_boundary_rounding_clipped', 0)}",
        f"Unmapped annotations excluded: {stats.get('annotations_excluded_unmapped', 0)}",
        "",
        "Images containing each class by split:",
    ]
    for split, counts in class_image_counts.items():
        report_lines.append(f"{split}: {counts}")
    report_lines.extend(["", f"Processing stats: {dict(stats)}"])
    (REPORT_DIR / "build_report.txt").write_text(
        "\n".join(report_lines), encoding="utf-8"
    )

    print("\n========== BUILD COMPLETE ==========")
    print("Output:", OUTPUT_DIR)
    print("Unique images:", len(items))
    print("Split counts:", {k: len(v) for k, v in splits.items()})
    print("Background images:", background_counts)
    print("Class image counts:", class_image_counts)
    print("Segmentation polygons converted:", stats.get("segmentation_polygons_converted", 0))
    print("Bounding boxes clipped for tiny boundary rounding:", stats.get("bbox_boundary_rounding_clipped", 0))
    print("Unmapped annotations excluded:", stats.get("annotations_excluded_unmapped", 0))
    print("Report:", REPORT_DIR / "build_report.txt")


def main():
    if ZIP_FILES is None:
        zip_paths = sorted(INPUT_DIR.glob("*.zip"))
    else:
        zip_paths = [INPUT_DIR / name for name in ZIP_FILES]

    if len(zip_paths) != 4:
        raise RuntimeError(
            f"Expected exactly 4 ZIP files in {INPUT_DIR}, found {len(zip_paths)}."
        )

    for path in zip_paths:
        if not path.exists():
            raise FileNotFoundError(path)
        if not zipfile.is_zipfile(path):
            raise RuntimeError(f"Not a valid ZIP archive: {path.name}")

    # Use a short Windows temporary path to avoid MAX_PATH extraction issues.
    temp_parent = Path("C:/") if Path("C:/").exists() else None
    with tempfile.TemporaryDirectory(prefix="pds_", dir=temp_parent) as tmp:
        work_root = Path(tmp)
        extracted_roots = []

        for index, zip_path in enumerate(zip_paths, start=1):
            extract_dir = work_root / f"ds{index}"
            extract_dir.mkdir(parents=True, exist_ok=True)
            print(f"Extracting {zip_path.name} ...")
            safe_extract(zip_path, extract_dir)
            extracted_roots.append(extract_dir)

        build_dataset(zip_paths, extracted_roots)


if __name__ == "__main__":
    main()
