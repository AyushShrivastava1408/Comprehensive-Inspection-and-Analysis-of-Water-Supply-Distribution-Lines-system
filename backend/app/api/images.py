import os

from flask import Blueprint, Response, request, send_file

from ..errors import ApiError
from ..extensions import db
from ..models import InspectionImage
from ..security import login_required
from ..services.image_io import encode_preview

bp = Blueprint("images", __name__)


def _serve(path, mimetype):
    if not path or not os.path.exists(path):
        raise ApiError("Image file not available", 404)
    width = request.args.get("w", type=int)  # ?w=300 => thumbnail/preview
    if width:
        width = max(32, min(width, 2000))
        resp = Response(encode_preview(path, width), mimetype="image/jpeg")
    else:
        resp = send_file(path, mimetype=mimetype)
    resp.headers["Cache-Control"] = "private, max-age=300"
    return resp


@bp.get("/images/<int:image_id>/original")
@login_required
def original_image(image_id):
    img = db.get_or_404(InspectionImage, image_id)
    mime = "image/png" if img.original_path.lower().endswith(".png") else "image/jpeg"
    return _serve(img.original_path, mime)


@bp.get("/images/<int:image_id>/annotated")
@login_required
def annotated_image(image_id):
    img = db.get_or_404(InspectionImage, image_id)
    if not img.annotated_path:
        raise ApiError("Image has not been analyzed yet", 404)
    return _serve(img.annotated_path, "image/jpeg")
