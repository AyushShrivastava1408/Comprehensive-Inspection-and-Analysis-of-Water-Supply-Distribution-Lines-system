"""Severity = HEURISTIC (class weight + bbox coverage + confidence). Model output nahi hai.
Weights engineering judgement hain; project guide ke saath review karke badal sakte ho."""
from ..constants import NON_DEFECT_CLASSES, SEV_CRITICAL, SEV_HIGH, SEV_LOW, SEV_MEDIUM

CLASS_WEIGHT = {"blockage": 0.90, "crack": 0.80, "joint_displacement": 0.75, "corrosion": 0.60}
DEFAULT_WEIGHT = 0.50
COVERAGE_FULL = 0.25  # image ka 25% cover karne wala defect = max coverage score


def severity_score(defect_type: str, coverage: float, confidence: float):
    if defect_type in NON_DEFECT_CLASSES:
        return None
    w = CLASS_WEIGHT.get(defect_type, DEFAULT_WEIGHT)
    cov = min(1.0, max(0.0, coverage) / COVERAGE_FULL)
    conf = min(1.0, max(0.0, confidence))
    return round(100 * (0.6 * w + 0.4 * cov) * (0.5 + 0.5 * conf), 1)


def severity_level(score):
    if score is None:
        return None
    if score >= 75:
        return SEV_CRITICAL
    if score >= 50:
        return SEV_HIGH
    if score >= 25:
        return SEV_MEDIUM
    return SEV_LOW
