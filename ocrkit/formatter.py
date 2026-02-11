"""
formatter.py — JSON output formatting for OCRKit results.

Produces the structured JSON output as specified in the MVP spec:
{
  "app": "...",
  "timestamp": "...",
  "image": { "width": ..., "height": ... },
  "blocks": [ ... ]
}
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from ocrkit.aggregator import UIBlock


def format_blocks(
    blocks: list[UIBlock],
    app_name: Optional[str] = None,
    source_file: Optional[str] = None,
    image_width: int = 0,
    image_height: int = 0,
    timestamp: Optional[str] = None,
    include_raw_text: bool = False,
) -> dict:
    """Format UIBlocks into the OCRKit JSON structure.

    Args:
        blocks: Classified UI blocks from the aggregator.
        app_name: Application name (if known).
        source_file: Source file path.
        image_width: Width of the source image.
        image_height: Height of the source image.
        timestamp: ISO timestamp; auto-generated if not provided.
        include_raw_text: If True, include a raw_text field with all text.

    Returns:
        A dict matching the OCRKit output schema.
    """
    if timestamp is None:
        timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")

    result: dict = {
        "app": app_name or "unknown",
        "source": source_file or "screenshot",
        "timestamp": timestamp,
        "image": {
            "width": image_width,
            "height": image_height,
        },
        "blocks": [block.to_dict() for block in blocks],
        "stats": {
            "total_blocks": len(blocks),
            "by_type": _count_by_type(blocks),
        },
    }

    if include_raw_text:
        result["raw_text"] = "\n".join(block.text for block in blocks)

    return result


def format_blocks_json(
    blocks: list[UIBlock],
    indent: int = 2,
    **kwargs,
) -> str:
    """Format UIBlocks and return a JSON string."""
    data = format_blocks(blocks, **kwargs)
    return json.dumps(data, indent=indent, ensure_ascii=False)


def _count_by_type(blocks: list[UIBlock]) -> dict[str, int]:
    """Count blocks grouped by type."""
    counts: dict[str, int] = {}
    for b in blocks:
        counts[b.block_type] = counts.get(b.block_type, 0) + 1
    return counts
