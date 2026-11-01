import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

STORAGE_DIR = os.getenv("STORAGE_DIR", str(BASE_DIR / "storage"))


def _db_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        return f"sqlite:///{BASE_DIR / 'instance' / 'inspection.db'}"
    return url.replace("postgres://", "postgresql://", 1)


def _bool(name, default="1"):
    return os.getenv(name, default).lower() in ("1", "true", "yes")


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me-dev-secret-change-me")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-jwt-secret-change-me-dev-jwt-secret-change")
    # Header ke saath ?token= bhi chalega, taaki <img src> mein preview dikh sake
    JWT_TOKEN_LOCATION = ["headers", "query_string"]
    JWT_QUERY_STRING_NAME = "token"
    JWT_ACCESS_TOKEN_EXPIRES = 60 * 60 * 8

    SQLALCHEMY_DATABASE_URI = _db_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Storage: storage/original + storage/annotated
    ORIGINAL_FOLDER = os.path.join(STORAGE_DIR, "original")
    ANNOTATED_FOLDER = os.path.join(STORAGE_DIR, "annotated")

    # Upload limits / validation
    ALLOWED_IMAGE_EXT = {"jpg", "jpeg", "png"}
    MAX_IMAGE_MB = int(os.getenv("MAX_IMAGE_MB", "20"))
    MAX_FILES_PER_UPLOAD = int(os.getenv("MAX_FILES_PER_UPLOAD", "50"))
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_REQUEST_MB", "500")) * 1024 * 1024
    MIN_IMAGE_SIDE = int(os.getenv("MIN_IMAGE_SIDE", "64"))        # isse chhoti image reject
    # Quality warnings (reject nahi karte, sirf flag karte hain). Heuristic thresholds.
    BLUR_THRESHOLD = float(os.getenv("BLUR_THRESHOLD", "50"))      # Laplacian variance
    DARK_THRESHOLD = float(os.getenv("DARK_THRESHOLD", "35"))      # mean gray
    BRIGHT_THRESHOLD = float(os.getenv("BRIGHT_THRESHOLD", "225"))

    # Preprocessing (model jis preprocessing pe train hua uske hisaab se on/off karo)
    APPLY_CLAHE = _bool("APPLY_CLAHE")
    APPLY_DENOISE = _bool("APPLY_DENOISE")
    PROCESS_MAX_SIDE = int(os.getenv("PROCESS_MAX_SIDE", "1920"))  # isse badi image downscale hogi

    # YOLOv8
    YOLO_WEIGHTS = os.getenv("YOLO_WEIGHTS", str(BASE_DIR / "models" / "best.pt"))
    YOLO_DEVICE = os.getenv("YOLO_DEVICE") or None
    YOLO_IMGSZ = int(os.getenv("YOLO_IMGSZ", "640"))
    CONF_THRESHOLD = float(os.getenv("CONF_THRESHOLD", "0.25"))

    MAX_WORKERS = int(os.getenv("MAX_WORKERS", "1"))
    RUN_JOBS_INLINE = False  # sirf tests ke liye
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")
