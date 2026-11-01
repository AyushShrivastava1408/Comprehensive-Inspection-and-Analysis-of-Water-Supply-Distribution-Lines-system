import io
import os
import sys

import cv2
import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app  # noqa: E402
from app.config import Config  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import User  # noqa: E402
from mock_detector import MockDetector  # noqa: E402


@pytest.fixture()
def app(tmp_path):
    class TestConfig(Config):
        TESTING = True
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{tmp_path / 'test.db'}"
        ORIGINAL_FOLDER = str(tmp_path / "storage" / "original")
        ANNOTATED_FOLDER = str(tmp_path / "storage" / "annotated")
        RUN_JOBS_INLINE = True
        PROCESS_MAX_SIDE = 1000

    a = create_app(TestConfig)
    a.extensions["detector"] = MockDetector()   # sirf tests mein
    return a


@pytest.fixture()
def client(app):
    return app.test_client()


def make_user(app, username, role):
    with app.app_context():
        u = User(username=username, email=f"{username}@x.com", role=role)
        u.set_password("password123")
        db.session.add(u)
        db.session.commit()


def login(client, username):
    r = client.post("/api/auth/login", json={"username": username, "password": "password123"})
    assert r.status_code == 200, r.json
    return {"Authorization": f"Bearer {r.json['access_token']}"}


@pytest.fixture()
def headers(app, client):
    for name, role in [("op", "operator"), ("eng", "engineer"), ("adm", "admin"), ("mgr", "manager")]:
        make_user(app, name, role)
    return {n: login(client, n) for n in ("op", "eng", "adm", "mgr")}


def make_image_bytes(w=640, h=480, ext="jpg", seed=0, flat=False, value=128):
    rng = np.random.default_rng(seed)
    img = np.full((h, w, 3), value, np.uint8) if flat else rng.integers(0, 255, (h, w, 3), dtype=np.uint8)
    ok, buf = cv2.imencode(f".{ext}", img)
    assert ok
    return buf.tobytes()


def img_file(name="a.jpg", **kw):
    return (io.BytesIO(make_image_bytes(ext=name.rsplit(".", 1)[-1].replace("jpeg", "jpg"), **kw)), name)


@pytest.fixture()
def upload(client):
    def _up(h, files, **form):
        data = {"images": files}
        data.update(form)
        return client.post("/api/inspections/upload", data=data, headers=h, content_type="multipart/form-data")
    return _up


def make_gradient_bytes(w, h, ext="jpg"):
    """Badi image jo file size mein chhoti rahe (random noise nahi)."""
    x = np.linspace(0, 255, w, dtype=np.uint8)[None, :].repeat(h, 0)
    y = np.linspace(0, 255, h, dtype=np.uint8)[:, None].repeat(w, 1)
    img = np.dstack([x, y, (x // 2 + y // 2).astype(np.uint8)])
    img[::40, :, :] = 255  # thodi texture
    ok, buf = cv2.imencode(f".{ext}", img)
    assert ok
    return buf.tobytes()


@pytest.fixture()
def analyzed(client, headers, upload):
    """1 inspection: 640x480 + 3000x2000 image, analyzed."""
    r = upload(headers["op"], [img_file("small.jpg", seed=1),
                               (io.BytesIO(make_gradient_bytes(3000, 2000)), "big.jpg")],
               title="Analyzed run", location="Test street")
    iid = r.json["inspection"]["id"]
    a = client.post(f"/api/inspections/{iid}/analyze", headers=headers["op"])
    assert a.status_code == 200, a.json
    return iid
