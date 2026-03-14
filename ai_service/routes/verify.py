"""
POST /verify
------------
Compare two faces or two embeddings.

Accepted JSON bodies:

  Mode A – two base64 images:
    { "image1": "<base64>", "image2": "<base64>" }

  Mode B – one base64 image + one stored embedding:
    { "image": "<base64>", "embedding": [float × 512] }

  Mode C – two raw embeddings:
    { "embedding1": [float × 512], "embedding2": [float × 512] }

Output : { "similarity": float, "verified": bool }
         { "error": "..." }   on failure
"""

import numpy as np
from flask import Blueprint, current_app, jsonify, request

from services.image_utils import decode_base64_image
from services.similarity import cosine_similarity

verify_bp = Blueprint("verify", __name__)


@verify_bp.post("/verify")
def verify():
    model_service = current_app.config["MODEL_SERVICE"]
    threshold: float = current_app.config["SIMILARITY_THRESHOLD"]

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required."}), 400

    emb1, emb2, error = _resolve_embeddings(data, model_service)
    if error:
        return jsonify({"error": error}), 422

    similarity = cosine_similarity(emb1, emb2)
    return jsonify(
        {
            "similarity": round(similarity, 6),
            "verified": similarity >= threshold,
        }
    )


def _resolve_embeddings(data: dict, model_service):
    """Return (emb1, emb2, error_string)."""

    # Mode C – two raw embeddings
    if "embedding1" in data and "embedding2" in data:
        try:
            e1 = np.array(data["embedding1"], dtype=np.float32)
            e2 = np.array(data["embedding2"], dtype=np.float32)
            return e1, e2, None
        except Exception:
            return None, None, "Invalid embedding format."

    # Mode B – one image + one embedding
    if "image" in data and "embedding" in data:
        img = decode_base64_image(data["image"])
        if img is None:
            return None, None, "Could not decode 'image'."
        emb_img = model_service.get_embedding(img)
        if emb_img is None:
            return None, None, "No face detected in 'image'."
        try:
            emb_ref = np.array(data["embedding"], dtype=np.float32)
        except Exception:
            return None, None, "Invalid 'embedding' format."
        return emb_img, emb_ref, None

    # Mode A – two base64 images
    if "image1" in data and "image2" in data:
        img1 = decode_base64_image(data["image1"])
        img2 = decode_base64_image(data["image2"])
        if img1 is None or img2 is None:
            return None, None, "Could not decode one or both images."
        e1 = model_service.get_embedding(img1)
        e2 = model_service.get_embedding(img2)
        if e1 is None:
            return None, None, "No face detected in 'image1'."
        if e2 is None:
            return None, None, "No face detected in 'image2'."
        return e1, e2, None

    return None, None, "Provide (embedding1+embedding2) or (image+embedding) or (image1+image2)."