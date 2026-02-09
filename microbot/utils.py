"""Utility functions for microbot."""

import re
import uuid
import hashlib
import datetime
from pathlib import Path
from typing import Any


# =========================================================================
# ID generation
# =========================================================================

def generate_session_id() -> str:
    """Generate a unique session ID."""
    now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    short_uuid = uuid.uuid4().hex[:8]
    return f"{now}_{short_uuid}"


def short_id(text: str, length: int = 8) -> str:
    """Generate a short deterministic ID from text."""
    return hashlib.md5(text.encode()).hexdigest()[:length]


# =========================================================================
# Text processing
# =========================================================================

def truncate(text: str, max_length: int = 200, suffix: str = "...") -> str:
    """Truncate text to max_length, adding suffix if truncated."""
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix


def word_count(text: str) -> int:
    """Count words in text (handles CJK characters)."""
    # Count CJK characters individually
    cjk = len(re.findall(r"[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]", text))
    # Count space-separated words for non-CJK
    non_cjk = re.sub(r"[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]", " ", text)
    words = len(non_cjk.split())
    return cjk + words


def format_duration(ms: int) -> str:
    """Format milliseconds to a human-readable duration."""
    if ms < 1000:
        return f"{ms}ms"
    elif ms < 60_000:
        return f"{ms / 1000:.1f}s"
    else:
        minutes = ms // 60_000
        seconds = (ms % 60_000) / 1000
        return f"{minutes}m {seconds:.0f}s"


def format_size(size_bytes: int) -> str:
    """Format byte count to human-readable size."""
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            if unit == "B":
                return f"{size_bytes}{unit}"
            return f"{size_bytes:.1f}{unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f}TB"


# =========================================================================
# Path helpers
# =========================================================================

def safe_path(path: str) -> Path:
    """Resolve and expand a path safely."""
    return Path(path).expanduser().resolve()


def is_binary_file(path: Path) -> bool:
    """Check if a file is likely binary."""
    try:
        with open(path, "rb") as f:
            chunk = f.read(8192)
        # Check for null bytes (common in binary files)
        if b"\x00" in chunk:
            return True
        # Check for high ratio of non-text bytes
        text_chars = set(range(32, 127)) | {9, 10, 13}  # printable + tab, newline, CR
        non_text = sum(1 for b in chunk if b not in text_chars)
        return non_text / max(len(chunk), 1) > 0.3
    except (OSError, PermissionError):
        return True


# =========================================================================
# Markdown helpers
# =========================================================================

def extract_code_blocks(text: str) -> list[dict[str, str]]:
    """Extract fenced code blocks from markdown text."""
    pattern = r"```(\w*)\n(.*?)```"
    blocks = []
    for match in re.finditer(pattern, text, re.DOTALL):
        blocks.append({
            "language": match.group(1) or "text",
            "code": match.group(2).strip(),
        })
    return blocks


def strip_markdown(text: str) -> str:
    """Remove basic markdown formatting for plain-text display."""
    # Remove code blocks
    text = re.sub(r"```\w*\n.*?```", "[code block]", text, flags=re.DOTALL)
    # Remove inline code
    text = re.sub(r"`([^`]+)`", r"\1", text)
    # Remove bold/italic
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    # Remove headers
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    return text


# =========================================================================
# Token estimation
# =========================================================================

def estimate_tokens(text: str) -> int:
    """Rough token count estimation (not exact, but fast)."""
    # English: ~4 chars per token; CJK: ~1.5 chars per token
    cjk_chars = len(re.findall(r"[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]", text))
    other_chars = len(text) - cjk_chars
    return int(cjk_chars / 1.5 + other_chars / 4)
