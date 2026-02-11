"""
visualize.py — Draw bounding boxes and labels on images for debugging.

Produces an annotated image showing detected UI blocks with color-coded
bounding boxes by type.
"""

from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont

from ocrkit.aggregator import UIBlock

# Color palette by block type (R, G, B, A)
TYPE_COLORS: dict[str, tuple[int, int, int]] = {
    "heading": (220, 50, 50),       # red
    "text": (50, 130, 220),         # blue
    "label_value": (50, 180, 80),   # green
    "button": (230, 150, 30),       # orange
    "nav_item": (160, 50, 200),     # purple
    "list_item": (30, 180, 180),    # teal
    "caption": (150, 150, 150),     # gray
}

DEFAULT_COLOR = (100, 100, 100)


def draw_blocks(
    image: Image.Image,
    blocks: list[UIBlock],
    line_width: int = 2,
    font_size: int = 12,
    show_labels: bool = True,
    fill_alpha: int = 30,
) -> Image.Image:
    """Draw bounding boxes and type labels on a copy of the image.

    Args:
        image: Source PIL image.
        blocks: Classified UI blocks.
        line_width: Bounding box line width.
        font_size: Label font size.
        show_labels: Whether to draw type labels.
        fill_alpha: Alpha value for the box fill (0-255).

    Returns:
        Annotated copy of the image.
    """
    # Work on a copy in RGBA for semi-transparent fills
    canvas = image.convert("RGBA")
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw_overlay = ImageDraw.Draw(overlay)
    draw_main = ImageDraw.Draw(canvas)

    # Try to get a reasonable font
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", font_size)
    except (OSError, IOError):
        font = ImageFont.load_default()

    for block in blocks:
        color = TYPE_COLORS.get(block.block_type, DEFAULT_COLOR)
        fill_color = (*color, fill_alpha)
        x1, y1 = block.x, block.y
        x2, y2 = block.right, block.bottom

        # Semi-transparent fill
        draw_overlay.rectangle([x1, y1, x2, y2], fill=fill_color)

        # Solid border
        draw_main.rectangle([x1, y1, x2, y2], outline=color, width=line_width)

        # Type label
        if show_labels:
            label = block.block_type.replace("_", " ")
            if block.block_type == "label_value" and block.label:
                label = f"[{block.label}]"

            # Background for label text
            bbox = font.getbbox(label)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            label_y = max(0, y1 - th - 4)
            draw_main.rectangle(
                [x1, label_y, x1 + tw + 6, label_y + th + 4],
                fill=color,
            )
            draw_main.text((x1 + 3, label_y + 1), label, fill=(255, 255, 255), font=font)

    # Composite overlay
    result = Image.alpha_composite(canvas, overlay)
    return result.convert("RGB")
