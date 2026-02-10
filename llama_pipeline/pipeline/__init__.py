"""
llama.cpp local inference pipeline.

Architecture:
    logs/input → parser → facts.json
                            ↓
                     RAG retrieval (SQLite)
                            ↓
                     llama.cpp (local 7B) → draft
                            ↓
                     cloud review (optional, one-shot) → final output
"""

__version__ = "0.1.0"
