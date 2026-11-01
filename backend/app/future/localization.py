"""Spatio-temporal localization (SRS 4.3):
   video timestamp -> distance (wheel log) -> lat/lon (GIS polyline)."""
import csv
import math
from typing import List, Tuple

import numpy as np

TIME_COLS = ("time_sec", "time", "timestamp", "t", "seconds")
DIST_COLS = ("distance_m", "distance", "odometer", "odometry", "dist")


class LogError(ValueError):
    pass


def haversine_m(lat1, lon1, lat2, lon2) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


class DistanceLog:
    """CSV: time_sec,distance_m  -> kisi bhi time pe distance (linear interpolation)."""

    def __init__(self, times: np.ndarray, dists: np.ndarray):
        self.times, self.dists = times, dists

    @classmethod
    def from_csv(cls, path: str) -> "DistanceLog":
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                raise LogError("Distance log is empty")
            cols = {c.strip().lower(): c for c in reader.fieldnames}
            t_col = next((cols[c] for c in TIME_COLS if c in cols), None)
            d_col = next((cols[c] for c in DIST_COLS if c in cols), None)
            if not t_col or not d_col:
                raise LogError(f"CSV needs a time column {TIME_COLS} and a distance column {DIST_COLS}")
            rows = []
            for row in reader:
                try:
                    t, d = float(row[t_col]), float(row[d_col])
                except (TypeError, ValueError):
                    continue  # kharab row skip (log gaps handle - SRS 5.4)
                if math.isfinite(t) and math.isfinite(d):
                    rows.append((t, d))
        if len(rows) < 2:
            raise LogError("Distance log needs at least 2 valid rows")
        arr = np.array(sorted(rows))
        _, idx = np.unique(arr[:, 0], return_index=True)  # duplicate timestamps hatao
        arr = arr[idx]
        if len(arr) < 2:
            raise LogError("Distance log needs at least 2 distinct timestamps")
        return cls(arr[:, 0], arr[:, 1])

    @property
    def duration(self) -> float:
        return float(self.times[-1])

    @property
    def max_distance(self) -> float:
        return float(self.dists.max())

    def distance_at(self, t: float) -> float:
        # np.interp range ke bahar edge value deta hai (clamp) - gaps/ends pe safe
        return float(np.interp(t, self.times, self.dists))


class PipelineRoute:
    """Polyline [[lat, lon], ...] pe distance se point nikalta hai."""

    def __init__(self, polyline: List[Tuple[float, float]], length_m: float = None):
        if len(polyline) < 2:
            raise ValueError("Polyline needs at least 2 points")
        self.pts = [(float(a), float(b)) for a, b in polyline]
        seg = [haversine_m(*self.pts[i], *self.pts[i + 1]) for i in range(len(self.pts) - 1)]
        self.geo_length = sum(seg)
        self.cum = np.concatenate([[0.0], np.cumsum(seg)])
        # length_m (real pipe length) diya ho to crawler distance ko usi se scale karte hain
        self.length_m = float(length_m) if length_m else self.geo_length

    def point_at(self, distance_m: float) -> Tuple[float, float]:
        frac = min(1.0, max(0.0, distance_m / self.length_m)) if self.length_m > 0 else 0.0
        target = frac * self.geo_length
        i = int(np.searchsorted(self.cum, target, side="right")) - 1
        i = min(max(i, 0), len(self.pts) - 2)
        seg_len = self.cum[i + 1] - self.cum[i]
        t = 0.0 if seg_len == 0 else (target - self.cum[i]) / seg_len
        (la1, lo1), (la2, lo2) = self.pts[i], self.pts[i + 1]
        return la1 + (la2 - la1) * t, lo1 + (lo2 - lo1) * t


def validate_polyline(polyline) -> List[Tuple[float, float]]:
    if not isinstance(polyline, list) or len(polyline) < 2:
        raise ValueError("polyline must be a list of at least 2 [lat, lon] points")
    out = []
    for p in polyline:
        if not (isinstance(p, (list, tuple)) and len(p) == 2):
            raise ValueError("each polyline point must be [lat, lon]")
        lat, lon = float(p[0]), float(p[1])
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError(f"invalid coordinate [{lat}, {lon}]")
        out.append((lat, lon))
    return out
