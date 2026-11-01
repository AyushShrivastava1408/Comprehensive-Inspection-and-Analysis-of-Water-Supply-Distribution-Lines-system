import csv
import io
import shutil
import subprocess
from datetime import datetime, timedelta, timezone

import pytest

from conftest import img_file


def test_empty_database_has_no_fabricated_data(client, headers):
    s = client.get("/api/dashboard/summary", headers=headers["mgr"]).json
    assert s["total_inspections"] == 0 and s["total_images"] == 0 and s["total_defects_detected"] == 0
    assert s["average_confidence"] is None and s["last_analysis_at"] is None and s["recent_inspections"] == []
    st = client.get("/api/dashboard/defect-stats", headers=headers["mgr"]).json
    assert st["total_defects"] == 0 and st["daily_trend"] == []
    assert [c["defect_type"] for c in st["by_class"]] == ["crack", "corrosion", "blockage", "joint_displacement"]
    assert all(c["count"] == 0 and c["avg_confidence"] is None for c in st["by_class"])


def test_stats_match_database_records(client, headers, analyzed):
    dets = client.get(f"/api/inspections/{analyzed}/detections", headers=headers["op"]).json["items"]
    s = client.get("/api/dashboard/summary", headers=headers["mgr"]).json
    assert s["total_inspections"] == 1 and s["total_images"] == 2 and s["total_images_analyzed"] == 2
    assert s["total_defects_detected"] == len(dets) == 4 and s["images_with_defects"] == 2
    assert s["average_confidence"] == pytest.approx(sum(d["confidence"] for d in dets) / len(dets), abs=1e-3)
    assert s["inspections_by_status"] == {"completed": 1}
    assert s["recent_inspections"][0]["id"] == analyzed

    st = client.get("/api/dashboard/defect-stats", headers=headers["mgr"]).json
    by = {c["defect_type"]: c for c in st["by_class"]}
    assert by["crack"]["count"] == sum(d["defect_type"] == "crack" for d in dets) == 3
    assert by["corrosion"]["count"] == 1 and by["blockage"]["count"] == 0
    assert by["crack"]["percentage"] == 75.0
    assert by["crack"]["max_confidence"] == 0.9
    assert sum(st["by_severity"].values()) == 4
    assert st["daily_trend"][0]["count"] == 4
    one = client.get(f"/api/dashboard/defect-stats?inspection_id={analyzed}", headers=headers["mgr"]).json
    assert one["total_defects"] == 4
    assert client.get("/api/dashboard/defect-stats?inspection_id=999", headers=headers["mgr"]).json["total_defects"] == 0
    assert client.get("/api/dashboard/defect-stats?days=abc", headers=headers["mgr"]).status_code == 400


def test_verification_updates_stats_and_keeps_history(client, headers, analyzed):
    dets = client.get(f"/api/inspections/{analyzed}/detections?defect_type=crack", headers=headers["op"]).json["items"]
    did = dets[0]["id"]
    assert client.post(f"/api/detections/{did}/verify", headers=headers["op"], json={"status": "confirmed"}).status_code == 403
    assert client.post(f"/api/detections/{did}/verify", headers=headers["eng"], json={"status": "maybe"}).status_code == 400
    assert client.post(f"/api/detections/{did}/verify", headers=headers["eng"], json={"status": "rejected"}).status_code == 400
    ok = client.post(f"/api/detections/{did}/verify", headers=headers["eng"], json={"status": "confirmed", "comment": "clear"})
    assert ok.status_code == 200 and ok.json["review_status"] == "confirmed"
    rej = client.post(f"/api/detections/{did}/verify", headers=headers["adm"],
                      json={"status": "rejected", "comment": "reflection, not a crack"}).json
    assert [v["status"] for v in rej["verifications"]] == ["confirmed", "rejected"]
    assert rej["verifications"][1]["reviewer"] == "adm"
    s = client.get("/api/dashboard/summary", headers=headers["mgr"]).json
    assert s["total_defects_detected"] == 3 and s["detections_rejected_by_reviewers"] == 1
    st = client.get("/api/dashboard/defect-stats", headers=headers["mgr"]).json
    assert {c["defect_type"]: c["count"] for c in st["by_class"]}["crack"] == 2


def test_inspection_history_filters(client, headers, upload, analyzed):
    upload(headers["op"], [img_file("x.jpg", seed=7)], title="Second batch", location="Ring road")
    upload(headers["eng"], [img_file("y.jpg", seed=8)], title="Third")
    h = headers["mgr"]
    allr = client.get("/api/inspections", headers=h).json
    assert allr["total"] == 3 and [i["id"] for i in allr["items"]] == [3, 2, 1]        # latest first
    assert client.get("/api/inspections?order=asc", headers=h).json["items"][0]["id"] == 1
    assert client.get("/api/inspections?status=completed", headers=h).json["total"] == 1
    assert client.get("/api/inspections?status=uploaded", headers=h).json["total"] == 2
    assert client.get("/api/inspections?q=ring", headers=h).json["total"] == 1
    assert client.get("/api/inspections?per_page=2&page=2", headers=h).json["items"][0]["id"] == 1
    today = datetime.now(timezone.utc).date()
    assert client.get(f"/api/inspections?from={today}&to={today}", headers=h).json["total"] == 3
    assert client.get(f"/api/inspections?to={today - timedelta(days=1)}", headers=h).json["total"] == 0
    assert client.get("/api/inspections?from=notadate", headers=h).status_code == 400
    eng_id = client.get("/api/auth/me", headers=headers["eng"]).json["id"]
    assert client.get(f"/api/inspections?created_by={eng_id}", headers=h).json["total"] == 1
    assert client.get("/api/inspections/999", headers=h).status_code == 404


def test_pdf_report(client, headers, analyzed, upload, tmp_path):
    r = client.get(f"/api/reports/{analyzed}/pdf", headers=headers["mgr"])
    assert r.status_code == 200 and r.mimetype == "application/pdf"
    assert r.data.startswith(b"%PDF") and len(r.data) > 5000
    assert "inspection_1_report.pdf" in r.headers["Content-Disposition"]
    if shutil.which("pdftotext"):
        p = tmp_path / "r.pdf"
        p.write_bytes(r.data)
        txt = subprocess.run(["pdftotext", "-layout", str(p), "-"], capture_output=True, text=True).stdout
        assert "Inspection #1" in txt and "Analyzed run" in txt and "test-mock-detector" in txt
        assert "crack" in txt and "0.90" in txt and "decision support" in txt
    # analyze hone se pehle report nahi
    pending = upload(headers["op"], [img_file("p.jpg", seed=9)]).json["inspection"]["id"]
    assert client.get(f"/api/reports/{pending}/pdf", headers=headers["op"]).status_code == 409
    assert client.get("/api/reports/999/pdf", headers=headers["op"]).status_code == 404


def test_csv_export(client, headers, analyzed, upload, app):
    r = client.get("/api/reports/export/csv", headers=headers["mgr"])
    assert r.status_code == 200 and r.mimetype == "text/csv"
    rows = list(csv.DictReader(io.StringIO(r.data.decode("utf-8-sig"))))
    assert len(rows) == 4
    api = client.get(f"/api/inspections/{analyzed}/detections", headers=headers["op"]).json["items"]
    assert sorted(float(x["confidence"]) for x in rows) == sorted(d["confidence"] for d in api)
    assert rows[0]["model_version"] == "test-mock-detector" and rows[0]["inspection_title"] == "Analyzed run"
    assert {x["image_filename"] for x in rows} == {"small.jpg", "big.jpg"}
    assert len(list(csv.DictReader(io.StringIO(client.get("/api/reports/export/csv?defect_type=corrosion",
                    headers=headers["mgr"]).data.decode("utf-8-sig"))))) == 1
    assert len(list(csv.DictReader(io.StringIO(client.get("/api/reports/export/csv?inspection_id=999",
                    headers=headers["mgr"]).data.decode("utf-8-sig"))))) == 0
    # rejected hatana
    did = api[0]["id"]
    client.post(f"/api/detections/{did}/verify", headers=headers["eng"], json={"status": "rejected", "comment": "fp"})
    ex = client.get("/api/reports/export/csv?exclude_rejected=true", headers=headers["mgr"]).data.decode("utf-8-sig")
    assert len(list(csv.DictReader(io.StringIO(ex)))) == 3


def test_csv_formula_injection_is_neutralised(client, headers, upload):
    iid = upload(headers["op"], [img_file("=cmd.jpg")], title='=HYPERLINK("http://evil")').json["inspection"]["id"]
    client.post(f"/api/inspections/{iid}/analyze", headers=headers["op"])
    txt = client.get("/api/reports/export/csv", headers=headers["mgr"]).data.decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(txt)))
    assert rows[0]["inspection_title"].startswith("'=") and rows[0]["image_filename"].startswith("'=")
