import hashlib
import io
import os

import cv2
import numpy as np
import pytest

from conftest import img_file
from mock_detector import MockDetector
from app.services.detector import Detection
from app.services.preprocessing import apply_clahe, denoise, preprocess_image, resize_max_side


def test_analysis_end_to_end(client, headers, upload, app):
    from conftest import make_gradient_bytes
    r = upload(headers["op"], [img_file("small.jpg", seed=1),
                               (io.BytesIO(make_gradient_bytes(3000, 2000)), "big.jpg")], title="T")
    iid = r.json["inspection"]["id"]
    originals = {i["id"]: i for i in r.json["images"]}
    hashes = {k: hashlib.md5(open(os.path.join(app.config["ORIGINAL_FOLDER"], v["stored_filename"]), "rb").read()).hexdigest()
              for k, v in originals.items()}

    # analyze se pehle annotated nahi hai
    assert client.get(f"/api/images/{r.json['images'][0]['id']}/annotated", headers=headers["op"]).status_code == 404

    a = client.post(f"/api/inspections/{iid}/analyze", headers=headers["op"])
    assert a.status_code == 200
    insp = a.json
    assert insp["status"] == "completed" and insp["images_processed"] == 2 and insp["detection_count"] == 4
    assert insp["model_version"] == "test-mock-detector"
    assert insp["settings"]["apply_clahe"] is True and insp["settings"]["process_max_side"] == 1000

    # preprocessing: badi image downscale hui, chhoti nahi
    det = app.extensions["detector"]
    assert det.shapes[0] == (480, 640) and det.shapes[1] == (667, 1000)

    imgs = client.get(f"/api/inspections/{iid}/images", headers=headers["op"]).json["items"]
    assert imgs[0]["status"] == "analyzed" and imgs[0]["detection_count"] == 2 and imgs[0]["inference_ms"] is not None
    for im in imgs:
        # original untouched
        path = os.path.join(app.config["ORIGINAL_FOLDER"], im["stored_filename"])
        assert hashlib.md5(open(path, "rb").read()).hexdigest() == hashes[im["id"]]
        # annotated alag folder mein, original size, original se alag pixels
        ann = client.get(im["annotated_url"], headers=headers["op"])
        assert ann.status_code == 200 and ann.mimetype == "image/jpeg"
        a_img = cv2.imdecode(np.frombuffer(ann.data, np.uint8), 1)
        o_img = cv2.imread(path)
        assert a_img.shape == o_img.shape and np.abs(a_img.astype(int) - o_img.astype(int)).mean() > 0.1
    assert len(os.listdir(app.config["ANNOTATED_FOLDER"])) == 2

    # detections: asli confidence + bbox ORIGINAL coordinates mein
    dets = client.get(f"/api/inspections/{iid}/detections?image_id={imgs[1]['id']}", headers=headers["op"]).json["items"]
    big = max(dets, key=lambda d: d["confidence"])
    assert big["confidence"] == 0.9 and big["defect_type"] == "corrosion"
    assert big["bbox"]["x1"] == pytest.approx(750, abs=2) and big["bbox"]["x2"] == pytest.approx(2250, abs=2)
    assert big["bbox"]["y1"] == pytest.approx(500, abs=2) and big["bbox"]["y2"] == pytest.approx(1500, abs=2)
    assert big["bbox_coverage"] == pytest.approx(0.25, abs=0.01) and big["severity_level"] in ("low", "medium", "high", "critical")

    # filters
    assert client.get(f"/api/inspections/{iid}/detections?min_confidence=0.5", headers=headers["op"]).json["total"] == 2
    assert client.get(f"/api/inspections/{iid}/detections?defect_type=crack", headers=headers["op"]).json["total"] == 3
    one = client.get(f"/api/detections/{big['id']}", headers=headers["op"]).json
    assert one["id"] == big["id"] and one["verifications"] == []

    # dobara analyze: bina force 409, force se replace (duplicate nahi)
    assert client.post(f"/api/inspections/{iid}/analyze", headers=headers["op"]).status_code == 409
    assert client.post(f"/api/inspections/{iid}/analyze?force=true", headers=headers["op"]).json["detection_count"] == 4
    assert len(os.listdir(app.config["ANNOTATED_FOLDER"])) == 2


def test_model_loaded_once(client, headers, upload, app):
    det = app.extensions["detector"]
    r = upload(headers["op"], [img_file("a.jpg", seed=1), img_file("b.jpg", seed=2)])
    client.post(f"/api/inspections/{r.json['inspection']['id']}/analyze", headers=headers["op"])
    r2 = upload(headers["op"], [img_file("c.jpg", seed=3)])
    client.post(f"/api/inspections/{r2.json['inspection']['id']}/analyze", headers=headers["op"])
    assert app.extensions["detector"] is det and det.calls == 3


def test_partial_failure_and_retry(client, headers, upload, app):
    app.extensions["detector"] = MockDetector(fail_on_call=2)
    iid = upload(headers["op"], [img_file("a.jpg", seed=1), img_file("b.jpg", seed=2)]).json["inspection"]["id"]
    insp = client.post(f"/api/inspections/{iid}/analyze", headers=headers["op"]).json
    assert insp["status"] == "partial"
    imgs = client.get(f"/api/inspections/{iid}/images", headers=headers["op"]).json["items"]
    assert [i["status"] for i in imgs] == ["analyzed", "failed"] and "simulated" in imgs[1]["error"]
    # retry sirf failed image ko dobara chalata hai
    insp = client.post(f"/api/inspections/{iid}/analyze", headers=headers["op"]).json
    assert insp["status"] == "completed" and insp["detection_count"] == 4


def test_all_images_fail(client, headers, upload, app):
    class Boom(MockDetector):
        def detect(self, image):
            raise RuntimeError("boom")
    app.extensions["detector"] = Boom()
    iid = upload(headers["op"], [img_file("a.jpg")]).json["inspection"]["id"]
    insp = client.post(f"/api/inspections/{iid}/analyze", headers=headers["op"]).json
    assert insp["status"] == "failed" and insp["error"]


def test_missing_weights_gives_clear_503(client, headers, upload, app):
    app.extensions.pop("detector")
    app.config["YOLO_WEIGHTS"] = "/nonexistent/best.pt"
    iid = upload(headers["op"], [img_file("a.jpg")]).json["inspection"]["id"]
    r = client.post(f"/api/inspections/{iid}/analyze", headers=headers["op"])
    assert r.status_code == 503 and "best.pt" in r.json["error"]
    info = client.get("/api/model/info", headers=headers["op"]).json
    assert info["weights_present"] is False and info["loaded"] is False and info["classes"] is None


def test_analyze_rules(client, headers, upload):
    iid = upload(headers["op"], [img_file("a.jpg")]).json["inspection"]["id"]
    assert client.post(f"/api/inspections/{iid}/analyze", headers=headers["mgr"]).status_code == 403
    assert client.post("/api/inspections/999/analyze", headers=headers["op"]).status_code == 404
    from app.extensions import db
    from app.models import Inspection
    with client.application.app_context():
        db.session.get(Inspection, iid).status = "processing"
        db.session.commit()
    assert client.post(f"/api/inspections/{iid}/analyze", headers=headers["op"]).status_code == 409


def test_normal_class_not_counted_as_defect(client, headers, upload, app):
    class WithNormal(MockDetector):
        def detect(self, image):
            h, w = image.shape[:2]
            return [Detection("normal", "Normal", 0.8, 0, 0, w, h), Detection("crack", "crack", 0.7, 5, 5, 50, 50)]
    app.extensions["detector"] = WithNormal()
    iid = upload(headers["op"], [img_file("a.jpg")]).json["inspection"]["id"]
    client.post(f"/api/inspections/{iid}/analyze", headers=headers["op"])
    items = client.get(f"/api/inspections/{iid}/detections", headers=headers["op"]).json["items"]
    normal = [d for d in items if d["defect_type"] == "normal"][0]
    assert normal["severity_level"] is None
    stats = client.get("/api/dashboard/defect-stats", headers=headers["op"]).json
    assert stats["total_defects"] == 1 and all(c["defect_type"] != "normal" for c in stats["by_class"])


# ---- OpenCV preprocessing units ----
def test_preprocessing_units():
    rng = np.random.default_rng(0)
    dark = (rng.integers(0, 60, (200, 300, 3))).astype(np.uint8)
    enh = apply_clahe(dark)
    assert enh.shape == dark.shape and enh.mean() > dark.mean()          # contrast badha
    noisy = rng.integers(0, 255, (100, 100, 3), dtype=np.uint8)
    assert denoise(noisy).std() < noisy.std()                             # noise kam
    big, s = resize_max_side(np.zeros((2000, 3000, 3), np.uint8), 1000)
    assert big.shape[:2] == (667, 1000) and s == pytest.approx(1 / 3)
    same, s = resize_max_side(np.zeros((200, 300, 3), np.uint8), 1000)
    assert same.shape[:2] == (200, 300) and s == 1.0
    cfg = {"PROCESS_MAX_SIDE": 100, "APPLY_CLAHE": False, "APPLY_DENOISE": False}
    out, _ = preprocess_image(dark, cfg)
    assert out.shape[:2] == (67, 100)
