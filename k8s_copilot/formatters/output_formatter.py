"""
Output Formatter — Mandatory 5-Section Diagnostic Output

Parses LLM raw responses and enforces the 5-piece output structure.
Also validates hard constraints (evidence citations, no large code blocks, etc.).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class NextStep:
    """A single action step with priority."""
    priority: str  # P0, P1, P2
    action: str
    expected_result: str = ""


@dataclass
class DiagnosisOutput:
    """The mandatory 5-section output structure."""

    # Section 1: Diagnosis
    diagnosis: str = ""

    # Section 2: Root Cause
    root_cause: str = ""
    missing_info: list[str] = field(default_factory=list)

    # Section 3: Next Steps
    next_steps: list[NextStep] = field(default_factory=list)

    # Section 4: Commands / YAML Patch
    commands_yaml: str = ""

    # Section 5: Rollback + Customer Message
    rollback: str = ""
    customer_message: str = ""

    # Meta
    evidence_citations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_markdown(self) -> str:
        """Render the diagnosis as a formatted Markdown document."""
        sections = []

        # Header
        sections.append("# K8s/Helm Support Copilot — Diagnosis Report\n")

        # Warnings
        if self.warnings:
            sections.append("> **Warnings:**")
            for w in self.warnings:
                sections.append(f"> - {w}")
            sections.append("")

        # Section 1
        sections.append("## 1. Diagnosis\n")
        sections.append(self.diagnosis or "_No diagnosis provided._")
        sections.append("")

        # Section 2
        sections.append("## 2. Root Cause\n")
        sections.append(self.root_cause or "_No root cause identified._")
        if self.missing_info:
            sections.append("\n### Missing Information Needed")
            for info in self.missing_info:
                sections.append(f"- {info}")
        sections.append("")

        # Section 3
        sections.append("## 3. Next Steps\n")
        if self.next_steps:
            for step in self.next_steps:
                line = f"- **{step.priority}**: {step.action}"
                if step.expected_result:
                    line += f"\n  - Expected result: {step.expected_result}"
                sections.append(line)
        else:
            sections.append("_No next steps defined._")
        sections.append("")

        # Section 4
        sections.append("## 4. Commands / YAML Patch\n")
        sections.append(self.commands_yaml or "_No commands provided._")
        sections.append("")

        # Section 5
        sections.append("## 5. Rollback + Customer Message\n")
        sections.append("### Rollback Procedure\n")
        sections.append(self.rollback or "_No rollback procedure provided._")
        sections.append("\n### Customer Message\n")
        sections.append(self.customer_message or "_No customer message drafted._")

        # Evidence Citations
        if self.evidence_citations:
            sections.append("\n---\n")
            sections.append("### Evidence Citations")
            for cite in self.evidence_citations:
                sections.append(f"- {cite}")

        return "\n".join(sections)


def parse_llm_response(raw_response: str) -> DiagnosisOutput:
    """Parse a raw LLM response into the structured 5-section output.

    The LLM is prompted to use specific section headers. This parser
    extracts each section by header matching.

    Args:
        raw_response: Raw text from the LLM.

    Returns:
        Structured DiagnosisOutput.
    """
    output = DiagnosisOutput()

    # Define section patterns (flexible matching)
    section_patterns = [
        (r"#{1,3}\s*1[\.\):]?\s*Diagnosis", "diagnosis"),
        (r"#{1,3}\s*2[\.\):]?\s*Root\s*Cause", "root_cause"),
        (r"#{1,3}\s*3[\.\):]?\s*Next\s*Steps", "next_steps_raw"),
        (r"#{1,3}\s*4[\.\):]?\s*Commands|#{1,3}\s*4[\.\):]?\s*YAML", "commands_yaml"),
        (r"#{1,3}\s*5[\.\):]?\s*Rollback", "rollback_raw"),
    ]

    # Split response into sections
    section_boundaries = []
    for pattern, name in section_patterns:
        match = re.search(pattern, raw_response, re.IGNORECASE)
        if match:
            section_boundaries.append((match.start(), match.end(), name))

    # Sort by position
    section_boundaries.sort(key=lambda x: x[0])

    # Extract section content
    section_content = {}
    for i, (start, header_end, name) in enumerate(section_boundaries):
        if i + 1 < len(section_boundaries):
            content = raw_response[header_end:section_boundaries[i + 1][0]]
        else:
            content = raw_response[header_end:]
        section_content[name] = content.strip()

    # If no sections found, treat entire response as diagnosis
    if not section_content:
        output.diagnosis = raw_response.strip()
        output.warnings.append(
            "LLM response did not follow the 5-section format. "
            "Entire response placed in Diagnosis section."
        )
        return output

    # Populate output
    output.diagnosis = section_content.get("diagnosis", "")
    output.root_cause = section_content.get("root_cause", "")
    output.commands_yaml = section_content.get("commands_yaml", "")

    # Parse next steps for priority levels
    next_steps_raw = section_content.get("next_steps_raw", "")
    if next_steps_raw:
        _parse_next_steps(next_steps_raw, output)

    # Parse rollback section (may contain customer message)
    rollback_raw = section_content.get("rollback_raw", "")
    if rollback_raw:
        _parse_rollback(rollback_raw, output)

    # Extract evidence citations
    citation_pattern = r"\[Evidence[:\s]*([^\]]+)\]"
    output.evidence_citations = re.findall(citation_pattern, raw_response, re.IGNORECASE)

    # Extract missing info
    missing_pattern = r"[Mm]issing\s+[Ii]nformation.*?(?:\n[-*]\s+(.+))"
    missing_matches = re.findall(missing_pattern, raw_response)
    output.missing_info = missing_matches

    return output


def _parse_next_steps(raw: str, output: DiagnosisOutput) -> None:
    """Parse next steps section looking for P0/P1/P2 priorities."""
    # Match lines like "- P0 (immediate): ..." or "- **P0**: ..."
    step_pattern = re.compile(
        r"[-*]\s*\*?\*?(P[012])\*?\*?\s*(?:\([^)]*\))?\s*[:\-]?\s*(.+?)(?:\n|$)",
        re.IGNORECASE,
    )
    expected_pattern = re.compile(
        r"(?:expected\s+result|预期)[:\s]*(.+?)(?:\n|$)",
        re.IGNORECASE,
    )

    for match in step_pattern.finditer(raw):
        priority = match.group(1).upper()
        action = match.group(2).strip()

        # Look for expected result on next line
        remaining = raw[match.end():]
        exp_match = expected_pattern.match(remaining)
        expected = exp_match.group(1).strip() if exp_match else ""

        output.next_steps.append(NextStep(
            priority=priority,
            action=action,
            expected_result=expected,
        ))

    # If no structured steps found, add the raw text as a single P1
    if not output.next_steps and raw.strip():
        output.next_steps.append(NextStep(
            priority="P1",
            action=raw.strip()[:200],
        ))


def _parse_rollback(raw: str, output: DiagnosisOutput) -> None:
    """Parse rollback section, splitting out customer message if present."""
    # Check for customer message sub-section
    customer_patterns = [
        r"#{1,4}\s*[Cc]ustomer\s+[Mm]essage",
        r"\*\*[Cc]ustomer\s+[Mm]essage\*\*",
        r"[Cc]ustomer\s+[Mm]essage\s*:",
    ]

    for pattern in customer_patterns:
        match = re.search(pattern, raw)
        if match:
            output.rollback = raw[:match.start()].strip()
            output.customer_message = raw[match.end():].strip()
            return

    # No customer message section found
    output.rollback = raw.strip()


def validate_output_constraints(output: DiagnosisOutput) -> list[str]:
    """Validate the output against hard constraints.

    Returns a list of constraint violations (empty = all good).
    """
    violations = []

    # R1: No large code blocks (>50 lines)
    if output.commands_yaml:
        code_blocks = re.findall(r"```[\s\S]*?```", output.commands_yaml)
        for block in code_blocks:
            line_count = block.count("\n")
            if line_count > 50:
                violations.append(
                    f"R1 violation: Code block has {line_count} lines (max 50)"
                )

    # R3: Must have evidence citations
    if not output.evidence_citations:
        violations.append(
            "R3 violation: No evidence citations found. "
            "Conclusions must reference [Evidence: <source>]"
        )

    # R5: Must have rollback
    if not output.rollback or output.rollback == "_No rollback procedure provided._":
        violations.append(
            "R5 violation: No rollback procedure provided"
        )

    # R7: YAML blocks should have apiVersion/kind/metadata
    yaml_blocks = re.findall(r"```ya?ml\n([\s\S]*?)```", output.commands_yaml or "")
    for i, block in enumerate(yaml_blocks):
        if "apiVersion" not in block and "kind" not in block:
            # Could be a values.yaml or patch — only warn for manifests
            if "spec:" in block or "metadata:" in block:
                violations.append(
                    f"R7 violation: YAML block {i+1} appears to be a manifest "
                    "but is missing apiVersion/kind"
                )

    return violations


def format_diagnosis_output(raw_response: str) -> str:
    """End-to-end: parse LLM response, validate, and produce final Markdown.

    Args:
        raw_response: Raw text from the LLM.

    Returns:
        Formatted Markdown string with any constraint warnings.
    """
    output = parse_llm_response(raw_response)
    violations = validate_output_constraints(output)

    if violations:
        output.warnings.extend(violations)

    return output.to_markdown()
