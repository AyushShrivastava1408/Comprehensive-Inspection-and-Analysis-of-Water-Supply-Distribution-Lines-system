import os

from flask import Blueprint, current_app, jsonify, request

from ..constants import ST_PROCESSING, ST_UPLOADED, IMG_PENDING, IMG_FAILED
from ..errors import ApiError
from ..extensions import db
from ..models import Detection, Inspection, InspectionImage
from ..security import current_user, login_required, roles_required
from ..services.analysis import run_analysis
from ..services.image_io import ImageValidationError, save_original, validate_image
from ..utils import paginate_args, paginated, parse_date_arg, safe_remove

bp = Blueprint("inspections", __name__)


def _truthy(v):
    return str(v).lower() in ("1", "true", "yes")


@bp.post("/inspections/upload")
@roles_required("operator", "engineer", "admin")
def upload_images():
    """multipart/form-data:
         images      : 1 ya zyada files (field name 'images' repeat karo; single ke liye 'image' bhi chalega)
         title, location, notes : optional text
         inspection_id : optional - maujooda inspection mein aur images jodne ke liye
    Valid images save hoti hain; invalid ki list 'rejected' mein aati hai. Koi bhi valid na ho to 400."""
    cfg = current_app.config
    files = request.files.getlist("images") + request.files.getlist("image")
    files = [f for f in files if f and f.filename]
    if not files:
        raise ApiError("No images received. Send files in the 'images' field (JPG/JPEG/PNG).")
    if len(files) > cfg["MAX_FILES_PER_UPLOAD"]:
        raise ApiError(f"Too many files; maximum {cfg['MAX_FILES_PER_UPLOAD']} per upload")

    inspection = None
    if request.form.get("inspection_id"):
        try:
            inspection = db.session.get(Inspection, int(request.form["inspection_id"]))
        except ValueError:
            raise ApiError("inspection_id must be an integer")
        if inspection is None:
            raise ApiError("Inspection not found", 404)
        if inspection.status == ST_PROCESSING:
            raise ApiError("Inspection is being analyzed; wait until it finishes", 409)

    valid, rejected = [], []
    for f in files:
        try:
            valid.append((f.filename, validate_image(f.filename, f.read(), cfg)))
        except ImageValidationError as e:
            rejected.append({"filename": f.filename, "reason": str(e)})
    if not valid:
        raise ApiError("No valid images in upload", 400, details=rejected)

    saved_paths = []
    try:
        if inspection is None:
            inspection = Inspection(
                title=(request.form.get("title") or "").strip()[:160] or None,
                location=(request.form.get("location") or "").strip()[:200] or None,
                notes=(request.form.get("notes") or "").strip() or None,
                created_by=current_user().id, status=ST_UPLOADED)
            db.session.add(inspection)
        else:
            inspection.status = ST_UPLOADED  # nayi pending images aayi hain
        new_images = []
        for name, v in valid:
            stored, path = save_original(v, cfg["ORIGINAL_FOLDER"])
            saved_paths.append(path)
            img = InspectionImage(
                inspection=inspection, original_filename=os.path.basename(name)[:255],
                stored_filename=stored, original_path=path, width=v.width, height=v.height,
                size_bytes=len(v.data), blur_score=v.blur_score, brightness=v.brightness,
                quality_warnings=v.warnings)
            db.session.add(img)
            new_images.append(img)
        db.session.commit()
    except Exception:
        db.session.rollback()
        for p in saved_paths:
            safe_remove(p)
        raise
    return jsonify({"inspection": inspection.to_dict(),
                    "images": [i.to_dict() for i in new_images],
                    "rejected": rejected}), 201


@bp.post("/inspections/<int:iid>/analyze")
@roles_required("operator", "engineer", "admin")
def analyze_inspection(iid):
    """OpenCV preprocessing + YOLOv8 chalata hai. Background mein chalta hai: 202 milta hai,
    phir GET /api/inspections/<id> se status poll karo (processing -> completed/partial/failed).
    Default mein sirf pending/failed images; ?force=true se sabko dobara."""
    insp = db.get_or_404(Inspection, iid)
    cfg = current_app.config
    force = _truthy(request.args.get("force", "false"))
    if insp.status == ST_PROCESSING:
        raise ApiError("Analysis already running for this inspection", 409)
    if not insp.images:
        raise ApiError("Inspection has no images", 409)
    todo = [i for i in insp.images if force or i.status in (IMG_PENDING, IMG_FAILED)]
    if not todo:
        raise ApiError("Nothing to analyze: all images already analyzed (use ?force=true to re-run)", 409)
    if "detector" not in current_app.extensions and not os.path.exists(cfg["YOLO_WEIGHTS"]):
        raise ApiError("Model weights not found. Place trained best.pt at "
                       f"'{cfg['YOLO_WEIGHTS']}' (or set YOLO_WEIGHTS).", 503)

    insp.status, insp.error = ST_PROCESSING, None
    db.session.commit()
    app = current_app._get_current_object()
    if cfg["RUN_JOBS_INLINE"]:
        run_analysis(app, insp.id, force)
        db.session.refresh(insp)
        return jsonify(insp.to_dict()), 200
    app.extensions["executor"].submit(run_analysis, app, insp.id, force)
    return jsonify(insp.to_dict()), 202


@bp.get("/inspections")
@login_required
def list_inspections():
    """Inspection history. Filters: status, q (title/location), created_by, from, to."""
    q = Inspection.query
    a = request.args
    if a.get("status"):
        q = q.filter(Inspection.status.in_(a["status"].split(",")))
    if a.get("q"):
        like = f"%{a['q'].strip()}%"
        q = q.filter(Inspection.title.ilike(like) | Inspection.location.ilike(like))
    if a.get("created_by"):
        q = q.filter(Inspection.created_by == a.get("created_by", type=int))
    if (d := parse_date_arg("from")):
        q = q.filter(Inspection.created_at >= d)
    if (d := parse_date_arg("to", end_of_day=True)):
        q = q.filter(Inspection.created_at <= d)
    q = q.order_by(Inspection.id.asc() if a.get("order") == "asc" else Inspection.id.desc())
    page, per = paginate_args()
    return jsonify(paginated(q, page, per, lambda i: i.to_dict()))


@bp.get("/inspections/<int:iid>")
@login_required
def get_inspection(iid):
    return jsonify(db.get_or_404(Inspection, iid).to_dict())


@bp.get("/inspections/<int:iid>/images")
@login_required
def list_images(iid):
    insp = db.get_or_404(Inspection, iid)
    return jsonify({"items": [i.to_dict() for i in insp.images], "total": len(insp.images)})


@bp.get("/inspections/<int:iid>/detections")
@login_required
def list_detections(iid):
    db.get_or_404(Inspection, iid)
    q = Detection.query.filter_by(inspection_id=iid)
    a = request.args
    if a.get("defect_type"):
        q = q.filter(Detection.defect_type.in_(a["defect_type"].split(",")))
    if a.get("severity"):
        q = q.filter(Detection.severity_level.in_(a["severity"].split(",")))
    if a.get("review_status"):
        q = q.filter(Detection.review_status == a["review_status"])
    if a.get("image_id"):
        q = q.filter(Detection.image_id == a.get("image_id", type=int))
    if a.get("min_confidence"):
        try:
            q = q.filter(Detection.confidence >= float(a["min_confidence"]))
        except ValueError:
            raise ApiError("min_confidence must be a number")
    q = q.order_by(Detection.image_id, Detection.confidence.desc())
    page, per = paginate_args(default_per_page=100, max_per_page=500)
    return jsonify(paginated(q, page, per, lambda d: d.to_dict()))


@bp.delete("/inspections/<int:iid>")
@roles_required("admin")
def delete_inspection(iid):
    insp = db.get_or_404(Inspection, iid)
    if insp.status == ST_PROCESSING:
        raise ApiError("Inspection is being analyzed", 409)
    for img in insp.images:
        safe_remove(img.original_path)
        safe_remove(img.annotated_path)
    db.session.delete(insp)
    db.session.commit()
    return "", 204
