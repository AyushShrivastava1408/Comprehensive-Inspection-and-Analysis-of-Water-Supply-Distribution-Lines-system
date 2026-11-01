from datetime import datetime, timezone

from werkzeug.security import check_password_hash, generate_password_hash

from .constants import IMG_PENDING, REVIEW_PENDING, ROLE_OPERATOR, ST_UPLOADED
from .extensions import db


def utcnow():
    return datetime.now(timezone.utc)


def _iso(dt):
    return dt.isoformat() if dt else None


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default=ROLE_OPERATOR)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)

    def set_password(self, raw: str):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw: str) -> bool:
        return check_password_hash(self.password_hash, raw)

    def to_dict(self):
        return {"id": self.id, "username": self.username, "email": self.email,
                "role": self.role, "is_active": self.is_active, "created_at": _iso(self.created_at)}


class Inspection(db.Model):
    """Ek inspection = ek batch of pipeline photographs."""
    __tablename__ = "inspections"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160))
    location = db.Column(db.String(200))  # user ka likha hua text (jaise "Sector 5 main line"); GPS nahi
    notes = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    status = db.Column(db.String(20), nullable=False, default=ST_UPLOADED, index=True)
    error = db.Column(db.Text)
    model_version = db.Column(db.String(80))   # kis model ne analyze kiya (weights name + hash)
    settings = db.Column(db.JSON)              # analysis ke time ki preprocessing/conf settings
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, index=True)
    analysis_started_at = db.Column(db.DateTime(timezone=True))
    analyzed_at = db.Column(db.DateTime(timezone=True))

    creator = db.relationship("User")
    images = db.relationship("InspectionImage", back_populates="inspection",
                             cascade="all, delete-orphan", order_by="InspectionImage.id")
    detections = db.relationship("Detection", back_populates="inspection", cascade="all, delete-orphan")

    def to_dict(self):
        n_images = len(self.images)
        done = sum(1 for i in self.images if i.status != IMG_PENDING)
        return {
            "id": self.id, "title": self.title, "location": self.location, "notes": self.notes,
            "created_by": self.created_by,
            "created_by_username": self.creator.username if self.creator else None,
            "status": self.status, "error": self.error, "model_version": self.model_version,
            "settings": self.settings, "image_count": n_images, "images_processed": done,
            "detection_count": len(self.detections),
            "created_at": _iso(self.created_at),
            "analysis_started_at": _iso(self.analysis_started_at), "analyzed_at": _iso(self.analyzed_at),
        }


class InspectionImage(db.Model):
    __tablename__ = "inspection_images"
    id = db.Column(db.Integer, primary_key=True)
    inspection_id = db.Column(db.Integer, db.ForeignKey("inspections.id"), nullable=False, index=True)
    original_filename = db.Column(db.String(255))   # user ne jo naam diya
    stored_filename = db.Column(db.String(80), nullable=False)  # unique uuid naam
    original_path = db.Column(db.String(500), nullable=False)
    annotated_path = db.Column(db.String(500))
    width = db.Column(db.Integer)
    height = db.Column(db.Integer)
    size_bytes = db.Column(db.Integer)
    blur_score = db.Column(db.Float)          # Laplacian variance (kam = blurry)
    brightness = db.Column(db.Float)          # mean gray 0-255
    quality_warnings = db.Column(db.JSON)     # list of strings
    status = db.Column(db.String(12), nullable=False, default=IMG_PENDING, index=True)
    error = db.Column(db.Text)
    detection_count = db.Column(db.Integer, default=0)
    inference_ms = db.Column(db.Float)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)
    analyzed_at = db.Column(db.DateTime(timezone=True))

    inspection = db.relationship("Inspection", back_populates="images")
    detections = db.relationship("Detection", back_populates="image", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id, "inspection_id": self.inspection_id,
            "original_filename": self.original_filename, "stored_filename": self.stored_filename,
            "width": self.width, "height": self.height, "size_bytes": self.size_bytes,
            "blur_score": self.blur_score, "brightness": self.brightness,
            "quality_warnings": self.quality_warnings or [],
            "status": self.status, "error": self.error, "detection_count": self.detection_count,
            "inference_ms": self.inference_ms,
            "original_url": f"/api/images/{self.id}/original",
            "annotated_url": f"/api/images/{self.id}/annotated" if self.annotated_path else None,
            "created_at": _iso(self.created_at), "analyzed_at": _iso(self.analyzed_at),
        }


class Detection(db.Model):
    __tablename__ = "detections"
    id = db.Column(db.Integer, primary_key=True)
    inspection_id = db.Column(db.Integer, db.ForeignKey("inspections.id"), nullable=False, index=True)
    image_id = db.Column(db.Integer, db.ForeignKey("inspection_images.id"), nullable=False, index=True)
    defect_type = db.Column(db.String(40), nullable=False, index=True)  # model ki class (normalized)
    raw_label = db.Column(db.String(60))                                # model ka asli label
    confidence = db.Column(db.Float, nullable=False)                    # model ka asli score
    # bbox ORIGINAL image ke pixel coordinates mein
    bbox_x1 = db.Column(db.Float, nullable=False)
    bbox_y1 = db.Column(db.Float, nullable=False)
    bbox_x2 = db.Column(db.Float, nullable=False)
    bbox_y2 = db.Column(db.Float, nullable=False)
    bbox_coverage = db.Column(db.Float)       # bbox area / image area
    severity_score = db.Column(db.Float)      # heuristic (class + coverage + confidence); normal ke liye None
    severity_level = db.Column(db.String(10), index=True)
    review_status = db.Column(db.String(12), nullable=False, default=REVIEW_PENDING, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, index=True)

    inspection = db.relationship("Inspection", back_populates="detections")
    image = db.relationship("InspectionImage", back_populates="detections")
    verifications = db.relationship("Verification", back_populates="detection",
                                    cascade="all, delete-orphan", order_by="Verification.id")

    def to_dict(self, with_verifications=False):
        d = {
            "id": self.id, "inspection_id": self.inspection_id, "image_id": self.image_id,
            "defect_type": self.defect_type, "raw_label": self.raw_label,
            "confidence": round(self.confidence, 4),
            "bbox": {"x1": self.bbox_x1, "y1": self.bbox_y1, "x2": self.bbox_x2, "y2": self.bbox_y2},
            "bbox_coverage": self.bbox_coverage,
            "severity_score": self.severity_score, "severity_level": self.severity_level,
            "review_status": self.review_status,
            "image_original_url": f"/api/images/{self.image_id}/original",
            "image_annotated_url": f"/api/images/{self.image_id}/annotated",
            "created_at": _iso(self.created_at),
        }
        if with_verifications:
            d["verifications"] = [v.to_dict() for v in self.verifications]
        return d


class Verification(db.Model):
    """Reviewer ka record: detection sahi (confirmed) hai ya false positive (rejected)."""
    __tablename__ = "verifications"
    id = db.Column(db.Integer, primary_key=True)
    detection_id = db.Column(db.Integer, db.ForeignKey("detections.id"), nullable=False, index=True)
    reviewer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    status = db.Column(db.String(12), nullable=False)
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)

    detection = db.relationship("Detection", back_populates="verifications")
    reviewer = db.relationship("User")

    def to_dict(self):
        return {"id": self.id, "detection_id": self.detection_id, "reviewer_id": self.reviewer_id,
                "reviewer": self.reviewer.username if self.reviewer else None,
                "status": self.status, "comment": self.comment, "created_at": _iso(self.created_at)}
