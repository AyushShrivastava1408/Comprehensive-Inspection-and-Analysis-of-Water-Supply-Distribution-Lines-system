"""Core workflow: image -> preprocessing -> YOLOv8 -> annotated image -> DB."""
import logging
import os
import time
from datetime import datetime, timezone

import cv2

from ..constants import (IMG_ANALYZED, IMG_FAILED, IMG_PENDING, ST_COMPLETED, ST_FAILED,
                         ST_PARTIAL, ST_PROCESSING)
from ..extensions import db
from ..models import Detection, Inspection, InspectionImage
from ..utils import safe_remove
from .annotate import draw_detections
from .detector import get_detector
from .image_io import load_image
from .preprocessing import preprocess_image
from .severity import severity_level, severity_score

log = logging.getLogger(__name__)


def _now():
    return datetime.now(timezone.utc)


def run_analysis(app, inspection_id: int, force: bool = False):
    """Background entry point (ya tests mein inline)."""
    with app.app_context():
        try:
            _analyze(app, inspection_id, force)
        except Exception as exc:  # noqa: BLE001
            log.exception("Analysis of inspection %s failed", inspection_id)
            db.session.rollback()
            insp = db.session.get(Inspection, inspection_id)
            if insp:
                insp.status, insp.error = ST_FAILED, str(exc)[:1000]
                insp.analyzed_at = _now()
                db.session.commit()


def _clear_previous(image: InspectionImage):
    for d in list(image.detections):
        db.session.delete(d)
    safe_remove(image.annotated_path)
    image.annotated_path, image.detection_count = None, 0


def _analyze(app, inspection_id: int, force: bool):
    cfg = app.config
    insp = db.session.get(Inspection, inspection_id)
    if insp is None:
        return
    todo = [i for i in insp.images if force or i.status in (IMG_PENDING, IMG_FAILED)]
    insp.status, insp.error = ST_PROCESSING, None
    insp.analysis_started_at = _now()
    db.session.commit()

    detector = get_detector(app)  # model load fail ho to poora inspection 'failed' (clear error ke saath)
    insp.model_version = detector.model_version
    insp.settings = {
        "apply_clahe": cfg["APPLY_CLAHE"], "apply_denoise": cfg["APPLY_DENOISE"],
        "process_max_side": cfg["PROCESS_MAX_SIDE"], "conf_threshold": cfg["CONF_THRESHOLD"],
        "yolo_imgsz": cfg["YOLO_IMGSZ"],
    }
    db.session.commit()

    for image in todo:
        try:
            _analyze_one(app, detector, insp, image)
        except Exception as exc:  # noqa: BLE001  (ek image kharab ho to baaki chalti rahein)
            log.warning("Image %s failed", image.id, exc_info=True)
            db.session.rollback()
            image = db.session.get(InspectionImage, image.id)
            image.status, image.error = IMG_FAILED, str(exc)[:500]
            db.session.commit()

    db.session.refresh(insp)
    states = [i.status for i in insp.images]
    if all(s == IMG_ANALYZED for s in states):
        insp.status = ST_COMPLETED
    elif any(s == IMG_ANALYZED for s in states):
        insp.status = ST_PARTIAL
    else:
        insp.status = ST_FAILED
        insp.error = "No image could be analyzed"
    insp.analyzed_at = _now()
    db.session.commit()


def _analyze_one(app, detector, insp, image):
    cfg = app.config
    if image.detections or image.annotated_path:
        _clear_previous(image)
    original = load_image(image.original_path)
    h, w = original.shape[:2]
    processed, scale = preprocess_image(original, cfg)

    t0 = time.perf_counter()
    dets = detector.detect(processed)
    infer_ms = (time.perf_counter() - t0) * 1000

    kept = []
    for d in dets:
        # boxes ko ORIGINAL image coordinates mein wapas lao
        d.x1, d.y1, d.x2, d.y2 = [v / scale for v in (d.x1, d.y1, d.x2, d.y2)]
        d.x1, d.x2 = max(0.0, d.x1), min(float(w), d.x2)
        d.y1, d.y2 = max(0.0, d.y1), min(float(h), d.y2)
        if d.x2 <= d.x1 or d.y2 <= d.y1:
            continue
        kept.append(d)

    annotated = draw_detections(original, kept)
    os.makedirs(cfg["ANNOTATED_FOLDER"], exist_ok=True)
    stem = os.path.splitext(image.stored_filename)[0]
    out_path = os.path.join(cfg["ANNOTATED_FOLDER"], f"{stem}_annotated.jpg")
    if not cv2.imwrite(out_path, annotated, [cv2.IMWRITE_JPEG_QUALITY, 92]):
        raise IOError("could not write annotated image")

    for d in kept:
        cov = ((d.x2 - d.x1) * (d.y2 - d.y1)) / float(w * h)
        score = severity_score(d.defect_type, cov, d.confidence)
        db.session.add(Detection(
            inspection_id=insp.id, image_id=image.id, defect_type=d.defect_type, raw_label=d.raw_label,
            confidence=d.confidence, bbox_x1=d.x1, bbox_y1=d.y1, bbox_x2=d.x2, bbox_y2=d.y2,
            bbox_coverage=round(cov, 4), severity_score=score, severity_level=severity_level(score)))

    image.annotated_path = out_path
    image.detection_count = len(kept)
    image.inference_ms = round(infer_ms, 1)
    image.status, image.error, image.analyzed_at = IMG_ANALYZED, None, _now()
    db.session.commit()
