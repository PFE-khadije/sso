
import logging
import os

from flask import Flask
from routes.health import health_bp
from routes.detect import detect_bp
from routes.embed import embed_bp
from routes.verify import verify_bp
from routes.verify_id import verify_id_bp
from models import ModelService
#from routes.liveness import liveness_bp


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)


def create_app() -> Flask:
    app = Flask(__name__)

    # ── Configuration ──────────────────────────────────────────────────────────
    app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("MAX_CONTENT_LENGTH", 16 * 1024 * 1024))  # 16 MB
    app.config["SIMILARITY_THRESHOLD"] = float(os.getenv("SIMILARITY_THRESHOLD", 0.70))
    app.config["ONNX_MODEL_PATH"] = os.getenv("ONNX_MODEL_PATH", "models/facenet.onnx")

    # ── Load ML models once at startup ─────────────────────────────────────────
    logger.info("Loading ML models …")
    model_service = ModelService(onnx_model_path=app.config["ONNX_MODEL_PATH"])
    app.config["MODEL_SERVICE"] = model_service
    logger.info("Models loaded successfully.")

    # ── Register blueprints ────────────────────────────────────────────────────
    app.register_blueprint(health_bp)
    app.register_blueprint(detect_bp)
    app.register_blueprint(embed_bp)
    app.register_blueprint(verify_bp)
    app.register_blueprint(verify_id_bp)
    #app.register_blueprint(liveness_bp)

    return app


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5001))
    app = create_app()
    app.run(host="0.0.0.0", port=port, debug=False)