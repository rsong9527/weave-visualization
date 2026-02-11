"""
ocr_engine.py — OCR text extraction with bounding-box information.

Uses Tesseract (via pytesseract) to extract words/lines with their
positions, confidence scores, and block/paragraph grouping.
"""

from __future__ import annotations

import dataclasses
from typing import Optional

import pytesseract
from PIL import Image


@dataclasses.dataclass
class OCRWord:
    """A single word detected by OCR."""

    text: str
    confidence: float  # 0-100
    x: int
    y: int
    width: int
    height: int
    block_num: int
    par_num: int
    line_num: int
    word_num: int

    @property
    def cx(self) -> float:
        return self.x + self.width / 2

    @property
    def cy(self) -> float:
        return self.y + self.height / 2

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height

    @property
    def bbox(self) -> tuple[int, int, int, int]:
        """(x, y, x2, y2)"""
        return (self.x, self.y, self.right, self.bottom)

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "confidence": round(self.confidence, 1),
            "position": [self.x, self.y],
            "size": [self.width, self.height],
        }


def run_ocr(
    image: Image.Image,
    lang: str = "eng",
    min_confidence: float = 30.0,
    config: str = "",
) -> list[OCRWord]:
    """Run Tesseract OCR and return structured word-level results.

    Args:
        image: PIL Image to process.
        lang: Tesseract language code (e.g. 'eng', 'chi_sim', 'eng+chi_sim').
        min_confidence: Minimum confidence threshold (0-100).
        config: Extra Tesseract config flags.

    Returns:
        List of OCRWord objects sorted top-to-bottom, left-to-right.
    """
    data = pytesseract.image_to_data(image, lang=lang, config=config, output_type=pytesseract.Output.DICT)

    words: list[OCRWord] = []
    n = len(data["text"])

    for i in range(n):
        text = data["text"][i].strip()
        if not text:
            continue
        conf = float(data["conf"][i])
        if conf < min_confidence:
            continue

        words.append(
            OCRWord(
                text=text,
                confidence=conf,
                x=int(data["left"][i]),
                y=int(data["top"][i]),
                width=int(data["width"][i]),
                height=int(data["height"][i]),
                block_num=int(data["block_num"][i]),
                par_num=int(data["par_num"][i]),
                line_num=int(data["line_num"][i]),
                word_num=int(data["word_num"][i]),
            )
        )

    # Sort by vertical then horizontal position
    words.sort(key=lambda w: (w.y, w.x))
    return words


def run_ocr_simple(
    image: Image.Image,
    lang: str = "eng",
    config: str = "",
) -> str:
    """Run Tesseract OCR and return plain text."""
    return pytesseract.image_to_string(image, lang=lang, config=config).strip()
