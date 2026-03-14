import cv2
import numpy as np
from flask import Blueprint, request, jsonify
from services.image_utils import decode_image_bytes
import mediapipe as mp

liveness_bp = Blueprint("liveness", __name__)

# Initialiser MediaPipe FaceMesh
mp_face_mesh = mp.solutions.face_mesh
face_mesh = mp_face_mesh.FaceMesh(
    static_image_mode=False,
    max_num_faces=1,
    refine_landmarks=True,
    min_detection_confidence=0.5
)

def eye_aspect_ratio(landmarks, eye_indices):
    """Compute EAR given a list of landmarks and eye landmark indices."""
    points = np.array([[landmarks[i].x, landmarks[i].y] for i in eye_indices])
    # Distances verticales
    A = np.linalg.norm(points[1] - points[5])
    B = np.linalg.norm(points[2] - points[4])
    # Distance horizontale
    C = np.linalg.norm(points[0] - points[3])
    ear = (A + B) / (2.0 * C)
    return ear

@liveness_bp.post("/liveness")
def liveness_check():
    """
    Reçoit une séquence d'images (frames) nommées frame0, frame1, ...
    Retourne {'liveness': True/False, 'confidence': float}
    """
    frames = []
    i = 0
    while f"frame{i}" in request.files:
        frame_bytes = request.files[f"frame{i}"].read()
        img = decode_image_bytes(frame_bytes)
        if img is not None:
            frames.append(img)
        i += 1

    if len(frames) < 3:
        return jsonify({"error": "Au moins 3 frames sont requises"}), 400

    ear_values = []
    for frame in frames:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = face_mesh.process(rgb)
        if results.multi_face_landmarks:
            landmarks = results.multi_face_landmarks[0].landmark
            # Indices MediaPipe pour les yeux (468 landmarks)
            LEFT_EYE = [33, 160, 158, 133, 153, 144]
            RIGHT_EYE = [362, 385, 387, 263, 373, 380]
            left_ear = eye_aspect_ratio(landmarks, LEFT_EYE)
            right_ear = eye_aspect_ratio(landmarks, RIGHT_EYE)
            ear = (left_ear + right_ear) / 2.0
            ear_values.append(ear)
        else:
            return jsonify({"error": "Visage non détecté dans une frame"}), 400

    if len(ear_values) < 3:
        return jsonify({"error": "Pas assez de frames valides"}), 400

    # Détection simple : chercher une chute brutale puis remontée
    min_ear = min(ear_values)
    min_idx = ear_values.index(min_ear)

    # Vérifier que le minimum est entouré de valeurs plus élevées
    if 0 < min_idx < len(ear_values) - 1:
        if ear_values[min_idx - 1] > min_ear + 0.1 and ear_values[min_idx + 1] > min_ear + 0.1:
            return jsonify({"liveness": True, "confidence": 0.8})
        else:
            return jsonify({"liveness": False, "confidence": 0.2})
    else:
        return jsonify({"liveness": False, "confidence": 0.2})