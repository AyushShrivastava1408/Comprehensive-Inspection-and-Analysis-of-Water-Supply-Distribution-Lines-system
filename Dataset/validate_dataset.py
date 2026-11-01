
from pathlib import Path
from collections import Counter
from PIL import Image

DATASET = Path("Pipeline_Defect_Dataset")
SPLITS = ["train", "valid", "test"]

class_counts = Counter()
total_images = 0
total_labels = 0
empty_labels = 0
errors = []

for split in SPLITS:
    image_dir = DATASET / split / "images"
    label_dir = DATASET / split / "labels"

    images = [
        p for p in image_dir.iterdir()
        if p.suffix.lower() in {
            ".jpg", ".jpeg", ".png", ".bmp",
            ".tif", ".tiff", ".webp"
        }
    ]

    labels = list(label_dir.glob("*.txt"))

    image_stems = {p.stem for p in images}
    label_stems = {p.stem for p in labels}

    missing_labels = image_stems - label_stems
    extra_labels = label_stems - image_stems

    print(f"\n--- {split.upper()} ---")
    print("Images:", len(images))
    print("Labels:", len(labels))
    print("Missing labels:", len(missing_labels))
    print("Extra labels:", len(extra_labels))

    if missing_labels:
        errors.append(f"{split}: images without labels")

    if extra_labels:
        errors.append(f"{split}: labels without images")

    total_images += len(images)
    total_labels += len(labels)

    for image in images:
        try:
            with Image.open(image) as im:
                im.verify()
        except Exception:
            errors.append(f"Corrupt image: {image.name}")

    for label in labels:
        content = label.read_text(encoding="utf-8").strip()

        if not content:
            empty_labels += 1
            continue

        for line_no, line in enumerate(content.splitlines(), 1):
            values = line.split()

            try:
                class_id = int(values[0])
                coords = [float(v) for v in values[1:]]
            except (ValueError, IndexError):
                errors.append(f"Invalid annotation: {label.name}")
                continue

            if class_id not in range(4):
                errors.append(f"Invalid class ID: {label.name}")
                continue

            if len(coords) != 4:
                errors.append(f"Invalid box format: {label.name}")
                continue

            x, y, w, h = coords

            if (
                not all(0 <= v <= 1 for v in coords)
                or w <= 0 or h <= 0
                or x - w / 2 < -1e-6
                or y - h / 2 < -1e-6
                or x + w / 2 > 1.000001
                or y + h / 2 > 1.000001
            ):
                errors.append(
                    f"Invalid bounding box: {label.name}, line {line_no}"
                )
                continue

            class_counts[class_id] += 1

print("\n========== VALIDATION SUMMARY ==========")
print("Total images:", total_images)
print("Total label files:", total_labels)
print("Empty background labels:", empty_labels)

print("\nObject annotation counts:")
for class_id, name in enumerate([
    "crack",
    "joint_displacement",
    "corrosion",
    "blockage"
]):
    print(f"{class_id} - {name}: {class_counts[class_id]}")

print("\nValidation errors:", len(errors))

for error in errors[:30]:
    print("ERROR:", error)

if not errors:
    print("\nSUCCESS: All dataset checks passed!")
else:
    print("\nVALIDATION FAILED: Review the errors above.")
