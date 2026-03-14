from flask import Blueprint, current_app, jsonify

health_bp = Blueprint("health", __name__)


@health_bp.get("/health")
def health():
    """Returns service status and model readiness."""
    model_service = current_app.config.get("MODEL_SERVICE")
    ready = model_service is not None and getattr(model_service, "model_loaded", False)
    payload = {
        "status": "ok" if ready else "degraded",
        "model_loaded": ready,
    }
    return jsonify(payload), 200 if ready else 503