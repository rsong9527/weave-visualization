"""
OCRKit MVP Specification — PDF Generator

Generates a PDF document describing the OCRKit MVP:
a lightweight OCR + AX-Tree extraction tool for agent-facing UI parsing.

Usage:
    pip install reportlab
    python ocrkit_mvp_spec.py
"""

from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4


def generate_spec_pdf(output_path: str = "OCRKit_MVP_Spec.pdf") -> str:
    """Generate the OCRKit MVP specification PDF and return the output path."""

    doc = SimpleDocTemplate(output_path, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []

    # --- Content sections ---
    sections = [
        (
            "Project Name",
            "**OCRKit**: A lightweight OCR + AX-Tree extraction tool for agent-facing UI parsing.",
        ),
        (
            "MVP Objectives",
            (
                "- Pure local OCR-based UI understanding (no GPT needed)\n"
                "- Structured output in JSON\n"
                "- Built for Mac / Web / Screenshot UI"
            ),
        ),
        (
            "Core Modules",
            (
                "1. Screenshot Capture: macOS CGWindowListCreateImage or Electron API\n"
                "2. OCR Engine: tesseract.js or paddleocr\n"
                "3. (Optional) AX Tree Extractor: macOS AXUIElement / puppeteer-accessibility\n"
                "4. Block Aggregator: Position/Font-based clustering\n"
                "5. JSON Formatter: Output labeled, positioned UI components\n"
                "6. Localhost Viewer: Use next.js to preview OCR JSON structure"
            ),
        ),
        (
            "Sample Output JSON",
            (
                '{\n'
                '  "app": "Preview",\n'
                '  "timestamp": "2026-02-12T12:34:56",\n'
                '  "blocks": [\n'
                '    {"type": "label+value", "label": "File name", "value": "tax_document_2025.pdf"},\n'
                '    {"type": "button", "label": "Download", "position": [830, 120]},\n'
                '    {"type": "text", "content": "Scanned copy of your tax return", "position": [100, 300]}\n'
                '  ]\n'
                '}'
            ),
        ),
        (
            "Run Pipeline",
            (
                "1. Capture Screenshot\n"
                "2. OCR Text Blocks\n"
                "3. (Optional) AX Tree Scraping\n"
                "4. Cluster + Label\n"
                "5. Output JSON\n"
                "6. (Optional) Serve Viewer"
            ),
        ),
        (
            "Recommended Stack",
            (
                "- Runtime: Node.js + Electron\n"
                "- OCR: tesseract.js or paddleocr\n"
                "- Viewer: React + react-json-view\n"
                "- Optional: Python backend if using paddleocr"
            ),
        ),
        (
            "Target Deliverable",
            (
                "- macOS App window OCR\n"
                "- Structured JSON\n"
                "- Optional Viewer (React)\n"
                "- MVP Timeline: 5-7 days for working prototype"
            ),
        ),
    ]

    # --- Build PDF story ---
    for title, content in sections:
        story.append(Paragraph(f"<b>{title}</b>", styles["Heading2"]))
        for line in content.strip().split("\n"):
            story.append(Paragraph(line.strip(), styles["BodyText"]))
        story.append(Spacer(1, 12))

    doc.build(story)
    return output_path


if __name__ == "__main__":
    path = generate_spec_pdf()
    print(f"PDF generated: {path}")
