from flask import Blueprint, current_app, jsonify, request

from ..errors import ApiError
from ..security import login_required
from ..services import stats

bp = Blueprint("dashboard", __name__)


@bp.get("/dashboard/summary")
@login_required
def summary():
    return jsonify(stats.summary())


@bp.get("/dashboard/defect-stats")
@login_required
def defect_stats():
    """?inspection_id=<id> (optional), ?days=30 (trend window)"""
    try:
        days = min(365, max(1, int(request.args.get("days", 30))))
    except ValueError:
        raise ApiError("days must be an integer")
    return jsonify(stats.defect_stats(request.args.get("inspection_id", type=int), days))


@bp.get("/model/info")
@login_required
def model_info():
    """Model ke baare mein sach: weights hain ya nahi, load hua ya nahi, kaunsi classes."""
    import os
    cfg = current_app.config
    det = current_app.extensions.get("detector")
    return jsonify({
        "weights_file": os.path.basename(cfg["YOLO_WEIGHTS"]),
        "weights_present": os.path.exists(cfg["YOLO_WEIGHTS"]),
        "loaded": det is not None,
        "model_version": det.model_version if det else None,
        "classes": det.class_names if det else None,
        "conf_threshold": cfg["CONF_THRESHOLD"], "imgsz": cfg["YOLO_IMGSZ"],
        "preprocessing": {"clahe": cfg["APPLY_CLAHE"], "gaussian_denoise": cfg["APPLY_DENOISE"],
                          "max_side": cfg["PROCESS_MAX_SIDE"]},
    })
