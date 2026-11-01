"""SIRF AUTOMATED TESTS ke liye. App ke andar koi mock nahi hai; ye detector tests inject karte hain."""
from app.services.detector import BaseDetector, Detection


class MockDetector(BaseDetector):
    model_version = "test-mock-detector"
    class_names = ["crack", "corrosion", "blockage", "joint_displacement"]

    def __init__(self, fail_on_call=None):
        self.calls = 0
        self.fail_on_call = fail_on_call
        self.shapes = []

    def detect(self, image):
        self.calls += 1
        self.shapes.append(image.shape[:2])
        if self.fail_on_call == self.calls:
            raise RuntimeError("simulated inference failure")
        h, w = image.shape[:2]
        kind = self.class_names[(self.calls - 1) % 4]
        # processed image ke 25%-75% wala box, confidence 0.9 / 0.4 (taaki ek low-conf bhi mile)
        return [Detection(kind, kind, 0.9, w * .25, h * .25, w * .75, h * .75),
                Detection("crack", "crack", 0.4, 0, 0, w * .1, h * .1)]
