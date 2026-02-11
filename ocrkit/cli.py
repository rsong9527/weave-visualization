"""
cli.py — Command-line interface for OCRKit.

Usage:
    python -m ocrkit image.png                    # Print JSON to stdout
    python -m ocrkit image.png -o result.json     # Save to file
    python -m ocrkit image.png --annotate out.png # Save annotated image
    python -m ocrkit image.png --viewer           # Launch web viewer
    python -m ocrkit --serve result.json          # Serve existing JSON in viewer
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ocrkit",
        description="OCRKit — Lightweight OCR + UI structure extraction",
    )
    parser.add_argument(
        "image",
        nargs="?",
        help="Path to the input image (PNG, JPEG, BMP, TIFF, etc.)",
    )
    parser.add_argument(
        "-o", "--output",
        help="Save JSON output to this file (default: print to stdout).",
    )
    parser.add_argument(
        "--annotate",
        metavar="FILE",
        help="Save an annotated image with bounding boxes to FILE.",
    )
    parser.add_argument(
        "--lang",
        default="eng",
        help="Tesseract language code (default: eng). Examples: chi_sim, eng+chi_sim.",
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=30.0,
        help="Minimum OCR confidence 0-100 (default: 30).",
    )
    parser.add_argument(
        "--app-name",
        help="Application name to include in the output JSON.",
    )
    parser.add_argument(
        "--raw-text",
        action="store_true",
        help="Include raw OCR text in the JSON output.",
    )
    parser.add_argument(
        "--viewer",
        action="store_true",
        help="Launch the web viewer after processing.",
    )
    parser.add_argument(
        "--serve",
        metavar="JSON_FILE",
        help="Serve an existing JSON file in the web viewer (no OCR).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5678,
        help="Port for the web viewer (default: 5678).",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host for the web viewer (default: 0.0.0.0).",
    )

    args = parser.parse_args(argv)

    # --- Serve existing JSON ---
    if args.serve:
        return _serve_json(args.serve, args.host, args.port)

    # --- Need an image for OCR ---
    if not args.image:
        parser.print_help()
        print("\nError: Please provide an image path or use --serve.", file=sys.stderr)
        return 1

    image_path = Path(args.image)
    if not image_path.exists():
        print(f"Error: Image not found: {image_path}", file=sys.stderr)
        return 1

    # --- Run pipeline ---
    from ocrkit.pipeline import OCRKitPipeline

    pipeline = OCRKitPipeline(
        lang=args.lang,
        min_confidence=args.min_confidence,
    )

    print(f"Processing: {image_path}", file=sys.stderr)
    result = pipeline.process_image(
        image_path,
        app_name=args.app_name,
        include_raw_text=args.raw_text,
    )

    json_str = json.dumps(result, indent=2, ensure_ascii=False)

    # --- Save or print JSON ---
    if args.output:
        out_path = Path(args.output)
        out_path.write_text(json_str, encoding="utf-8")
        print(f"JSON saved to: {out_path}", file=sys.stderr)
    else:
        print(json_str)

    # --- Annotated image ---
    if args.annotate:
        from ocrkit.capture import load_image
        from ocrkit.aggregator import aggregate
        from ocrkit.ocr_engine import run_ocr
        from ocrkit.visualize import draw_blocks

        image = load_image(image_path)
        words = run_ocr(image, lang=args.lang, min_confidence=args.min_confidence)
        blocks = aggregate(words, image_width=image.size[0], image_height=image.size[1])
        annotated = draw_blocks(image, blocks)
        annotated.save(args.annotate)
        print(f"Annotated image saved to: {args.annotate}", file=sys.stderr)

    # --- Web viewer ---
    if args.viewer:
        # Save temp JSON and serve
        import tempfile

        tmp = Path(tempfile.mktemp(suffix=".json", prefix="ocrkit_"))
        tmp.write_text(json_str, encoding="utf-8")

        # Also save annotated image for viewer
        annotated_path = None
        if not args.annotate:
            from ocrkit.capture import load_image
            from ocrkit.aggregator import aggregate
            from ocrkit.ocr_engine import run_ocr
            from ocrkit.visualize import draw_blocks

            image = load_image(image_path)
            words = run_ocr(image, lang=args.lang, min_confidence=args.min_confidence)
            blocks = aggregate(words, image_width=image.size[0], image_height=image.size[1])
            annotated = draw_blocks(image, blocks)
            annotated_path = str(tmp).replace(".json", "_annotated.png")
            annotated.save(annotated_path)
        else:
            annotated_path = args.annotate

        return _serve_json(
            str(tmp),
            args.host,
            args.port,
            original_image=str(image_path),
            annotated_image=annotated_path,
        )

    return 0


def _serve_json(
    json_path: str,
    host: str = "0.0.0.0",
    port: int = 5678,
    original_image: str | None = None,
    annotated_image: str | None = None,
) -> int:
    """Launch the web viewer for a JSON file."""
    from ocrkit.viewer.app import create_app

    app = create_app(
        json_path=json_path,
        original_image=original_image,
        annotated_image=annotated_image,
    )
    print(f"Starting OCRKit viewer at http://{host}:{port}", file=sys.stderr)
    app.run(host=host, port=port, debug=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
