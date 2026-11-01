"""Image preprocessing: resize (sirf bahut badi image), CLAHE, Gaussian denoise.
(Video stabilization / optical flow yahan use nahi hota - app/future/stabilizer.py dekho.)"""
from typing import Tuple

import cv2
import numpy as np


def resize_max_side(img: np.ndarray, max_side: int) -> Tuple[np.ndarray, float]:
    """Badi image ko downscale karta hai. (image, scale) return; scale = processed/original."""
    h, w = img.shape[:2]
    longest = max(h, w)
    if max_side <= 0 or longest <= max_side:
        return img, 1.0
    scale = max_side / float(longest)
    out = cv2.resize(img, (int(round(w * scale)), int(round(h * scale))), interpolation=cv2.INTER_AREA)
    return out, scale


def apply_clahe(img: np.ndarray, clip_limit=2.0, tile=(8, 8)) -> np.ndarray:
    """Sirf brightness (L channel) pe CLAHE, taaki colors kharab na ho."""
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    l = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile).apply(l)
    return cv2.cvtColor(cv2.merge((l, a, b)), cv2.COLOR_LAB2BGR)


def denoise(img: np.ndarray, ksize=5) -> np.ndarray:
    return cv2.GaussianBlur(img, (ksize, ksize), 0)


def preprocess_image(img: np.ndarray, cfg) -> Tuple[np.ndarray, float]:
    """Returns (processed_image, scale). Detection boxes ko original coords mein laane ke liye 1/scale lagana."""
    out, scale = resize_max_side(img, cfg["PROCESS_MAX_SIDE"])
    if cfg["APPLY_CLAHE"]:
        out = apply_clahe(out)
    if cfg["APPLY_DENOISE"]:
        out = denoise(out)
    return out, scale
