"""Image upload validation + quality checks + preview helpers."""
import os
import uuid
from dataclasses import dataclass, field
from typing import List, Optional

import cv2
import numpy as np

JPEG_SIG = b"\xff\xd8\xff"
PNG_SIG = b"\x89PNG\r\n\x1a\n"


class ImageValidationError(ValueError):
    pass


@dataclass
class ValidatedImage:
    data: bytes
    ext: str                  # asli format (content se), 'jpg' ya 'png'
    width: int
    height: int
    blur_score: float
    brightness: float
    warnings: List[str] = field(default_factory=list)


def detect_format(data: bytes) -> Optional[str]:
    if data.startswith(JPEG_SIG):
        return "jpg"
    if data.startswith(PNG_SIG):
        return "png"
    return None


def assess_quality(img: np.ndarray, cfg) -> dict:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    bright = float(gray.mean())
    warnings = []
    if blur < cfg["BLUR_THRESHOLD"]:
        warnings.append("blurry")
    if bright < cfg["DARK_THRESHOLD"]:
        warnings.append("too_dark")
    if bright > cfg["BRIGHT_THRESHOLD"]:
        warnings.append("too_bright")
    return {"blur_score": round(blur, 2), "brightness": round(bright, 2), "warnings": warnings}


def validate_image(filename: str, data: bytes, cfg) -> ValidatedImage:
    """Extension + file signature + real decode + size + resolution check.
    Raises ImageValidationError (reason user ko dikhane layak)."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in cfg["ALLOWED_IMAGE_EXT"]:
        raise ImageValidationError(f"unsupported file type '.{ext}' (allowed: JPG, JPEG, PNG)")
    if not data:
        raise ImageValidationError("file is empty")
    if len(data) > cfg["MAX_IMAGE_MB"] * 1024 * 1024:
        raise ImageValidationError(f"file larger than {cfg['MAX_IMAGE_MB']} MB")
    real = detect_format(data)
    if real is None:
        raise ImageValidationError("file content is not a valid JPEG/PNG image")
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ImageValidationError("image is corrupt and could not be decoded")
    h, w = img.shape[:2]
    if min(h, w) < cfg["MIN_IMAGE_SIDE"]:
        raise ImageValidationError(f"image too small ({w}x{h}); minimum side is {cfg['MIN_IMAGE_SIDE']} px")
    q = assess_quality(img, cfg)
    return ValidatedImage(data, real, w, h, q["blur_score"], q["brightness"], q["warnings"])


def save_original(v: ValidatedImage, folder: str):
    """Unique naam se save. (stored_filename, full_path) return."""
    os.makedirs(folder, exist_ok=True)
    name = f"{uuid.uuid4().hex}.{v.ext}"
    path = os.path.join(folder, name)
    with open(path, "wb") as f:
        f.write(v.data)
    return name, path


def load_image(path: str) -> np.ndarray:
    img = cv2.imread(path, cv2.IMREAD_COLOR)
    if img is None:
        raise IOError(f"could not read image: {os.path.basename(path)}")
    return img


def encode_preview(path: str, max_width: Optional[int], fmt: str = "jpg"):
    """Preview/thumbnail bytes. max_width None ho to original file bhejo (caller handle kare)."""
    img = load_image(path)
    h, w = img.shape[:2]
    if max_width and w > max_width:
        img = cv2.resize(img, (max_width, int(h * max_width / w)), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not ok:
        raise IOError("could not encode preview")
    return buf.tobytes()
