"""
capture.py — Image / screenshot acquisition module.

Supports:
  - Loading an image from disk (PNG, JPEG, BMP, TIFF …)
  - Taking a screenshot of the current display (Linux/macOS)
  - Fetching a screenshot from a URL
"""

from __future__ import annotations

import io
import platform
from pathlib import Path
from typing import Optional, Union

from PIL import Image


def load_image(source: Union[str, Path, bytes, Image.Image]) -> Image.Image:
    """Load an image from various source types.

    Args:
        source: A file path (str/Path), raw bytes, or an already-opened PIL Image.

    Returns:
        A PIL Image in RGB mode.
    """
    if isinstance(source, Image.Image):
        return source.convert("RGB")

    if isinstance(source, bytes):
        return Image.open(io.BytesIO(source)).convert("RGB")

    path = Path(source)
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {path}")
    return Image.open(path).convert("RGB")


def take_screenshot(region: Optional[tuple[int, int, int, int]] = None) -> Image.Image:
    """Capture a screenshot of the current display.

    Args:
        region: Optional (x, y, width, height) to capture a sub-region.

    Returns:
        A PIL Image of the screenshot.

    Note:
        Requires a display. On headless servers this will raise an error.
        On macOS uses screencapture, on Linux uses PIL.ImageGrab or scrot.
    """
    system = platform.system()

    if system == "Darwin":
        import subprocess
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = tmp.name
        cmd = ["screencapture", "-x"]  # -x = no sound
        if region:
            x, y, w, h = region
            cmd.extend(["-R", f"{x},{y},{w},{h}"])
        cmd.append(tmp_path)
        subprocess.run(cmd, check=True)
        img = Image.open(tmp_path).convert("RGB")
        Path(tmp_path).unlink(missing_ok=True)
        return img

    # Linux fallback — requires a display or Xvfb
    try:
        from PIL import ImageGrab

        img = ImageGrab.grab(bbox=region)
        return img.convert("RGB")
    except Exception:
        # Try scrot as last resort
        import subprocess
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = tmp.name
        subprocess.run(["scrot", tmp_path], check=True)
        img = Image.open(tmp_path).convert("RGB")
        Path(tmp_path).unlink(missing_ok=True)
        if region:
            img = img.crop(region)
        return img


def fetch_url_screenshot(url: str, width: int = 1280, height: int = 800) -> Image.Image:
    """Take a screenshot of a web page using a headless browser.

    Requires playwright or selenium to be installed.

    Args:
        url: The URL to screenshot.
        width: Viewport width.
        height: Viewport height.

    Returns:
        A PIL Image of the web page.
    """
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": width, "height": height})
            page.goto(url, wait_until="networkidle")
            screenshot_bytes = page.screenshot(full_page=False)
            browser.close()
            return Image.open(io.BytesIO(screenshot_bytes)).convert("RGB")
    except ImportError:
        raise ImportError(
            "Web screenshot requires playwright. "
            "Install with: pip install playwright && playwright install chromium"
        )
