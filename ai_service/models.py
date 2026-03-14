import logging
from typing import Optional

import cv2
import numpy as np
import onnxruntime as ort
from facenet_pytorch import MTCNN as MTCNN_PT

logger = logging.getLogger(__name__)

# FaceNet input size
FACE_SIZE = 160

# Normalisation constants
NORM_MEAN = 127.5
NORM_STD = 128.0


class ModelService:
    """
    Provides:
      - detect_face(image_bgr)  → bounding box dict or None
      - get_embedding(image_bgr) → 512-d unit vector or None
    """

    def __init__(self, onnx_model_path: str) -> None:
        self._detector = self._load_detector()
        self._session = self._load_onnx(onnx_model_path)
        self._input_name: str = self._session.get_inputs()[0].name
        self.model_loaded: bool = True

        # Préchauffage : inférence factice
        dummy = np.random.randn(1, 3, 160, 160).astype(np.float32)
        _ = self._session.run(None, {self._input_name: dummy})
        logger.info("Model pre-warmed.")

    # ── Public API ─────────────────────────────────────────────────────────────

    def detect_face(self, image_bgr: np.ndarray) -> Optional[dict]:
        """
        Detect the largest face in a BGR image.

        Returns a dict with keys: box [x, y, w, h], confidence, keypoints.
        Returns None if no face is detected.
        """
        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        boxes, probs, points = self._detector.detect(image_rgb, landmarks=True)
        if boxes is None or len(boxes) == 0:
            return None
        # Prendre la première détection (la plus confiante)
        box = boxes[0].astype(int).tolist()
        confidence = float(probs[0])
        # Les points sont de forme (5,2) – on les convertit en dict
        kp = points[0]
        keypoints = {
            'left_eye': [int(kp[0][0]), int(kp[0][1])],
            'right_eye': [int(kp[1][0]), int(kp[1][1])],
            'nose': [int(kp[2][0]), int(kp[2][1])],
            'mouth_left': [int(kp[3][0]), int(kp[3][1])],
            'mouth_right': [int(kp[4][0]), int(kp[4][1])],
        }
        return {
            'box': [box[0], box[1], box[2]-box[0], box[3]-box[1]],
            'confidence': confidence,
            'keypoints': keypoints,
        }

    def get_embedding(self, image_bgr: np.ndarray) -> Optional[np.ndarray]:
        """
        Detect the largest face, align and extract its 512-d L2-normalised embedding.

        Returns None if no face is detected.
        """
        detection = self.detect_face(image_bgr)
        if detection is None:
            logger.debug("No face detected in image.")
            return None

        face_crop = self._crop_and_align(image_bgr, detection["box"])
        embedding = self._run_inference(face_crop)
        return embedding

    # ── Private helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _load_detector():
        logger.info("Initialising MTCNN (PyTorch) …")
        return MTCNN_PT(keep_all=False, device='cpu')

    @staticmethod
    def _load_onnx(path: str) -> ort.InferenceSession:
        logger.info("Loading ONNX model from '%s' …", path)
        providers = (
            ["CUDAExecutionProvider", "CPUExecutionProvider"]
            if "CUDAExecutionProvider" in ort.get_available_providers()
            else ["CPUExecutionProvider"]
        )
        logger.info("Using ONNX providers: %s", providers)
        return ort.InferenceSession(path, providers=providers)

    @staticmethod
    def _crop_and_align(image_bgr: np.ndarray, box: list[int]) -> np.ndarray:
        """Crop face region and resize to FACE_SIZE × FACE_SIZE."""
        x, y, w, h = box
        # Clamp coordinates to image boundaries
        ih, iw = image_bgr.shape[:2]
        x1 = max(0, x)
        y1 = max(0, y)
        x2 = min(iw, x + w)
        y2 = min(ih, y + h)

        face = image_bgr[y1:y2, x1:x2]
        face_rgb = cv2.cvtColor(face, cv2.COLOR_BGR2RGB)
        face_resized = cv2.resize(face_rgb, (FACE_SIZE, FACE_SIZE), interpolation=cv2.INTER_LINEAR)
        return face_resized

    def _run_inference(self, face_rgb: np.ndarray) -> np.ndarray:
        """Normalise pixel values and run ONNX inference."""
        face = face_rgb.astype(np.float32)
        face = (face - NORM_MEAN) / NORM_STD
        # Shape: (160, 160, 3) -> ajouter batch
        face_input = np.expand_dims(face, axis=0)          # (1, 160, 160, 3)
        # Convertir en channels first (NCHW) attendu par le modèle
        face_input = np.transpose(face_input, (0, 3, 1, 2))  # (1, 3, 160, 160)

        outputs = self._session.run(None, {self._input_name: face_input})
        embedding = outputs[0][0]  # shape (512,)

        # L2 normalise
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm
        return embedding