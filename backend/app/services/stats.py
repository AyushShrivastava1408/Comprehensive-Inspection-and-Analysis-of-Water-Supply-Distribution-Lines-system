"""Saari statistics DATABASE records se. Kuch bhi hardcoded/fake nahi."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import func

from ..constants import (DEFECT_TYPES, IMG_ANALYZED, NON_DEFECT_CLASSES, REVIEW_REJECTED,
                         SEVERITY_ORDER)
from ..extensions import db
from ..models import Detection, Inspection, InspectionImage


def _defect_filter(inspection_id=None):
    """Real defects = 'normal' nahi + reviewer ne reject nahi kiya."""
    f = [Detection.defect_type.notin_(NON_DEFECT_CLASSES), Detection.review_status != REVIEW_REJECTED]
    if inspection_id:
        f.append(Detection.inspection_id == inspection_id)
    return f


def summary():
    total_insp = db.session.query(func.count(Inspection.id)).scalar()
    by_status = dict(db.session.query(Inspection.status, func.count()).group_by(Inspection.status).all())
    total_images = db.session.query(func.count(InspectionImage.id)).scalar()
    analyzed = db.session.query(func.count(InspectionImage.id)).filter(
        InspectionImage.status == IMG_ANALYZED).scalar()
    defects = db.session.query(func.count(Detection.id)).filter(*_defect_filter()).scalar()
    rejected = db.session.query(func.count(Detection.id)).filter(
        Detection.review_status == REVIEW_REJECTED).scalar()
    confirmed = db.session.query(func.count(Detection.id)).filter(
        Detection.review_status == "confirmed").scalar()
    imgs_with_defects = db.session.query(func.count(func.distinct(Detection.image_id))).filter(
        *_defect_filter()).scalar()
    avg_conf = db.session.query(func.avg(Detection.confidence)).filter(*_defect_filter()).scalar()
    last = db.session.query(func.max(Inspection.analyzed_at)).scalar()
    recent = Inspection.query.order_by(Inspection.id.desc()).limit(5).all()
    return {
        "total_inspections": total_insp,
        "inspections_by_status": by_status,
        "total_images": total_images,
        "total_images_analyzed": analyzed,
        "images_with_defects": imgs_with_defects,
        "total_defects_detected": defects,
        "defects_confirmed_by_reviewers": confirmed,
        "detections_rejected_by_reviewers": rejected,
        "average_confidence": round(avg_conf, 4) if avg_conf is not None else None,
        "last_analysis_at": last.isoformat() if last else None,
        "recent_inspections": [i.to_dict() for i in recent],
    }


def defect_stats(inspection_id=None, days=30):
    f = _defect_filter(inspection_id)
    rows = db.session.query(Detection.defect_type, func.count(), func.avg(Detection.confidence),
                            func.max(Detection.confidence)).filter(*f).group_by(Detection.defect_type).all()
    found = {r[0]: r for r in rows}
    total = sum(r[1] for r in rows)
    classes = list(DEFECT_TYPES) + sorted(k for k in found if k not in DEFECT_TYPES)
    class_stats = []
    for c in classes:
        r = found.get(c)
        count = r[1] if r else 0
        class_stats.append({
            "defect_type": c, "count": count,
            "percentage": round(100 * count / total, 1) if total else 0.0,
            "avg_confidence": round(r[2], 4) if r else None,
            "max_confidence": round(r[3], 4) if r else None,
        })
    sev = dict(db.session.query(Detection.severity_level, func.count()).filter(*f)
               .group_by(Detection.severity_level).all())
    since = datetime.now(timezone.utc) - timedelta(days=days)
    trend_rows = db.session.query(func.date(Detection.created_at), func.count()).filter(
        *f, Detection.created_at >= since).group_by(func.date(Detection.created_at)).order_by(
        func.date(Detection.created_at)).all()
    return {
        "inspection_id": inspection_id, "total_defects": total,
        "by_class": class_stats,
        "by_severity": {k: sev.get(k, 0) for k in SEVERITY_ORDER},
        "daily_trend": [{"date": str(d), "count": c} for d, c in trend_rows],
        "trend_days": days,
    }
