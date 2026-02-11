"""
aggregator.py — Block aggregation and UI element classification.

Groups OCR words into logical UI blocks based on:
  - Tesseract's block/paragraph/line hierarchy
  - Spatial proximity (horizontal/vertical gaps)
  - Font-size heuristics (inferred from bounding-box height)

Then classifies each block into UI element types:
  - heading, text, label+value, button, nav_item, list_item, caption
"""

from __future__ import annotations

import dataclasses
import re
from typing import Optional

from ocrkit.ocr_engine import OCRWord


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class TextLine:
    """A single line of text composed of OCR words."""

    words: list[OCRWord]

    @property
    def text(self) -> str:
        return " ".join(w.text for w in self.words)

    @property
    def x(self) -> int:
        return min(w.x for w in self.words)

    @property
    def y(self) -> int:
        return min(w.y for w in self.words)

    @property
    def right(self) -> int:
        return max(w.right for w in self.words)

    @property
    def bottom(self) -> int:
        return max(w.bottom for w in self.words)

    @property
    def width(self) -> int:
        return self.right - self.x

    @property
    def height(self) -> int:
        return self.bottom - self.y

    @property
    def avg_word_height(self) -> float:
        return sum(w.height for w in self.words) / len(self.words) if self.words else 0

    @property
    def avg_confidence(self) -> float:
        return sum(w.confidence for w in self.words) / len(self.words) if self.words else 0


@dataclasses.dataclass
class UIBlock:
    """A logical UI element composed of one or more text lines."""

    lines: list[TextLine]
    block_type: str = "text"  # heading, text, label_value, button, nav_item, list_item, caption
    label: Optional[str] = None
    value: Optional[str] = None

    @property
    def text(self) -> str:
        return "\n".join(line.text for line in self.lines)

    @property
    def x(self) -> int:
        return min(line.x for line in self.lines)

    @property
    def y(self) -> int:
        return min(line.y for line in self.lines)

    @property
    def right(self) -> int:
        return max(line.right for line in self.lines)

    @property
    def bottom(self) -> int:
        return max(line.bottom for line in self.lines)

    @property
    def width(self) -> int:
        return self.right - self.x

    @property
    def height(self) -> int:
        return self.bottom - self.y

    @property
    def position(self) -> list[int]:
        return [self.x, self.y]

    @property
    def size(self) -> list[int]:
        return [self.width, self.height]

    @property
    def avg_line_height(self) -> float:
        return sum(l.avg_word_height for l in self.lines) / len(self.lines) if self.lines else 0

    @property
    def avg_confidence(self) -> float:
        total = sum(l.avg_confidence * len(l.words) for l in self.lines)
        count = sum(len(l.words) for l in self.lines)
        return total / count if count else 0

    def to_dict(self) -> dict:
        """Serialize to spec-compatible JSON dict."""
        result: dict = {
            "type": self.block_type,
            "position": self.position,
            "size": self.size,
            "confidence": round(self.avg_confidence, 1),
        }
        if self.block_type == "label_value" and self.label is not None:
            result["label"] = self.label
            result["value"] = self.value or ""
        else:
            result["content"] = self.text
        return result


# ---------------------------------------------------------------------------
# Step 1: Group words → lines using Tesseract's hierarchy
# ---------------------------------------------------------------------------

def _group_words_to_lines(words: list[OCRWord]) -> list[TextLine]:
    """Group words into lines using Tesseract's block/par/line numbers."""
    from collections import defaultdict

    line_map: dict[tuple[int, int, int], list[OCRWord]] = defaultdict(list)
    for w in words:
        key = (w.block_num, w.par_num, w.line_num)
        line_map[key].append(w)

    lines: list[TextLine] = []
    for key in sorted(line_map.keys()):
        line_words = sorted(line_map[key], key=lambda w: w.x)
        lines.append(TextLine(words=line_words))

    # Sort lines top-to-bottom
    lines.sort(key=lambda l: (l.y, l.x))
    return lines


# ---------------------------------------------------------------------------
# Step 2: Merge lines → blocks based on spatial proximity
# ---------------------------------------------------------------------------

def _merge_lines_to_blocks(
    lines: list[TextLine],
    vertical_gap_factor: float = 1.8,
    horizontal_overlap_ratio: float = 0.3,
) -> list[list[TextLine]]:
    """Merge text lines into logical blocks based on proximity.

    Two lines are merged if:
    - Their vertical gap is less than `vertical_gap_factor` × average line height
    - They have sufficient horizontal overlap
    """
    if not lines:
        return []

    blocks: list[list[TextLine]] = [[lines[0]]]

    for line in lines[1:]:
        merged = False
        current_block = blocks[-1]
        last_line = current_block[-1]

        # Calculate vertical gap
        v_gap = line.y - last_line.bottom
        avg_h = (last_line.avg_word_height + line.avg_word_height) / 2
        max_v_gap = avg_h * vertical_gap_factor

        # Calculate horizontal overlap
        overlap_start = max(last_line.x, line.x)
        overlap_end = min(last_line.right, line.right)
        overlap = max(0, overlap_end - overlap_start)
        min_width = min(last_line.width, line.width) if min(last_line.width, line.width) > 0 else 1
        h_overlap_ratio = overlap / min_width

        if v_gap <= max_v_gap and (h_overlap_ratio >= horizontal_overlap_ratio or v_gap <= avg_h * 0.5):
            current_block.append(line)
            merged = True

        if not merged:
            blocks.append([line])

    return blocks


# ---------------------------------------------------------------------------
# Step 3: Classify blocks into UI element types
# ---------------------------------------------------------------------------

# Patterns that suggest a label:value pair
_LABEL_VALUE_PATTERNS = [
    re.compile(r"^(.+?):\s+(.+)$"),          # "Label: Value"
    re.compile(r"^(.+?)\s*[=]\s*(.+)$"),      # "Label = Value"
    re.compile(r"^(.+?)\s*[-–—]\s+(.+)$"),    # "Label — Value"
]

# Common button-like words
_BUTTON_KEYWORDS = {
    "ok", "cancel", "submit", "save", "close", "open", "yes", "no",
    "apply", "delete", "remove", "edit", "add", "new", "next", "back",
    "continue", "done", "send", "upload", "download", "browse", "search",
    "login", "logout", "sign in", "sign out", "sign up", "register",
    "confirm", "retry", "refresh", "update", "install", "uninstall",
}

# Navigation keywords
_NAV_KEYWORDS = {
    "file", "edit", "view", "window", "help", "tools", "format",
    "insert", "options", "settings", "preferences", "about",
    "home", "back", "forward", "bookmarks", "history",
}


def _classify_block(block: UIBlock, median_height: float, image_width: int) -> UIBlock:
    """Classify a UIBlock's type based on heuristics."""
    text = block.text.strip()
    line_count = len(block.lines)
    avg_h = block.avg_line_height
    word_count = sum(len(l.words) for l in block.lines)

    # --- Heading: taller text, short content ---
    if avg_h > median_height * 1.3 and word_count <= 10 and line_count <= 2:
        block.block_type = "heading"
        return block

    # --- Button: short, single-line, matches keywords ---
    if line_count == 1 and word_count <= 4:
        lower_text = text.lower().strip("[] (){}|")
        if lower_text in _BUTTON_KEYWORDS or (
            len(text) <= 15 and text.isupper()
        ):
            block.block_type = "button"
            return block

    # --- Nav item: short, at top of screen, matches nav keywords ---
    if line_count == 1 and word_count <= 3 and block.y < 60:
        lower_text = text.lower()
        if lower_text in _NAV_KEYWORDS:
            block.block_type = "nav_item"
            return block

    # --- Label+Value: matches "Label: Value" pattern ---
    if line_count == 1:
        for pattern in _LABEL_VALUE_PATTERNS:
            match = pattern.match(text)
            if match:
                label_part = match.group(1).strip()
                value_part = match.group(2).strip()
                # Heuristic: label should be short-ish
                if len(label_part.split()) <= 5:
                    block.block_type = "label_value"
                    block.label = label_part
                    block.value = value_part
                    return block

    # --- List item: starts with bullet/number ---
    if line_count == 1 and re.match(r"^(\d+[.)]\s|[-•*]\s)", text):
        block.block_type = "list_item"
        return block

    # --- Caption: very small text ---
    if avg_h < median_height * 0.7 and word_count <= 15:
        block.block_type = "caption"
        return block

    # Default: plain text
    block.block_type = "text"
    return block


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def aggregate(
    words: list[OCRWord],
    image_width: int = 1920,
    image_height: int = 1080,
    vertical_gap_factor: float = 1.8,
    horizontal_overlap_ratio: float = 0.3,
) -> list[UIBlock]:
    """Full aggregation pipeline: words → lines → blocks → classified blocks.

    Args:
        words: OCR word list from ocr_engine.run_ocr().
        image_width: Width of the source image (for layout heuristics).
        image_height: Height of the source image.
        vertical_gap_factor: Multiplier for merging lines vertically.
        horizontal_overlap_ratio: Minimum horizontal overlap to merge.

    Returns:
        List of classified UIBlock objects.
    """
    if not words:
        return []

    # Step 1: Words → Lines
    lines = _group_words_to_lines(words)

    if not lines:
        return []

    # Step 2: Lines → Block groups
    block_groups = _merge_lines_to_blocks(
        lines,
        vertical_gap_factor=vertical_gap_factor,
        horizontal_overlap_ratio=horizontal_overlap_ratio,
    )

    # Build UIBlocks
    blocks = [UIBlock(lines=group) for group in block_groups]

    # Compute median line height for classification
    all_heights = [line.avg_word_height for block in blocks for line in block.lines if line.avg_word_height > 0]
    median_height = sorted(all_heights)[len(all_heights) // 2] if all_heights else 16.0

    # Step 3: Classify each block
    classified = [_classify_block(b, median_height, image_width) for b in blocks]

    return classified
