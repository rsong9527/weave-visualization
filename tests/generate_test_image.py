"""Generate a synthetic UI screenshot for testing OCRKit."""

from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

WIDTH = 1280
HEIGHT = 800
BG = (245, 245, 250)
TEXT_COLOR = (30, 30, 40)
ACCENT = (60, 120, 220)
BORDER = (200, 200, 210)
BUTTON_BG = (60, 120, 220)
BUTTON_TEXT = (255, 255, 255)
LABEL_COLOR = (100, 100, 110)

try:
    font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
    font_medium = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
    font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
    font_button = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
    font_nav = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 15)
except (OSError, IOError):
    font_large = ImageFont.load_default()
    font_medium = font_large
    font_small = font_large
    font_button = font_large
    font_nav = font_large


def draw_test_ui():
    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(img)

    # --- Title bar (nav) ---
    draw.rectangle([0, 0, WIDTH, 50], fill=(35, 40, 55))
    nav_items = ["File", "Edit", "View", "Window", "Help"]
    x = 20
    for item in nav_items:
        draw.text((x, 15), item, fill=(200, 200, 215), font=font_nav)
        x += 80

    # --- Page Title ---
    draw.text((40, 80), "Document Manager", fill=TEXT_COLOR, font=font_large)

    # --- Info section with label:value pairs ---
    y = 140
    info = [
        ("File name", "annual_report_2025.pdf"),
        ("File size", "2.4 MB"),
        ("Created", "2026-01-15 09:30:00"),
        ("Author", "John Smith"),
        ("Status", "Published"),
    ]
    for label, value in info:
        draw.text((60, y), f"{label}:", fill=LABEL_COLOR, font=font_small)
        draw.text((200, y), value, fill=TEXT_COLOR, font=font_small)
        y += 30

    # --- Description text block ---
    y += 20
    draw.text((60, y), "Description", fill=TEXT_COLOR, font=font_medium)
    y += 30
    desc_lines = [
        "This document contains the annual financial report for fiscal year 2025.",
        "It includes revenue projections, expense breakdowns, and strategic",
        "planning outcomes for all regional divisions.",
    ]
    for line in desc_lines:
        draw.text((60, y), line, fill=TEXT_COLOR, font=font_small)
        y += 22

    # --- Buttons ---
    y += 30
    buttons = ["Download", "Edit", "Delete", "Share"]
    bx = 60
    for btn_text in buttons:
        bbox = font_button.getbbox(btn_text)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        pad_x, pad_y = 20, 10
        draw.rounded_rectangle(
            [bx, y, bx + tw + pad_x * 2, y + th + pad_y * 2],
            radius=6,
            fill=BUTTON_BG if btn_text == "Download" else BG,
            outline=BUTTON_BG,
            width=2,
        )
        draw.text(
            (bx + pad_x, y + pad_y),
            btn_text,
            fill=BUTTON_TEXT if btn_text == "Download" else ACCENT,
            font=font_button,
        )
        bx += tw + pad_x * 2 + 16

    # --- List items ---
    y += 80
    draw.text((60, y), "Recent Activity", fill=TEXT_COLOR, font=font_medium)
    y += 30
    activities = [
        "1. File uploaded by admin on 2026-01-15",
        "2. Reviewed by finance team on 2026-01-20",
        "3. Published to portal on 2026-02-01",
    ]
    for act in activities:
        draw.text((60, y), act, fill=TEXT_COLOR, font=font_small)
        y += 24

    # --- Caption at bottom ---
    draw.text(
        (40, HEIGHT - 35),
        "OCRKit Test Image - Generated for testing purposes",
        fill=(150, 150, 160),
        font=font_small,
    )

    return img


if __name__ == "__main__":
    out_dir = Path(__file__).parent
    img = draw_test_ui()
    out_path = out_dir / "test_ui_screenshot.png"
    img.save(out_path)
    print(f"Test image saved to: {out_path}")
