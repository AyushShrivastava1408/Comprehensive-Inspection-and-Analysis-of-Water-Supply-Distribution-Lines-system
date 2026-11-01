import io
import os

from conftest import img_file, make_image_bytes


def test_single_upload(client, headers, upload, app):
    r = upload(headers["op"], [img_file("pipe1.jpg")], title="Run A", location="Sector 5")
    assert r.status_code == 201, r.json
    insp, imgs = r.json["inspection"], r.json["images"]
    assert insp["status"] == "uploaded" and insp["title"] == "Run A" and insp["image_count"] == 1
    assert len(imgs) == 1 and imgs[0]["status"] == "pending"
    assert imgs[0]["width"] == 640 and imgs[0]["height"] == 480
    assert imgs[0]["original_filename"] == "pipe1.jpg"
    # unique naam + original storage
    stored = imgs[0]["stored_filename"]
    assert stored != "pipe1.jpg" and stored.endswith(".jpg")
    assert os.path.exists(os.path.join(app.config["ORIGINAL_FOLDER"], stored))
    assert imgs[0]["annotated_url"] is None
    # preview URL kaam karta hai (full + thumbnail)
    full = client.get(imgs[0]["original_url"], headers=headers["op"])
    assert full.status_code == 200 and full.mimetype == "image/jpeg"
    thumb = client.get(imgs[0]["original_url"] + "?w=100", headers=headers["op"])
    assert thumb.status_code == 200 and len(thumb.data) < len(full.data)
    tok = headers["op"]["Authorization"].split()[1]
    assert client.get(imgs[0]["original_url"] + f"?token={tok}").status_code == 200  # <img src> ke liye


def test_multiple_upload_and_unique_names(client, headers, upload):
    files = [img_file("same.jpg", seed=1), img_file("same.jpg", seed=2), img_file("b.png", seed=3),
             img_file("c.jpeg", seed=4)]
    r = upload(headers["op"], files)
    assert r.status_code == 201
    names = [i["stored_filename"] for i in r.json["images"]]
    assert len(names) == 4 and len(set(names)) == 4
    assert {n.rsplit(".", 1)[-1] for n in names} == {"jpg", "png"}


def test_invalid_formats_rejected(client, headers, upload, tmp_path):
    # sirf invalid -> 400
    for bad in [(io.BytesIO(b"hello"), "notes.txt"), (io.BytesIO(make_image_bytes()), "photo.gif"),
                (io.BytesIO(b"x" * 500), "fake.jpg"),                      # extension jpg, content nahi
                (io.BytesIO(b""), "empty.png")]:
        r = upload(headers["op"], [bad])
        assert r.status_code == 400, bad[1]
        assert r.json["details"][0]["filename"] == bad[1]
    # truncated/corrupt jpeg (signature sahi, data kharab)
    corrupt = make_image_bytes()[:200]
    r = upload(headers["op"], [(io.BytesIO(corrupt), "cut.jpg")])
    assert r.status_code == 400 and "corrupt" in r.json["details"][0]["reason"]
    # ek valid + ek invalid -> valid save, invalid report
    r = upload(headers["op"], [img_file("ok.jpg"), (io.BytesIO(b"nope"), "bad.png")])
    assert r.status_code == 201 and len(r.json["images"]) == 1
    assert r.json["rejected"][0]["filename"] == "bad.png"


def test_too_small_and_no_files(client, headers, upload):
    small = (io.BytesIO(make_image_bytes(w=20, h=20)), "tiny.jpg")
    r = upload(headers["op"], [small])
    assert r.status_code == 400 and "too small" in r.json["details"][0]["reason"]
    assert client.post("/api/inspections/upload", headers=headers["op"], data={}).status_code == 400


def test_quality_warnings(client, headers, upload):
    r = upload(headers["op"], [img_file("dark.jpg", flat=True, value=5), img_file("ok.jpg", seed=3)])
    by = {i["original_filename"]: i for i in r.json["images"]}
    assert "too_dark" in by["dark.jpg"]["quality_warnings"] and "blurry" in by["dark.jpg"]["quality_warnings"]
    assert by["ok.jpg"]["quality_warnings"] == []


def test_append_to_existing_inspection(client, headers, upload):
    first = upload(headers["op"], [img_file("a.jpg")]).json["inspection"]["id"]
    r = upload(headers["op"], [img_file("b.jpg", seed=5)], inspection_id=str(first))
    assert r.status_code == 201 and r.json["inspection"]["id"] == first and r.json["inspection"]["image_count"] == 2
    assert upload(headers["op"], [img_file("b.jpg")], inspection_id="9999").status_code == 404


def test_upload_permissions(client, headers, upload):
    assert upload(headers["mgr"], [img_file()]).status_code == 403
    assert client.post("/api/inspections/upload").status_code == 401
