"""Setup script for microbot."""

from setuptools import setup, find_packages

setup(
    name="microbot",
    version="0.1.0",
    description="Ultra-lightweight personal AI assistant in ~2000 lines of code",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="microbot contributors",
    license="MIT",
    python_requires=">=3.11",
    packages=find_packages(),
    install_requires=[
        "httpx>=0.25.0",
    ],
    entry_points={
        "console_scripts": [
            "microbot=microbot.cli:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
)
