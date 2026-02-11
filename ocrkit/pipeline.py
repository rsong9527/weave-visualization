"""
pipeline.py — End-to-end OCRKit pipeline.

Orchestrates: Image → OCR → Aggregate → Format → JSON
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Union

from PIL import Image

from ocrkit.capture import load_image
from ocrkit.ocr_engine import OCRWord, run_ocr
from ocrkit.aggregator import UIBlock, aggregate
from ocrkit.formatter import format_blocks, format_blocks_json


class OCRKitPipeline:
    """High-level API for running the full OCRKit pipeline."""

    def __init__(
        self,
        lang: str = "eng",
        min_confidence: float = 30.0,
        tesseract_config: str = "",
        vertical_gap_factor: float = 1.8,
        horizontal_overlap_ratio: float = 0.3,
    ):
        """Initialize pipeline configuration.

        Args:
            lang: Tesseract language code (e.g. 'eng', 'chi_sim', 'eng+chi_sim').
            min_confidence: Minimum OCR confidence threshold (0-100).
            tesseract_config: Extra Tesseract flags.
            vertical_gap_factor: Controls vertical merging aggressiveness.
            horizontal_overlap_ratio: Controls horizontal overlap for merging.
        """
        self.lang = lang
        self.min_confidence = min_confidence
        self.tesseract_config = tesseract_config
        self.vertical_gap_factor = vertical_gap_factor
        self.horizontal_overlap_ratio = horizontal_overlap_ratio

    def process_image(
        self,
        source: Union[str, Path, bytes, Image.Image],
        app_name: Optional[str] = None,
        include_raw_text: bool = False,
    ) -> dict:
        """Run the full pipeline on an image.

        Args:
            source: Image path, bytes, or PIL Image.
            app_name: Application name to include in output.
            include_raw_text: Whether to include raw OCR text.

        Returns:
            Structured JSON dict with detected UI blocks.
        """
        # 1. Load image
        image = load_image(source)
        w, h = image.size
        source_file = str(source) if isinstance(source, (str, Path)) else None

        # 2. OCR
        words = run_ocr(
            image,
            lang=self.lang,
            min_confidence=self.min_confidence,
            config=self.tesseract_config,
        )

        # 3. Aggregate
        blocks = aggregate(
            words,
            image_width=w,
            image_height=h,
            vertical_gap_factor=self.vertical_gap_factor,
            horizontal_overlap_ratio=self.horizontal_overlap_ratio,
        )

        # 4. Format
        result = format_blocks(
            blocks,
            app_name=app_name,
            source_file=source_file,
            image_width=w,
            image_height=h,
            include_raw_text=include_raw_text,
        )

        return result

    def process_image_json(
        self,
        source: Union[str, Path, bytes, Image.Image],
        indent: int = 2,
        **kwargs,
    ) -> str:
        """Run the full pipeline and return a JSON string."""
        result = self.process_image(source, **kwargs)
        return json.dumps(result, indent=indent, ensure_ascii=False)

    def process_and_save(
        self,
        source: Union[str, Path, bytes, Image.Image],
        output_path: Union[str, Path] = "ocrkit_output.json",
        **kwargs,
    ) -> Path:
        """Run the pipeline and save output to a JSON file.

        Returns:
            Path to the saved JSON file.
        """
        result = self.process_image(source, **kwargs)
        out = Path(output_path)
        out.write_text(
            json.dumps(result, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return out

    # -----------------------------------------------------------------------
    # Lower-level access for advanced usage
    # -----------------------------------------------------------------------

    def extract_words(
        self, source: Union[str, Path, bytes, Image.Image]
    ) -> tuple[Image.Image, list[OCRWord]]:
        """Run only the OCR step. Returns (image, words)."""
        image = load_image(source)
        words = run_ocr(
            image,
            lang=self.lang,
            min_confidence=self.min_confidence,
            config=self.tesseract_config,
        )
        return image, words

    def extract_blocks(
        self, source: Union[str, Path, bytes, Image.Image]
    ) -> tuple[Image.Image, list[UIBlock]]:
        """Run OCR + aggregation. Returns (image, blocks)."""
        image, words = self.extract_words(source)
        w, h = image.size
        blocks = aggregate(
            words,
            image_width=w,
            image_height=h,
            vertical_gap_factor=self.vertical_gap_factor,
            horizontal_overlap_ratio=self.horizontal_overlap_ratio,
        )
        return image, blocks
