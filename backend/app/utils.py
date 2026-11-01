import os
from datetime import datetime, timezone

from flask import request
from .errors import ApiError


def json_body() -> dict:
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ApiError("Request body must be a JSON object", 400)
    return data


def require_fields(data: dict, *fields):
    missing = [f for f in fields if data.get(f) in (None, "")]
    if missing:
        raise ApiError(f"Missing required field(s): {', '.join(missing)}", 400)


def paginate_args(default_per_page=20, max_per_page=200):
    try:
        page = max(1, int(request.args.get("page", 1)))
        per_page = min(max_per_page, max(1, int(request.args.get("per_page", default_per_page))))
    except ValueError:
        raise ApiError("page and per_page must be integers", 400)
    return page, per_page


def paginated(query, page, per_page, serializer):
    p = query.paginate(page=page, per_page=per_page, error_out=False)
    return {"items": [serializer(i) for i in p.items], "page": p.page,
            "per_page": p.per_page, "total": p.total, "pages": p.pages}


def safe_remove(path):
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


def parse_date_arg(name, end_of_day=False):
    """?from=2026-10-01 / ?to=2026-10-31 (ISO). Invalid ho to 400."""
    raw = request.args.get(name)
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        raise ApiError(f"'{name}' must be an ISO date like 2026-10-31")
    if len(raw) <= 10 and end_of_day:
        dt = dt.replace(hour=23, minute=59, second=59)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
