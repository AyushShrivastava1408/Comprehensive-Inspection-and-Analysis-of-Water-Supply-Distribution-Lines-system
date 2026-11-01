"""REAL YOLOv8 inference test. Tumhare machine par tab chalega jab:
   - ultralytics installed ho, aur
   - trained weights mil jayein: models/best.pt  YA  env TEST_YOLO_WEIGHTS=/path/to/best.pt
Warna skip hota hai (CI/laptop bina model ke bhi green rahe). Isme MOCK nahi hai."""
import os

import cv2
import numpy as np
import pytest

WEIGHTS = os.getenv("TEST_YOLO_WEIGHTS") or os.path.join(os.path.dirname(__file__), "..", "models", "best.pt")
ultra = pytest.importorskip("ultralytics", reason="ultralytics not installed")
pytestmark = pytest.mark.skipif(not os.path.exists(WEIGHTS), reason=f"weights not found at {WEIGHTS}")


def test_real_model_end_to_end(tmp_path):
    from app import create_app
    from app.config import Config
    from app.extensions import db
    from app.models import User

    class Cfg(Config):
        TESTING = True
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{tmp_path / 't.db'}"
        ORIGINAL_FOLDER = str(tmp_path / "o")
        ANNOTATED_FOLDER = str(tmp_path / "a")
        RUN_JOBS_INLINE = True
        YOLO_WEIGHTS = WEIGHTS

    app = create_app(Cfg)            # NOTE: detector inject nahi kiya -> asli YoloDetector load hoga
    c = app.test_client()
    with app.app_context():
        u = User(username="u", email="u@x.com", role="admin")
        u.set_password("password123")
        db.session.add(u)
        db.session.commit()
    h = {"Authorization": "Bearer " + c.post("/api/auth/login", json={"username": "u", "password": "password123"}).json["access_token"]}

    # TEST_IMAGES env mein asli pipeline photos ka folder do, warna synthetic image (sirf pipeline chalane ke liye)
    folder = os.getenv("TEST_IMAGES")
    if folder:
        files = [os.path.join(folder, f) for f in sorted(os.listdir(folder)) if f.lower().endswith((".jpg", ".jpeg", ".png"))][:3]
        data = [(open(f, "rb"), os.path.basename(f)) for f in files]
    else:
        ok, buf = cv2.imencode(".jpg", np.random.default_rng(0).integers(0, 255, (480, 640, 3), dtype=np.uint8))
        import io
        data = [(io.BytesIO(buf.tobytes()), "synthetic.jpg")]
    iid = c.post("/api/inspections/upload", data={"images": data}, headers=h, content_type="multipart/form-data").json["inspection"]["id"]
    insp = c.post(f"/api/inspections/{iid}/analyze", headers=h).json
    assert insp["status"] == "completed", insp
    assert insp["model_version"].startswith(os.path.basename(WEIGHTS))
    info = c.get("/api/model/info", headers=h).json
    assert info["loaded"] and info["classes"]
    print("MODEL CLASSES:", info["classes"])
    for d in c.get(f"/api/inspections/{iid}/detections", headers=h).json["items"]:
        assert 0 < d["confidence"] <= 1 and d["bbox"]["x2"] > d["bbox"]["x1"]
    for im in c.get(f"/api/inspections/{iid}/images", headers=h).json["items"]:
        assert c.get(im["annotated_url"], headers=h).status_code == 200
