"""
POST /detect
------------
Detect the largest face in an uploaded image.

Input  : multipart/form-data  field "image"
         OR JSON              { "image": "<base64>" }

Output : { "box": [x, y, w, h], "confidence": float, "keypoints": {...} }
         { "error": "..." }   on failure
"""

from flask import Blueprint, current_app, jsonify, request

from services.image_utils import decode_base64_image, decode_image_bytes

detect_bp = Blueprint("detect", __name__)


@detect_bp.post("/detect")
def detect():
    model_service = current_app.config["MODEL_SERVICE"]
    image = _parse_image(request)
    if image is None:
        return jsonify({"error": "Could not decode image. Provide multipart 'image' or JSON base64."}), 400

    detection = model_service.detect_face(image)
    if detection is None:
        return jsonify({"error": "No face detected in the provided image."}), 422

    return jsonify(
        {
            "box": detection["box"],
            "confidence": round(float(detection["confidence"]), 4),
            "keypoints": {k: list(map(int, v)) for k, v in detection["keypoints"].items()},
        }
    )


def _parse_image(req):
    if "image" in req.files:
        return decode_image_bytes(req.files["image"].read())
    data = req.get_json(silent=True) or {}
    if "image" in data:
        return decode_base64_image(data["image"])
    return None