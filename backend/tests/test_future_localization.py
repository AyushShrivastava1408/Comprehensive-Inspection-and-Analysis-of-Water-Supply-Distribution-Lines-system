"""app/future/ ka code (abhi active workflow mein nahi) - sirf isliye test hai ki bigad na jaye."""
import pytest

from app.future.localization import DistanceLog, PipelineRoute


def test_route_and_log(tmp_path):
    r = PipelineRoute([[22.0, 75.0], [22.001, 75.0]])
    assert r.point_at(r.length_m / 2)[0] == pytest.approx(22.0005, abs=1e-6)
    p = tmp_path / "l.csv"
    p.write_text("time_sec,distance_m\n0,0\n2,4\n")
    assert DistanceLog.from_csv(str(p)).distance_at(1) == pytest.approx(2)
