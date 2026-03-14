"""
POST /embed
-----------
Extract a 512-d FaceNet embedding from an image.

Input  : multipart/form-data  field "image"
         OR JSON              { "image": "<base64>" }

Output : { "embedding": [float × 512] }
         { "error": "..." }   on failure
"""

from flask import Blueprint, current_app, jsonify, request

from services.image_utils import decode_base64_image, decode_image_bytes

embed_bp = Blueprint("embed", __name__)


@embed_bp.post("/embed")
def embed():
    model_service = current_app.config["MODEL_SERVICE"]
    image = _parse_image(request)
    if image is None:
        return jsonify({"error": "Could not decode image. Provide multipart 'image' or JSON base64."}), 400

    embedding = model_service.get_embedding(image)
    if embedding is None:
        return jsonify({"error": "No face detected in the provided image."}), 422

    return jsonify({"embedding": embedding.tolist()})


def _parse_image(req):
    if "image" in req.files:
        return decode_image_bytes(req.files["image"].read())
    data = req.get_json(silent=True) or {}
    if "image" in data:
        return decode_base64_image(data["image"])
    return None