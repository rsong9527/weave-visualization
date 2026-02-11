"""
Tests for OCRKit core modules.

Run with: python -m pytest tests/test_ocrkit.py -v
"""

import json
from pathlib import Path

import pytest
from PIL import Image

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TESTS_DIR = Path(__file__).parent
TEST_IMAGE = TESTS_DIR / "test_ui_screenshot.png"


@pytest.fixture(scope="session", autouse=True)
def ensure_test_image():
    """Generate the test image if it doesn't exist."""
    if not TEST_IMAGE.exists():
        from tests.generate_test_image import draw_test_ui
        img = draw_test_ui()
        img.save(TEST_IMAGE)
    return TEST_IMAGE


# ---------------------------------------------------------------------------
# capture.py tests
# ---------------------------------------------------------------------------

class TestCapture:
    def test_load_image_from_path(self):
        from ocrkit.capture import load_image
        img = load_image(TEST_IMAGE)
        assert isinstance(img, Image.Image)
        assert img.mode == "RGB"
        assert img.size == (1280, 800)

    def test_load_image_from_string_path(self):
        from ocrkit.capture import load_image
        img = load_image(str(TEST_IMAGE))
        assert img.size == (1280, 800)

    def test_load_image_from_bytes(self):
        from ocrkit.capture import load_image
        raw = TEST_IMAGE.read_bytes()
        img = load_image(raw)
        assert isinstance(img, Image.Image)
        assert img.size == (1280, 800)

    def test_load_image_from_pil(self):
        from ocrkit.capture import load_image
        pil_img = Image.new("RGBA", (100, 100), "red")
        img = load_image(pil_img)
        assert img.mode == "RGB"  # Converted from RGBA

    def test_load_image_not_found(self):
        from ocrkit.capture import load_image
        with pytest.raises(FileNotFoundError):
            load_image("/nonexistent/image.png")


# ---------------------------------------------------------------------------
# ocr_engine.py tests
# ---------------------------------------------------------------------------

class TestOCREngine:
    def test_run_ocr_returns_words(self):
        from ocrkit.capture import load_image
        from ocrkit.ocr_engine import run_ocr
        img = load_image(TEST_IMAGE)
        words = run_ocr(img)
        assert len(words) > 0
        # Check word structure
        w = words[0]
        assert hasattr(w, "text")
        assert hasattr(w, "confidence")
        assert hasattr(w, "x")
        assert hasattr(w, "y")
        assert hasattr(w, "width")
        assert hasattr(w, "height")

    def test_run_ocr_finds_key_text(self):
        from ocrkit.capture import load_image
        from ocrkit.ocr_engine import run_ocr
        img = load_image(TEST_IMAGE)
        words = run_ocr(img)
        all_text = " ".join(w.text for w in words).lower()
        assert "document" in all_text
        assert "manager" in all_text
        assert "download" in all_text

    def test_run_ocr_simple(self):
        from ocrkit.capture import load_image
        from ocrkit.ocr_engine import run_ocr_simple
        img = load_image(TEST_IMAGE)
        text = run_ocr_simple(img)
        assert "Document Manager" in text

    def test_confidence_filtering(self):
        from ocrkit.capture import load_image
        from ocrkit.ocr_engine import run_ocr
        img = load_image(TEST_IMAGE)
        words_low = run_ocr(img, min_confidence=10)
        words_high = run_ocr(img, min_confidence=90)
        assert len(words_low) >= len(words_high)

    def test_word_properties(self):
        from ocrkit.capture import load_image
        from ocrkit.ocr_engine import run_ocr
        img = load_image(TEST_IMAGE)
        words = run_ocr(img)
        w = words[0]
        assert w.right == w.x + w.width
        assert w.bottom == w.y + w.height
        assert w.bbox == (w.x, w.y, w.right, w.bottom)
        d = w.to_dict()
        assert "text" in d
        assert "position" in d


# ---------------------------------------------------------------------------
# aggregator.py tests
# ---------------------------------------------------------------------------

class TestAggregator:
    def test_aggregate_produces_blocks(self):
        from ocrkit.capture import load_image
        from ocrkit.ocr_engine import run_ocr
        from ocrkit.aggregator import aggregate
        img = load_image(TEST_IMAGE)
        words = run_ocr(img)
        blocks = aggregate(words, image_width=1280, image_height=800)
        assert len(blocks) > 0

    def test_heading_detected(self):
        from ocrkit.capture import load_image
        from ocrkit.ocr_engine import run_ocr
        from ocrkit.aggregator import aggregate
        img = load_image(TEST_IMAGE)
        words = run_ocr(img)
        blocks = aggregate(words, image_width=1280, image_height=800)
        types = [b.block_type for b in blocks]
        assert "heading" in types

    def test_button_detected(self):
        from ocrkit.capture import load_image
        from ocrkit.ocr_engine import run_ocr
        from ocrkit.aggregator import aggregate
        img = load_image(TEST_IMAGE)
        words = run_ocr(img)
        blocks = aggregate(words, image_width=1280, image_height=800)
        types = [b.block_type for b in blocks]
        assert "button" in types

    def test_block_has_position_and_size(self):
        from ocrkit.capture import load_image
        from ocrkit.ocr_engine import run_ocr
        from ocrkit.aggregator import aggregate
        img = load_image(TEST_IMAGE)
        words = run_ocr(img)
        blocks = aggregate(words, image_width=1280, image_height=800)
        for b in blocks:
            assert len(b.position) == 2
            assert len(b.size) == 2
            assert b.width > 0
            assert b.height > 0

    def test_empty_input(self):
        from ocrkit.aggregator import aggregate
        assert aggregate([]) == []


# ---------------------------------------------------------------------------
# formatter.py tests
# ---------------------------------------------------------------------------

class TestFormatter:
    def test_format_blocks_structure(self):
        from ocrkit.capture import load_image
        from ocrkit.ocr_engine import run_ocr
        from ocrkit.aggregator import aggregate
        from ocrkit.formatter import format_blocks
        img = load_image(TEST_IMAGE)
        words = run_ocr(img)
        blocks = aggregate(words, image_width=1280, image_height=800)
        result = format_blocks(blocks, app_name="Test", image_width=1280, image_height=800)

        assert "app" in result
        assert result["app"] == "Test"
        assert "blocks" in result
        assert "timestamp" in result
        assert "stats" in result
        assert result["stats"]["total_blocks"] == len(blocks)

    def test_format_blocks_json_is_valid(self):
        from ocrkit.capture import load_image
        from ocrkit.ocr_engine import run_ocr
        from ocrkit.aggregator import aggregate
        from ocrkit.formatter import format_blocks_json
        img = load_image(TEST_IMAGE)
        words = run_ocr(img)
        blocks = aggregate(words, image_width=1280, image_height=800)
        json_str = format_blocks_json(blocks, app_name="Test")
        data = json.loads(json_str)  # Should not raise
        assert isinstance(data, dict)

    def test_include_raw_text(self):
        from ocrkit.capture import load_image
        from ocrkit.ocr_engine import run_ocr
        from ocrkit.aggregator import aggregate
        from ocrkit.formatter import format_blocks
        img = load_image(TEST_IMAGE)
        words = run_ocr(img)
        blocks = aggregate(words, image_width=1280, image_height=800)
        result = format_blocks(blocks, include_raw_text=True)
        assert "raw_text" in result
        assert len(result["raw_text"]) > 0


# ---------------------------------------------------------------------------
# pipeline.py tests
# ---------------------------------------------------------------------------

class TestPipeline:
    def test_pipeline_process_image(self):
        from ocrkit.pipeline import OCRKitPipeline
        pipeline = OCRKitPipeline()
        result = pipeline.process_image(TEST_IMAGE, app_name="Test")
        assert result["app"] == "Test"
        assert len(result["blocks"]) > 0

    def test_pipeline_process_image_json(self):
        from ocrkit.pipeline import OCRKitPipeline
        pipeline = OCRKitPipeline()
        json_str = pipeline.process_image_json(TEST_IMAGE)
        data = json.loads(json_str)
        assert "blocks" in data

    def test_pipeline_process_and_save(self, tmp_path):
        from ocrkit.pipeline import OCRKitPipeline
        pipeline = OCRKitPipeline()
        out = pipeline.process_and_save(TEST_IMAGE, output_path=tmp_path / "out.json")
        assert out.exists()
        data = json.loads(out.read_text())
        assert "blocks" in data

    def test_pipeline_extract_words(self):
        from ocrkit.pipeline import OCRKitPipeline
        pipeline = OCRKitPipeline()
        img, words = pipeline.extract_words(TEST_IMAGE)
        assert len(words) > 0
        assert img.size == (1280, 800)

    def test_pipeline_extract_blocks(self):
        from ocrkit.pipeline import OCRKitPipeline
        pipeline = OCRKitPipeline()
        img, blocks = pipeline.extract_blocks(TEST_IMAGE)
        assert len(blocks) > 0

    def test_pipeline_chinese_lang(self):
        """Test that Chinese language config doesn't crash."""
        from ocrkit.pipeline import OCRKitPipeline
        pipeline = OCRKitPipeline(lang="eng+chi_sim")
        result = pipeline.process_image(TEST_IMAGE)
        assert "blocks" in result


# ---------------------------------------------------------------------------
# visualize.py tests
# ---------------------------------------------------------------------------

class TestVisualize:
    def test_draw_blocks(self):
        from ocrkit.capture import load_image
        from ocrkit.ocr_engine import run_ocr
        from ocrkit.aggregator import aggregate
        from ocrkit.visualize import draw_blocks
        img = load_image(TEST_IMAGE)
        words = run_ocr(img)
        blocks = aggregate(words, image_width=1280, image_height=800)
        annotated = draw_blocks(img, blocks)
        assert isinstance(annotated, Image.Image)
        assert annotated.size == (1280, 800)
        assert annotated.mode == "RGB"

    def test_draw_blocks_empty(self):
        from ocrkit.visualize import draw_blocks
        img = Image.new("RGB", (100, 100), "white")
        result = draw_blocks(img, [])
        assert result.size == (100, 100)
