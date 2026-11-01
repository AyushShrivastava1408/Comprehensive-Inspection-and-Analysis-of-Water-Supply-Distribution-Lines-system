"""YOLOv8 detector. Sirf REAL model - koi fake/mock result app ke andar nahi hai.
(Tests apni mock detector tests/ folder se inject karte hain.)"""
import hashlib
import logging
import os
import threading
from dataclasses import dataclass
from typing import List

import numpy as np

from ..constants import CLASS_ALIASES

log = logging.getLogger(__name__)


@dataclass
class Detection:
    defect_type: str   # normalized class
    raw_label: str     # model ka asli label
    confidence: float
    x1: float
    y1: float
    x2: float
    y2: float


def normalize_label(label: str) -> str:
    key = label.strip().lower().replace("-", "_")
    return CLASS_ALIASES.get(key, CLASS_ALIASES.get(key.replace("_", " "), key))


class BaseDetector:
    model_version = "unknown"
    class_names: List[str] = []

    def detect(self, image: np.ndarray) -> List[Detection]:
        raise NotImplementedError


class YoloDetector(BaseDetector):
    def __init__(self, weights: str, conf: float = 0.25, device=None, imgsz: int = 640):
        if not os.path.exists(weights):
            raise FileNotFoundError(
                f"YOLO weights not found at '{weights}'. Trained best.pt ko models/ mein rakho "
                f"ya YOLO_WEIGHTS env set karo.")
        from ultralytics import YOLO  # lazy import (heavy)

        self.model = YOLO(weights)
        self.conf, self.device, self.imgsz = conf, device, imgsz
        names = self.model.names  # {id: label}
        self.class_names = [normalize_label(names[i]) for i in sorted(names)]
        self.model_version = self._version(weights)
        log.info("YOLO loaded: %s classes=%s", self.model_version, self.class_names)

    @staticmethod
    def _version(path: str) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return f"{os.path.basename(path)}@{h.hexdigest()[:8]}"

    def detect(self, image: np.ndarray) -> List[Detection]:
        res = self.model.predict(image, conf=self.conf, imgsz=self.imgsz,
                                 device=self.device, verbose=False)[0]
        out = []
        for box in res.boxes:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            raw = res.names[int(box.cls[0])]
            out.append(Detection(normalize_label(raw), raw, float(box.conf[0]), x1, y1, x2, y2))
        return out


_lock = threading.Lock()


def get_detector(app) -> BaseDetector:
    """Model ek baar load hota hai aur reuse hota hai (thread-safe)."""
    with _lock:
        det = app.extensions.get("detector")
        if det is None:
            cfg = app.config
            det = YoloDetector(cfg["YOLO_WEIGHTS"], cfg["CONF_THRESHOLD"], cfg["YOLO_DEVICE"], cfg["YOLO_IMGSZ"])
            app.extensions["detector"] = det
        return det
