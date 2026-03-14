"""
Image utilities
---------------
Helpers to decode images from various input formats (file upload, base64 JSON).
"""

from __future__ import annotations

import base64
from typing import Optional

import cv2
import numpy as np



def decode_base64_image(b64_string: str) -> Optional[np.ndarray]:
    """Decode a base64-encoded image string to a BGR numpy array."""
    # Strip data-URI prefix if present  (data:image/jpeg;base64,…)
    if "," in b64_string:
        b64_string = b64_string.split(",", 1)[1]
    try:
        raw_bytes = base64.b64decode(b64_string)
    except Exception:
        return None
    return decode_image_bytes(raw_bytes)

def decode_image_bytes(raw_bytes: bytes, max_size: int = 640) -> Optional[np.ndarray]:
    arr = np.frombuffer(raw_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return None
    h, w = img.shape[:2]
    if max(h, w) > max_size:
        scale = max_size / max(h, w)
        new_w, new_h = int(w * scale), int(h * scale)
        img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    return img