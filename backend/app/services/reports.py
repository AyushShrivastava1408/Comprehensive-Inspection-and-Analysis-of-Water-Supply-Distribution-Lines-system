"""PDF inspection report (reportlab) + CSV export rows."""
import io
import os
from datetime import datetime, timezone

import cv2
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer,
                                Table, TableStyle)

from ..constants import NON_DEFECT_CLASSES, REVIEW_REJECTED

CSV_COLUMNS = ["detection_id", "inspection_id", "inspection_title", "image_id", "image_filename",
               "defect_type", "confidence", "bbox_x1", "bbox_y1", "bbox_x2", "bbox_y2",
               "severity_level", "severity_score", "review_status", "model_version", "detected_at"]


def csv_safe(v):
    """Spreadsheet formula injection se bachao (=,+,-,@ se shuru hone wale text)."""
    if isinstance(v, str) and v[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + v
    return v


def detection_csv_row(d):
    insp = d.inspection
    return [d.id, d.inspection_id, csv_safe(insp.title or ""), d.image_id,
            csv_safe(d.image.original_filename or ""), d.defect_type, round(d.confidence, 4),
            round(d.bbox_x1, 1), round(d.bbox_y1, 1), round(d.bbox_x2, 1), round(d.bbox_y2, 1),
            d.severity_level or "", d.severity_score if d.severity_score is not None else "",
            d.review_status, insp.model_version or "", d.created_at.isoformat() if d.created_at else ""]


def _jpeg_for_pdf(path, max_side=1100):
    img = cv2.imread(path)
    if img is None:
        return None
    h, w = img.shape[:2]
    s = max_side / max(h, w)
    if s < 1:
        img = cv2.resize(img, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return io.BytesIO(buf.tobytes()) if ok else None


def _fit(buf, max_w, max_h):
    from PIL import Image as PILImage  # reportlab ke saath aata hai
    w, h = PILImage.open(buf).size
    buf.seek(0)
    s = min(max_w / w, max_h / h)
    return Image(buf, width=w * s, height=h * s)


def build_pdf(inspection) -> bytes:
    out = io.BytesIO()
    doc = SimpleDocTemplate(out, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm,
                            topMargin=15 * mm, bottomMargin=15 * mm,
                            title=f"Inspection Report #{inspection.id}")
    ss = getSampleStyleSheet()
    small = ParagraphStyle("small", parent=ss["Normal"], fontSize=8, leading=10)
    story = [Paragraph("Pipeline Inspection Report", ss["Title"]),
             Paragraph(f"Inspection #{inspection.id}", ss["Heading2"])]

    def esc(t):
        return (str(t) if t is not None else "-").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    info = [
        ["Title", esc(inspection.title)], ["Location", esc(inspection.location)],
        ["Created by", esc(inspection.creator.username if inspection.creator else None)],
        ["Created at", esc(inspection.created_at.strftime("%Y-%m-%d %H:%M UTC") if inspection.created_at else None)],
        ["Analyzed at", esc(inspection.analyzed_at.strftime("%Y-%m-%d %H:%M UTC") if inspection.analyzed_at else None)],
        ["Status", esc(inspection.status)], ["Model version", esc(inspection.model_version)],
        ["Settings", esc(inspection.settings)], ["Notes", esc(inspection.notes)],
    ]
    t = Table([[Paragraph(f"<b>{a}</b>", small), Paragraph(b, small)] for a, b in info],
              colWidths=[30 * mm, 150 * mm])
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.3, colors.grey), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story += [t, Spacer(1, 6 * mm)]

    live = [d for d in inspection.detections
            if d.defect_type not in NON_DEFECT_CLASSES and d.review_status != REVIEW_REJECTED]
    by_class = {}
    for d in live:
        by_class[d.defect_type] = by_class.get(d.defect_type, 0) + 1
    story.append(Paragraph("Summary", ss["Heading3"]))
    summary = [["Images uploaded", len(inspection.images)],
               ["Images analyzed", sum(1 for i in inspection.images if i.status == "analyzed")],
               ["Defects detected", len(live)]] + [[f"  {k}", v] for k, v in sorted(by_class.items())]
    st = Table(summary, colWidths=[60 * mm, 30 * mm])
    st.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.3, colors.grey)]))
    story += [st, Spacer(1, 4 * mm)]
    story.append(Paragraph("AI output is decision support. Detections must be visually verified by "
                           "qualified personnel before any repair or excavation decision.", small))

    for img in inspection.images:
        story.append(PageBreak())
        story.append(Paragraph(f"Image {img.id}: {esc(img.original_filename)}", ss["Heading3"]))
        meta = f"{img.width}x{img.height}px | status: {img.status} | detections: {img.detection_count}"
        if img.quality_warnings:
            meta += f" | quality warnings: {', '.join(img.quality_warnings)}"
        story.append(Paragraph(esc(meta), small))
        path = img.annotated_path if img.annotated_path and os.path.exists(img.annotated_path) else img.original_path
        buf = _jpeg_for_pdf(path) if path and os.path.exists(path) else None
        if buf:
            story.append(Spacer(1, 2 * mm))
            story.append(_fit(buf, 175 * mm, 120 * mm))
        if img.error:
            story.append(Paragraph(f"Error: {esc(img.error)}", small))
        rows = [["#", "Class", "Confidence", "BBox (x1,y1,x2,y2)", "Severity", "Review"]]
        for n, d in enumerate(sorted(img.detections, key=lambda x: -x.confidence), 1):
            rows.append([n, d.defect_type, f"{d.confidence:.2f}",
                         f"{d.bbox_x1:.0f},{d.bbox_y1:.0f},{d.bbox_x2:.0f},{d.bbox_y2:.0f}",
                         d.severity_level or "-", d.review_status])
        if len(rows) == 1:
            story.append(Paragraph("No detections in this image.", small))
        else:
            dt = Table(rows, repeatRows=1, colWidths=[8 * mm, 38 * mm, 24 * mm, 56 * mm, 24 * mm, 26 * mm])
            dt.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
                                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                                    ("FONTSIZE", (0, 0), (-1, -1), 8)]))
            story += [Spacer(1, 2 * mm), dt]

    story += [Spacer(1, 6 * mm),
              Paragraph(f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}", small)]
    doc.build(story)
    return out.getvalue()
