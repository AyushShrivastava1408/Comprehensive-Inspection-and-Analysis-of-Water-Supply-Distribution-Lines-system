"""Original image pe bounding boxes + label (class + confidence) draw karta hai."""
import cv2
import numpy as np

# BGR colors
COLORS = {
    "crack": (0, 0, 255), "corrosion": (0, 140, 255), "blockage": (255, 0, 0),
    "joint_displacement": (0, 200, 0), "normal": (200, 200, 200),
}
DEFAULT_COLOR = (255, 0, 255)


def draw_detections(img: np.ndarray, dets) -> np.ndarray:
    """dets: objects with defect_type, confidence, x1,y1,x2,y2 (ORIGINAL image coords)."""
    out = img.copy()
    h, w = out.shape[:2]
    thick = max(2, int(round(max(h, w) / 500)))
    scale = max(0.5, max(h, w) / 1600)
    for d in dets:
        color = COLORS.get(d.defect_type, DEFAULT_COLOR)
        p1, p2 = (int(d.x1), int(d.y1)), (int(d.x2), int(d.y2))
        cv2.rectangle(out, p1, p2, color, thick)
        label = f"{d.defect_type} {d.confidence:.2f}"
        (tw, th), base = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, scale, max(1, thick - 1))
        y_top = max(p1[1] - th - base - 4, 0)
        cv2.rectangle(out, (p1[0], y_top), (p1[0] + tw + 6, y_top + th + base + 4), color, -1)
        cv2.putText(out, label, (p1[0] + 3, y_top + th + 1), cv2.FONT_HERSHEY_SIMPLEX, scale,
                    (255, 255, 255), max(1, thick - 1), cv2.LINE_AA)
    return out
