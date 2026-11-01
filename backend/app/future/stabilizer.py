"""FUTURE (video/crawler workflow): Farneback optical-flow stabilization.
Image workflow mein use nahi hota."""
import cv2
import numpy as np


class Stabilizer:
    """Farneback optical flow se camera jitter kam karta hai.

    Har frame ka median (dx, dy) nikalte hain, trajectory banate hain, use smooth karte hain,
    aur (smooth - actual) jitna frame ko shift kar dete hain.
    Crawler aage badhne se flow 'zoom' jaisa hota hai (median ~0), isliye median sirf jitter pakdta hai.
    """

    def __init__(self, smoothing=0.9, scale=0.5, max_shift_ratio=0.05):
        self.smoothing = smoothing
        self.scale = scale
        self.max_shift_ratio = max_shift_ratio
        self._prev = None
        self._traj = np.zeros(2)
        self._smooth = np.zeros(2)

    def reset(self):
        self._prev = None
        self._traj[:] = 0
        self._smooth[:] = 0

    def stabilize(self, frame: np.ndarray) -> np.ndarray:
        small = cv2.resize(frame, None, fx=self.scale, fy=self.scale)
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        if self._prev is None or self._prev.shape != gray.shape:
            self._prev = gray
            return frame
        flow = cv2.calcOpticalFlowFarneback(self._prev, gray, None, 0.5, 3, 15, 3, 5, 1.2, 0)
        self._prev = gray
        shift = np.array([np.median(flow[..., 0]), np.median(flow[..., 1])]) / self.scale
        self._traj += shift
        self._smooth = self.smoothing * self._smooth + (1 - self.smoothing) * self._traj
        corr = self._smooth - self._traj
        h, w = frame.shape[:2]
        corr[0] = np.clip(corr[0], -w * self.max_shift_ratio, w * self.max_shift_ratio)
        corr[1] = np.clip(corr[1], -h * self.max_shift_ratio, h * self.max_shift_ratio)
        m = np.float32([[1, 0, corr[0]], [0, 1, corr[1]]])
        return cv2.warpAffine(frame, m, (w, h), borderMode=cv2.BORDER_REFLECT)
