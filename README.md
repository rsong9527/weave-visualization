# OCRKit

A lightweight OCR + UI structure extraction toolkit that converts screenshots into structured JSON describing UI elements (labels, buttons, text blocks, headings, etc.) with positions.

Built for agent-facing UI parsing — no GPT required, runs fully local with Tesseract.

## Features

- **Pure local OCR** — uses Tesseract, no cloud APIs needed
- **Structured JSON output** — blocks with type, position, size, confidence
- **UI element classification** — heading, text, label\_value, button, nav\_item, list\_item, caption
- **Annotated image output** — color-coded bounding boxes overlaid on the original
- **Web viewer** — dark-themed Flask app with block inspector, JSON viewer, drag-and-drop upload
- **Multi-language** — supports English, Chinese (Simplified/Traditional), Japanese, Korean, etc.
- **Python API + CLI** — use as a library or from the command line

## Quick Start

### Install

```bash
# System dependency
sudo apt-get install tesseract-ocr

# Optional: additional languages
sudo apt-get install tesseract-ocr-chi-sim tesseract-ocr-chi-tra

# Python package
pip install -r requirements.txt
```

### CLI Usage

```bash
# Basic: print JSON to stdout
python -m ocrkit screenshot.png

# Save JSON to file
python -m ocrkit screenshot.png -o result.json

# Save annotated image with bounding boxes
python -m ocrkit screenshot.png --annotate annotated.png

# Chinese OCR
python -m ocrkit screenshot.png --lang chi_sim

# English + Chinese
python -m ocrkit screenshot.png --lang eng+chi_sim

# Launch web viewer
python -m ocrkit screenshot.png --viewer

# Serve existing JSON in viewer
python -m ocrkit --serve result.json --port 5678
```

### Python API

```python
from ocrkit import OCRKitPipeline

# Initialize
pipeline = OCRKitPipeline(lang="eng", min_confidence=30)

# Process an image → structured dict
result = pipeline.process_image("screenshot.png", app_name="MyApp")
print(result["blocks"])  # List of UI blocks with type, position, content

# Save to JSON file
pipeline.process_and_save("screenshot.png", output_path="output.json")

# Get raw OCR words
image, words = pipeline.extract_words("screenshot.png")

# Get classified UI blocks
image, blocks = pipeline.extract_blocks("screenshot.png")
```

## Output Format

```json
{
  "app": "Document Manager",
  "source": "screenshot.png",
  "timestamp": "2026-02-12T12:34:56+00:00",
  "image": { "width": 1280, "height": 800 },
  "blocks": [
    {
      "type": "heading",
      "position": [43, 86],
      "size": [306, 26],
      "confidence": 95.5,
      "content": "Document Manager"
    },
    {
      "type": "label_value",
      "position": [62, 142],
      "size": [305, 16],
      "confidence": 94.0,
      "label": "File name",
      "value": "annual_report_2025.pdf"
    },
    {
      "type": "button",
      "position": [81, 449],
      "size": [87, 12],
      "confidence": 96.0,
      "content": "Download"
    }
  ],
  "stats": {
    "total_blocks": 6,
    "by_type": { "heading": 2, "text": 3, "button": 1 }
  }
}
```

## Block Types

| Type | Description | Detection Heuristic |
|---|---|---|
| `heading` | Title / section header | Taller text, short content (≤10 words) |
| `text` | Body text / paragraph | Default for multi-word content |
| `label_value` | Key-value pair | Matches "Label: Value" pattern |
| `button` | Clickable button | Short text matching common button keywords |
| `nav_item` | Navigation menu item | Short text near top of screen |
| `list_item` | Numbered or bulleted item | Starts with `1.` / `-` / `•` |
| `caption` | Small caption text | Significantly smaller than median text |

## Architecture

```
ocrkit/
├── __init__.py          # Package init, exports OCRKitPipeline
├── __main__.py          # python -m ocrkit entry point
├── capture.py           # Image loading / screenshot capture
├── ocr_engine.py        # Tesseract OCR with word-level results
├── aggregator.py        # Block clustering + type classification
├── formatter.py         # JSON output formatting
├── pipeline.py          # End-to-end pipeline orchestration
├── visualize.py         # Annotated image rendering
├── cli.py               # Command-line interface
└── viewer/
    ├── app.py           # Flask web app
    └── templates/
        └── viewer.html  # Dark-themed single-page viewer
```

### Pipeline Flow

```
Image → Load → Tesseract OCR → Word-level results
  → Group by line (block/par/line hierarchy)
  → Merge lines into blocks (spatial proximity)
  → Classify blocks (heading/text/button/label_value/...)
  → Split mixed blocks (heading + body → separate blocks)
  → Format as JSON
```

## Web Viewer

The built-in viewer provides:

- **Block Inspector** — click any block to see its JSON in the right panel
- **JSON Tree View** — syntax-highlighted, copyable output
- **Image View** — original and annotated image tabs
- **Drag & Drop Upload** — process new images directly in the browser
- **Keyboard Navigation** — arrow keys / j/k to browse blocks, Escape to deselect
- **REST API** — `POST /api/process` to process images programmatically

## Tests

```bash
# Generate test image + run all tests
python -m pytest tests/test_ocrkit.py -v
```

## Requirements

- Python 3.10+
- Tesseract OCR (system package)
- pytesseract, Pillow, opencv-python-headless, numpy, flask
