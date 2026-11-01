import csv
import io

from flask import Blueprint, Response, request

from ..constants import ST_COMPLETED, ST_PARTIAL
from ..errors import ApiError
from ..extensions import db
from ..models import Detection, Inspection
from ..security import login_required
from ..services.reports import CSV_COLUMNS, build_pdf, detection_csv_row
from ..utils import parse_date_arg

bp = Blueprint("reports", __name__)


@bp.get("/reports/<int:iid>/pdf")
@login_required
def inspection_pdf(iid):
    insp = db.get_or_404(Inspection, iid)
    if insp.status not in (ST_COMPLETED, ST_PARTIAL):
        raise ApiError("Report is available only after the inspection has been analyzed", 409)
    pdf = build_pdf(insp)
    return Response(pdf, mimetype="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="inspection_{insp.id}_report.pdf"'})


@bp.get("/reports/export/csv")
@login_required
def export_csv():
    """Saari detections CSV mein. Filters: inspection_id, defect_type, from, to, exclude_rejected=true"""
    q = Detection.query
    a = request.args
    if a.get("inspection_id"):
        q = q.filter(Detection.inspection_id == a.get("inspection_id", type=int))
    if a.get("defect_type"):
        q = q.filter(Detection.defect_type.in_(a["defect_type"].split(",")))
    if (d := parse_date_arg("from")):
        q = q.filter(Detection.created_at >= d)
    if (d := parse_date_arg("to", end_of_day=True)):
        q = q.filter(Detection.created_at <= d)
    if str(a.get("exclude_rejected", "")).lower() in ("1", "true", "yes"):
        q = q.filter(Detection.review_status != "rejected")
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(CSV_COLUMNS)
    for d in q.order_by(Detection.id):
        w.writerow(detection_csv_row(d))
    return Response("\ufeff" + buf.getvalue(), mimetype="text/csv", headers={
        "Content-Disposition": 'attachment; filename="detections_export.csv"'})
