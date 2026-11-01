# Pipeline Inspection Backend (Image-based) - Group 9

Flask REST API. **Flow:**
`Image Upload -> OpenCV Preprocessing -> YOLOv8 Detection -> Annotated Image -> Database -> Inspection History -> Analytics -> Reports`

## Setup
```bash
python -m venv venv && source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                    # Windows: copy .env.example .env
# trained model ko models/best.pt mein rakho
flask --app run create-admin                            # pehla admin
python run.py                                           # http://localhost:5000
```
> Pehle wala (video) version use kiya tha to purani DB file ko ignore karo: ab DB `instance/inspection.db` hai (naya).
> Table structure badalne par DB delete karke dobara banao (migrations abhi nahi hain).

## Model (best.pt)
- File: `models/best.pt` (ya `.env` mein `YOLO_WEIGHTS=...`). Server model **ek baar load** karta hai aur reuse karta hai.
- Model nahi mila to `POST .../analyze` saaf message ke saath **503** deta hai. **Koi fake/mock result app mein nahi hai.**
- `GET /api/model/info` dikhata hai: weights hain ya nahi, load hua ya nahi, model ki asli classes.
- **Normal class**: hardcoded nahi hai. Agar tumhare trained model mein "normal" class hai to wo store hoti hai par defect count/stats mein nahi gini jaati.
- Preprocessing (CLAHE + Gaussian) training ke time jaisa hi rakho. Training images pe nahi lagayi thi to `.env` mein `APPLY_CLAHE=0 APPLY_DENOISE=0`.

## Storage
```
storage/
  original/    <uuid>.jpg|png            uploaded image, bilkul untouched
  annotated/   <uuid>_annotated.jpg      YOLO boxes + class + confidence ke saath
```

## API (sab login ke baad: `Authorization: Bearer <token>`; images ke liye `?token=<jwt>` bhi chalta hai)
| Method | URL | Role | Kaam |
|---|---|---|---|
| POST | /api/auth/register, /api/auth/login | public | account / JWT |
| GET | /api/auth/me | any | apni info |
| GET, PATCH | /api/users, /api/users/<id> | admin | role / active |
| **POST** | **/api/inspections/upload** | operator, engineer, admin | multipart: `images` (1+ files), `title`, `location`, `notes`, `inspection_id` (optional, purani inspection mein jodne ke liye) |
| **POST** | **/api/inspections/{id}/analyze** | operator, engineer, admin | background analysis (202). `?force=true` = sabko dobara |
| **GET** | **/api/inspections** | any | history. `status, q, from, to, created_by, order, page, per_page` |
| **GET** | **/api/inspections/{id}** | any | status, progress (`images_processed/image_count`), model_version |
| **GET** | **/api/inspections/{id}/images** | any | images + `original_url`, `annotated_url`, quality warnings |
| **GET** | **/api/inspections/{id}/detections** | any | `defect_type, severity, review_status, image_id, min_confidence, page` |
| **GET** | **/api/detections/{id}** | any | ek detection + verification history |
| POST | /api/detections/{id}/verify | engineer, admin | `{status: confirmed/rejected, comment}` (reject par comment zaroori) |
| GET | /api/images/{id}/original, /annotated | any | image; `?w=300` = thumbnail |
| **GET** | **/api/dashboard/summary** | any | inspections, images, defects, avg confidence, recent |
| **GET** | **/api/dashboard/defect-stats** | any | class-wise counts, severity, daily trend (`inspection_id`, `days`) |
| **GET** | **/api/reports/{id}/pdf** | any | PDF report |
| **GET** | **/api/reports/export/csv** | any | detections CSV (`inspection_id, defect_type, from, to, exclude_rejected`) |
| GET | /api/model/info | any | model ki sachchi sthiti |
| DELETE | /api/inspections/{id} | admin | files + records hatao |

Inspection status: `uploaded -> processing -> completed | partial | failed`.
`partial` = kuch images fail hui; `analyze` dobara chalao to sirf failed/pending images retry hoti hain.

## Upload validation
Sirf JPG/JPEG/PNG; file **content** (signature + OpenCV decode) check hota hai, sirf extension nahi; max 20 MB/file, 50 files/request;
minimum 64 px. Galat files `rejected` list mein reason ke saath aati hain (baaki valid save hoti hain; koi valid na ho to 400).
Blurry / too_dark / too_bright sirf **warning** hai (reject nahi), thresholds `.env`/config mein.

## Analytics
Saari numbers database records se query hoti hain. Empty DB = zeros/None, kuch bhi pre-filled nahi.
Reviewer ne reject kiye (false positive) detections defect counts se hat jaate hain (alag se `detections_rejected_by_reviewers` dikhta hai).
**Severity** (low/medium/high/critical) model ka output nahi, ek *heuristic* hai: class weight + bbox coverage + confidence (`app/services/severity.py`). Guide se review karwa lo.

## Test karna
```bash
pytest                     # 41 tests, mock detector sirf yahan (tests/mock_detector.py)
# REAL model test (tumhare machine pe):
TEST_YOLO_WEIGHTS=models/best.pt TEST_IMAGES=path/to/photos pytest tests/test_yolo_real.py -s
# Bina frontend ke full demo (server chalu rakho):
python scripts/demo_client.py --user admin --password '...' --images path/to/photos --out demo_output
```

## Frontend (React)
`frontend-integration/api.js` copy karo (saare endpoints ka client) aur `UploadAnalyze.example.jsx` dekho.
CORS on hai; `.env` mein `CORS_ORIGINS=http://localhost:5173` (apna React URL) rakho.

## Code map
```
app/api/            auth, inspections (upload/analyze/history), images, detections, dashboard, reports
app/services/       image_io (validation) | preprocessing (resize, CLAHE, Gaussian) | detector (YOLOv8, load-once)
                    annotate | analysis (poora flow) | severity | stats | reports (PDF/CSV)
app/models.py       User, Inspection, InspectionImage, Detection, Verification
app/future/         video/GPS code (localization, stabilizer) - abhi use nahi hota
tests/              upload, analysis, dashboard/reports, auth/permissions
```

## Limitations
- Analysis process ke andar background thread mein chalta hai (Celery nahi). Server beech mein restart ho to `processing` wali inspection atak sakti hai (dobara `analyze` chalao).
- Notifications (optional tha) nahi banaye.
- DB migrations nahi (Flask-Migrate/Alembic baad mein).
- Accuracy poori tarah tumhare trained model par depend karti hai; backend sirf uska output store/dikhata hai.
