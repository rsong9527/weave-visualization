"""Minimal setup.py for OCRKit."""

from setuptools import setup, find_packages

setup(
    name="ocrkit",
    version="0.1.0",
    description="Lightweight OCR + UI structure extraction toolkit",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        "ocrkit": ["viewer/templates/*.html", "viewer/static/*"],
    },
    python_requires=">=3.10",
    install_requires=[
        "pytesseract>=0.3.10",
        "Pillow>=10.0.0",
        "opencv-python-headless>=4.8.0",
        "numpy>=1.24.0",
        "flask>=3.0.0",
    ],
    entry_points={
        "console_scripts": [
            "ocrkit=ocrkit.cli:main",
        ],
    },
)
