import pytest

PROTECTED_GET = ["/api/inspections", "/api/inspections/1", "/api/inspections/1/images",
                 "/api/inspections/1/detections", "/api/detections/1", "/api/images/1/original",
                 "/api/images/1/annotated", "/api/dashboard/summary", "/api/dashboard/defect-stats",
                 "/api/reports/1/pdf", "/api/reports/export/csv", "/api/model/info", "/api/auth/me"]


@pytest.mark.parametrize("url", PROTECTED_GET)
def test_endpoints_require_login(client, url):
    assert client.get(url).status_code == 401


def test_write_endpoints_require_login(client):
    assert client.post("/api/inspections/upload").status_code == 401
    assert client.post("/api/inspections/1/analyze").status_code == 401
    assert client.post("/api/detections/1/verify", json={}).status_code == 401


def test_register_login_me(client):
    r = client.post("/api/auth/register", json={"username": "ram", "email": "ram@x.com", "password": "password123"})
    assert r.status_code == 201 and r.json["role"] == "operator" and "password" not in str(r.json)
    assert client.post("/api/auth/register", json={"username": "ram", "email": "r2@x.com", "password": "password123"}).status_code == 409
    assert client.post("/api/auth/register", json={"username": "sam", "email": "s@x.com", "password": "short"}).status_code == 400
    assert client.post("/api/auth/login", json={"username": "ram", "password": "wrong"}).status_code == 401
    tok = client.post("/api/auth/login", json={"username": "ram", "password": "password123"}).json["access_token"]
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {tok}"}).json["username"] == "ram"
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_role_management(client, headers):
    assert client.get("/api/users", headers=headers["eng"]).status_code == 403
    uid = client.get("/api/auth/me", headers=headers["op"]).json["id"]
    assert client.patch(f"/api/users/{uid}", headers=headers["adm"], json={"role": "engineer"}).json["role"] == "engineer"
    assert client.patch(f"/api/users/{uid}", headers=headers["adm"], json={"role": "god"}).status_code == 400
    client.patch(f"/api/users/{uid}", headers=headers["adm"], json={"is_active": False})
    assert client.get("/api/auth/me", headers=headers["op"]).status_code == 401  # disabled user ka token chalna band


def test_delete_inspection_permissions_and_cleanup(client, headers, analyzed, app):
    import os
    assert client.delete(f"/api/inspections/{analyzed}", headers=headers["eng"]).status_code == 403
    assert client.delete(f"/api/inspections/{analyzed}", headers=headers["adm"]).status_code == 204
    assert os.listdir(app.config["ORIGINAL_FOLDER"]) == [] and os.listdir(app.config["ANNOTATED_FOLDER"]) == []
    assert client.get(f"/api/inspections/{analyzed}", headers=headers["adm"]).status_code == 404
    assert client.get("/api/dashboard/summary", headers=headers["adm"]).json["total_defects_detected"] == 0


def test_errors_are_json(client, headers):
    r = client.get("/api/nope", headers=headers["op"])
    assert r.status_code == 404 and "error" in r.json
