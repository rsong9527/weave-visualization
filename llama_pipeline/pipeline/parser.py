"""
Parser: raw logs / text input → structured facts.json

Design principle: "先抽 facts，再让模型做决定，不要让模型从垃圾里找信号"
The model should never see raw logs. It gets clean, structured facts only.
"""

import json
import re
import hashlib
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)


@dataclass
class Fact:
    """A single extracted fact from input data."""
    category: str       # e.g. "error", "metric", "k8s_pod"
    value: str          # the extracted value
    line_number: int    # source line number (1-indexed)
    raw_line: str       # original line for traceability


@dataclass
class ParseResult:
    """Structured output of the parser."""
    source: str                          # input file path or identifier
    parsed_at: str = ""                  # ISO timestamp
    total_lines: int = 0
    facts: list[Fact] = field(default_factory=list)
    summary: dict = field(default_factory=dict)  # category → count

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @property
    def facts_text(self) -> str:
        """Compact text representation for prompt injection."""
        lines = []
        for cat, facts in self._grouped().items():
            lines.append(f"[{cat}] ({len(facts)} items)")
            for f in facts[:20]:  # cap per category to avoid blowing ctx
                lines.append(f"  - {f.value}")
            if len(facts) > 20:
                lines.append(f"  ... and {len(facts) - 20} more")
        return "\n".join(lines)

    def _grouped(self) -> dict[str, list[Fact]]:
        groups: dict[str, list[Fact]] = {}
        for f in self.facts:
            groups.setdefault(f.category, []).append(f)
        return groups


class LogParser:
    """Parse raw logs into structured facts using regex patterns."""

    def __init__(self, config_path: str = "config.yaml"):
        with open(config_path) as fh:
            cfg = yaml.safe_load(fh)

        parser_cfg = cfg.get("parser", {})
        self.max_lines = parser_cfg.get("max_lines", 5000)
        self.output_dir = Path(parser_cfg.get("output_dir", "./data"))
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Compile patterns
        self.patterns: list[tuple[str, re.Pattern, str]] = []
        for p in parser_cfg.get("patterns", []):
            try:
                compiled = re.compile(p["regex"])
                self.patterns.append((p["name"], compiled, p.get("description", "")))
            except re.error as e:
                logger.warning(f"Invalid regex for pattern '{p['name']}': {e}")

    def parse(self, input_path: str) -> ParseResult:
        """Parse a log file and return structured facts."""
        path = Path(input_path)
        if not path.exists():
            raise FileNotFoundError(f"Input not found: {input_path}")

        text = path.read_text(errors="replace")
        return self.parse_text(text, source=str(path))

    def parse_text(self, text: str, source: str = "<stdin>") -> ParseResult:
        """Parse raw text and return structured facts."""
        lines = text.splitlines()

        if len(lines) > self.max_lines:
            logger.warning(
                f"Input has {len(lines)} lines, truncating to {self.max_lines}"
            )
            lines = lines[:self.max_lines]

        result = ParseResult(
            source=source,
            parsed_at=datetime.now(timezone.utc).isoformat(),
            total_lines=len(lines),
        )

        for line_num, line in enumerate(lines, start=1):
            stripped = line.strip()
            if not stripped:
                continue

            for name, pattern, _ in self.patterns:
                match = pattern.search(stripped)
                if match:
                    # Use the last captured group as the value
                    value = match.group(match.lastindex or 0).strip()
                    if value:
                        result.facts.append(Fact(
                            category=name,
                            value=value,
                            line_number=line_num,
                            raw_line=stripped[:500],  # truncate long lines
                        ))

        # Build summary
        for fact in result.facts:
            result.summary[fact.category] = result.summary.get(fact.category, 0) + 1

        logger.info(
            f"Parsed {result.total_lines} lines → "
            f"{len(result.facts)} facts in {len(result.summary)} categories"
        )
        return result

    def parse_and_save(self, input_path: str) -> tuple[ParseResult, Path]:
        """Parse and save facts to JSON file."""
        result = self.parse(input_path)

        # Deterministic filename from source
        source_hash = hashlib.md5(result.source.encode()).hexdigest()[:8]
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        output_path = self.output_dir / f"facts_{ts}_{source_hash}.json"

        output_path.write_text(result.to_json(), encoding="utf-8")
        logger.info(f"Facts saved to {output_path}")

        return result, output_path


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    ap = argparse.ArgumentParser(description="Parse logs into structured facts")
    ap.add_argument("input", help="Path to log file or '-' for stdin")
    ap.add_argument("--config", default="config.yaml", help="Config file path")
    ap.add_argument("--output", help="Output JSON path (auto-generated if omitted)")
    args = ap.parse_args()

    parser = LogParser(config_path=args.config)

    if args.input == "-":
        import sys
        text = sys.stdin.read()
        result = parser.parse_text(text, source="<stdin>")
    else:
        result = parser.parse(args.input)

    if args.output:
        Path(args.output).write_text(result.to_json(), encoding="utf-8")
        print(f"Saved to {args.output}")
    else:
        _, path = parser.parse_and_save(args.input)
        print(f"Saved to {path}")

    print(f"\nSummary: {result.summary}")
    print(f"Total facts: {len(result.facts)}")


if __name__ == "__main__":
    main()
