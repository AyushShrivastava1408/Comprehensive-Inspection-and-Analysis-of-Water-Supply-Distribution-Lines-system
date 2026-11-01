from flask import Blueprint, jsonify

from ..constants import REVIEW_REJECTED, VERIFY_STATES
from ..errors import ApiError
from ..extensions import db
from ..models import Detection, Verification
from ..security import current_user, login_required, roles_required
from ..utils import json_body

bp = Blueprint("detections", __name__)


@bp.get("/detections/<int:did>")
@login_required
def get_detection(did):
    return jsonify(db.get_or_404(Detection, did).to_dict(with_verifications=True))


@bp.post("/detections/<int:did>/verify")
@roles_required("engineer", "admin")
def verify_detection(did):
    """Reviewer detection ko confirm ya reject (false positive) karta hai. Har action ka record bachta hai."""
    d = db.get_or_404(Detection, did)
    data = json_body()
    status = data.get("status")
    if status not in VERIFY_STATES:
        raise ApiError(f"status must be one of {sorted(VERIFY_STATES)}")
    comment = (str(data["comment"]).strip() if data.get("comment") else None)
    if status == REVIEW_REJECTED and not comment:
        raise ApiError("A comment is required when rejecting a detection")
    db.session.add(Verification(detection=d, reviewer_id=current_user().id, status=status, comment=comment))
    d.review_status = status
    db.session.commit()
    return jsonify(d.to_dict(with_verifications=True))
