"""
app.py — Flask web viewer for OCRKit results.

Provides:
  - JSON tree view with syntax highlighting
  - Original / annotated image comparison
  - Block inspector with click-to-highlight
  - REST API for programmatic access
"""

from __future__ import annotations

import json
import base64
from pathlib import Path
from typing import Optional

from flask import Flask, render_template, jsonify, send_file, request


def create_app(
    json_path: Optional[str] = None,
    original_image: Optional[str] = None,
    annotated_image: Optional[str] = None,
) -> Flask:
    """Create and configure the Flask viewer app."""

    app = Flask(
        __name__,
        template_folder=str(Path(__file__).parent / "templates"),
        static_folder=str(Path(__file__).parent / "static"),
    )

    # Store data in app config
    app.config["OCRKIT_JSON_PATH"] = json_path
    app.config["OCRKIT_ORIGINAL_IMAGE"] = original_image
    app.config["OCRKIT_ANNOTATED_IMAGE"] = annotated_image

    @app.route("/")
    def index():
        """Main viewer page."""
        data = _load_json(json_path)
        return render_template(
            "viewer.html",
            data=data,
            json_str=json.dumps(data, indent=2, ensure_ascii=False),
            has_original=original_image is not None and Path(original_image).exists(),
            has_annotated=annotated_image is not None and Path(annotated_image).exists(),
        )

    @app.route("/api/data")
    def api_data():
        """Return the OCR result as JSON."""
        data = _load_json(json_path)
        return jsonify(data)

    @app.route("/api/blocks")
    def api_blocks():
        """Return just the blocks array."""
        data = _load_json(json_path)
        return jsonify(data.get("blocks", []))

    @app.route("/api/image/original")
    def api_original_image():
        """Serve the original image."""
        if original_image and Path(original_image).exists():
            return send_file(original_image)
        return "No image", 404

    @app.route("/api/image/annotated")
    def api_annotated_image():
        """Serve the annotated image."""
        if annotated_image and Path(annotated_image).exists():
            return send_file(annotated_image)
        return "No image", 404

    @app.route("/api/process", methods=["POST"])
    def api_process():
        """Process an uploaded image via the API."""
        if "image" not in request.files:
            return jsonify({"error": "No image file provided"}), 400

        file = request.files["image"]
        from PIL import Image
        import io
        from ocrkit.pipeline import OCRKitPipeline

        img_bytes = file.read()
        image = Image.open(io.BytesIO(img_bytes)).convert("RGB")

        lang = request.form.get("lang", "eng")
        app_name = request.form.get("app_name", file.filename or "upload")

        pipeline = OCRKitPipeline(lang=lang)
        result = pipeline.process_image(image, app_name=app_name)

        return jsonify(result)

    return app


def _load_json(json_path: Optional[str]) -> dict:
    """Load JSON data from file."""
    if json_path and Path(json_path).exists():
        return json.loads(Path(json_path).read_text(encoding="utf-8"))
    return {"app": "unknown", "blocks": [], "stats": {"total_blocks": 0}}
