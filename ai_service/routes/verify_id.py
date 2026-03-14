"""
POST /verify-id
---------------
Compare the face on an identity document with a live selfie.

Input  : multipart/form-data
           id_card  – image of the identity document (JPEG / PNG)
           selfie   – live capture image

Output : { "similarity": float, "verified": bool, "message": str }
         { "error": "..." }   on failure
"""

from flask import Blueprint, current_app, jsonify, request

from services.image_utils import decode_image_bytes
from services.similarity import cosine_similarity

verify_id_bp = Blueprint("verify_id", __name__)


@verify_id_bp.post("/verify-id")
def verify_id():
    model_service = current_app.config["MODEL_SERVICE"]
    threshold: float = current_app.config["SIMILARITY_THRESHOLD"]

    # ── Input validation ───────────────────────────────────────────────────────
    if "id_card" not in request.files or "selfie" not in request.files:
        return jsonify({"error": "Both 'id_card' and 'selfie' file fields are required."}), 400

    id_card_bytes = request.files["id_card"].read()
    selfie_bytes = request.files["selfie"].read()

    id_card_image = decode_image_bytes(id_card_bytes)
    selfie_image = decode_image_bytes(selfie_bytes)

    if id_card_image is None:
        return jsonify({"error": "Could not decode 'id_card' image."}), 400
    if selfie_image is None:
        return jsonify({"error": "Could not decode 'selfie' image."}), 400

    # ── Extract embeddings ─────────────────────────────────────────────────────
    emb_id = model_service.get_embedding(id_card_image)
    if emb_id is None:
        return jsonify(
            {
                "error": "No face detected in the identity document.",
                "verified": False,
                "similarity": 0.0,
                "message": "The identity document image does not contain a detectable face.",
            }
        ), 422

    emb_selfie = model_service.get_embedding(selfie_image)
    if emb_selfie is None:
        return jsonify(
            {
                "error": "No face detected in the selfie.",
                "verified": False,
                "similarity": 0.0,
                "message": "The selfie image does not contain a detectable face.",
            }
        ), 422

    # ── Compare ────────────────────────────────────────────────────────────────
    similarity = cosine_similarity(emb_id, emb_selfie)
    verified = similarity >= threshold

    message = (
        "Identity verification successful: the selfie matches the identity document."
        if verified
        else "Identity verification failed: the selfie does not match the identity document."
    )

    return jsonify(
        {
            "similarity": round(similarity, 6),
            "verified": verified,
            "message": message,
        }
    )