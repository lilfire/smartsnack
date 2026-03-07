import logging

from flask import Flask, jsonify

from db import init_db, close_db
from blueprints import register_blueprints

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_app():
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

    app.teardown_appcontext(close_db)

    register_blueprints(app)

    @app.errorhandler(Exception)
    def handle_error(e):
        logger.error(f"Unhandled error: {e}", exc_info=True)
        return jsonify({"error": "An internal error occurred"}), 500

    return app


try:
    init_db()
except Exception as e:
    logger.error(f"Failed to initialize database: {e}")

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
