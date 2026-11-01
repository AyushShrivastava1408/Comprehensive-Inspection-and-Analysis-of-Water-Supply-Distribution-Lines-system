"""Bina frontend ke poora flow chalane ke liye (real server + real model).

  python scripts/demo_client.py --user admin --password '...' --images path/to/photos_folder_or_files
Outputs ./demo_output/ mein: annotated images, report.pdf, detections.csv
"""
import argparse
import os
import sys
import time

import requests


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:5000")
    ap.add_argument("--user", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--images", nargs="+", required=True, help="image files ya ek folder")
    ap.add_argument("--title", default="Demo inspection")
    ap.add_argument("--out", default="demo_output")
    a = ap.parse_args()
    api = a.url.rstrip("/") + "/api"

    paths = []
    for p in a.images:
        if os.path.isdir(p):
            paths += [os.path.join(p, f) for f in sorted(os.listdir(p)) if f.lower().endswith((".jpg", ".jpeg", ".png"))]
        else:
            paths.append(p)
    if not paths:
        sys.exit("No images found")

    r = requests.post(f"{api}/auth/login", json={"username": a.user, "password": a.password})
    r.raise_for_status()
    h = {"Authorization": "Bearer " + r.json()["access_token"]}

    files = [("images", (os.path.basename(p), open(p, "rb"))) for p in paths]
    up = requests.post(f"{api}/inspections/upload", headers=h, files=files, data={"title": a.title})
    if up.status_code != 201:
        sys.exit(f"Upload failed: {up.status_code} {up.text}")
    iid = up.json()["inspection"]["id"]
    print(f"Uploaded {len(up.json()['images'])} image(s) -> inspection #{iid}")
    for rej in up.json()["rejected"]:
        print("  rejected:", rej)

    r = requests.post(f"{api}/inspections/{iid}/analyze", headers=h)
    if r.status_code not in (200, 202):
        sys.exit(f"Analyze failed: {r.status_code} {r.text}")
    while True:
        insp = requests.get(f"{api}/inspections/{iid}", headers=h).json()
        print(f"  status={insp['status']} {insp['images_processed']}/{insp['image_count']}")
        if insp["status"] in ("completed", "partial", "failed"):
            break
        time.sleep(1.5)
    if insp["status"] == "failed":
        sys.exit("Analysis failed: " + str(insp["error"]))

    os.makedirs(a.out, exist_ok=True)
    dets = requests.get(f"{api}/inspections/{iid}/detections?per_page=500", headers=h).json()["items"]
    print(f"\nModel: {insp['model_version']} | {len(dets)} detection(s)")
    for d in dets:
        print(f"  image {d['image_id']}: {d['defect_type']:<20} conf={d['confidence']:.3f} severity={d['severity_level']}")
    for im in requests.get(f"{api}/inspections/{iid}/images", headers=h).json()["items"]:
        if im["annotated_url"]:
            data = requests.get(a.url.rstrip("/") + im["annotated_url"], headers=h).content
            open(os.path.join(a.out, f"annotated_{os.path.splitext(im['original_filename'])[0]}.jpg"), "wb").write(data)
    open(os.path.join(a.out, "report.pdf"), "wb").write(requests.get(f"{api}/reports/{iid}/pdf", headers=h).content)
    open(os.path.join(a.out, "detections.csv"), "wb").write(
        requests.get(f"{api}/reports/export/csv?inspection_id={iid}", headers=h).content)
    print(f"\nSaved annotated images, report.pdf, detections.csv in {a.out}/")


if __name__ == "__main__":
    main()
