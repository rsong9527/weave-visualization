"""
Pipeline Runner — orchestrates the full flow:

    1. Parse input → facts.json
    2. RAG retrieval → top-k context
    3. llama.cpp inference → draft runbook
    4. Cloud review (optional) → polished output

Usage:
    python -m pipeline.runner --input path/to/logs.txt
    python -m pipeline.runner --input path/to/logs.txt --no-review
    python -m pipeline.runner --input path/to/logs.txt --config custom.yaml
"""

import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

from pipeline.parser import LogParser
from pipeline.rag import VectorStore
from pipeline.inference import LlamaClient
from pipeline.reviewer import CloudReviewer

logger = logging.getLogger(__name__)


class PipelineRunner:
    """Orchestrate the full log → runbook pipeline."""

    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path

        with open(config_path) as fh:
            self.config = yaml.safe_load(fh)

        pipe_cfg = self.config.get("pipeline", {})
        self.work_dir = Path(pipe_cfg.get("work_dir", "./data/runs"))
        self.save_artifacts = pipe_cfg.get("save_artifacts", True)
        log_level = pipe_cfg.get("log_level", "INFO")

        # Configure logging
        logging.basicConfig(
            level=getattr(logging, log_level, logging.INFO),
            format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
            datefmt="%H:%M:%S",
        )

        # Initialize components
        self.parser = LogParser(config_path=config_path)
        self.rag = VectorStore(config_path=config_path)
        self.llama = LlamaClient(config_path=config_path)
        self.reviewer = CloudReviewer(config_path=config_path)

    def run(
        self,
        input_path: str,
        skip_review: bool = False,
        skip_rag: bool = False,
    ) -> dict:
        """
        Run the full pipeline.

        Args:
            input_path: Path to log file or text input.
            skip_review: Skip cloud review step.
            skip_rag: Skip RAG retrieval (use empty context).

        Returns:
            Dict with all pipeline outputs.
        """
        run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        run_dir = self.work_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        result = {
            "run_id": run_id,
            "input": input_path,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "stages": {},
        }

        total_start = time.time()

        # =====================================================================
        # Stage 1: Parse
        # =====================================================================
        logger.info("=" * 60)
        logger.info("Stage 1: PARSE — extracting structured facts")
        logger.info("=" * 60)

        t0 = time.time()
        try:
            parse_result = self.parser.parse(input_path)
        except FileNotFoundError:
            logger.error(f"Input file not found: {input_path}")
            sys.exit(1)

        facts_text = parse_result.facts_text
        result["stages"]["parse"] = {
            "total_lines": parse_result.total_lines,
            "total_facts": len(parse_result.facts),
            "summary": parse_result.summary,
            "elapsed_s": round(time.time() - t0, 2),
        }

        if self.save_artifacts:
            (run_dir / "facts.json").write_text(parse_result.to_json())

        if not parse_result.facts:
            logger.warning("No facts extracted! Check your patterns or input format.")
            # Still continue — the model can say "insufficient data"

        logger.info(
            f"  → {len(parse_result.facts)} facts in "
            f"{len(parse_result.summary)} categories"
        )

        # =====================================================================
        # Stage 2: RAG Retrieval
        # =====================================================================
        logger.info("=" * 60)
        logger.info("Stage 2: RAG — retrieving relevant context")
        logger.info("=" * 60)

        t0 = time.time()
        if skip_rag or self.rag.count() == 0:
            if not skip_rag:
                logger.info("  Vector store is empty. Skipping RAG.")
                logger.info("  Tip: run 'make ingest DOCS=path/to/docs/' to add knowledge")
            context_text = "(No knowledge base context available)"
        else:
            # Use facts summary as the search query
            query = " ".join(
                f.value for f in parse_result.facts[:10]  # top 10 facts as query
            )
            context_text = self.rag.search_with_context(query)

        result["stages"]["rag"] = {
            "skipped": skip_rag or self.rag.count() == 0,
            "context_length": len(context_text),
            "elapsed_s": round(time.time() - t0, 2),
        }

        if self.save_artifacts:
            (run_dir / "context.txt").write_text(context_text)

        logger.info(f"  → {len(context_text)} chars of context")

        # =====================================================================
        # Stage 3: Local Inference (llama.cpp)
        # =====================================================================
        logger.info("=" * 60)
        logger.info("Stage 3: INFERENCE — generating draft with llama.cpp")
        logger.info("=" * 60)

        t0 = time.time()

        # Check server health first
        if not self.llama.health_check():
            logger.error(
                "llama.cpp server is not reachable. Start it with: make server"
            )
            result["stages"]["inference"] = {"error": "server unreachable"}
            result["draft"] = None
            result["review"] = None
            result["finished_at"] = datetime.now(timezone.utc).isoformat()
            result["total_elapsed_s"] = round(time.time() - total_start, 2)

            if self.save_artifacts:
                (run_dir / "result.json").write_text(
                    json.dumps(result, indent=2, ensure_ascii=False)
                )
            return result

        draft = self.llama.generate_runbook(
            facts_text=facts_text,
            context_text=context_text,
        )

        result["stages"]["inference"] = {
            "draft_length": len(draft),
            "elapsed_s": round(time.time() - t0, 2),
        }

        if self.save_artifacts:
            (run_dir / "draft.md").write_text(draft)

        logger.info(f"  → {len(draft)} chars of draft")

        # =====================================================================
        # Stage 4: Cloud Review (optional)
        # =====================================================================
        review = None
        if not skip_review and self.reviewer.is_available():
            logger.info("=" * 60)
            logger.info("Stage 4: REVIEW — cloud model review (one-shot)")
            logger.info("=" * 60)

            t0 = time.time()
            try:
                review = self.reviewer.review(facts_text, draft)
                result["stages"]["review"] = {
                    "review_length": len(review) if review else 0,
                    "elapsed_s": round(time.time() - t0, 2),
                }
            except Exception as e:
                logger.error(f"Cloud review failed: {e}")
                result["stages"]["review"] = {"error": str(e)}
        else:
            reason = "skipped by user" if skip_review else "disabled or no API key"
            logger.info(f"Stage 4: REVIEW — {reason}")
            result["stages"]["review"] = {"skipped": True, "reason": reason}

        if self.save_artifacts and review:
            (run_dir / "review.md").write_text(review)

        # =====================================================================
        # Final Output
        # =====================================================================
        result["draft"] = draft
        result["review"] = review
        result["finished_at"] = datetime.now(timezone.utc).isoformat()
        result["total_elapsed_s"] = round(time.time() - total_start, 2)

        if self.save_artifacts:
            (run_dir / "result.json").write_text(
                json.dumps(result, indent=2, ensure_ascii=False)
            )
            logger.info(f"\nArtifacts saved to: {run_dir}/")

        # Print final output
        print("\n" + "=" * 60)
        print("PIPELINE OUTPUT")
        print("=" * 60)
        print(f"\nRun ID: {run_id}")
        print(f"Input: {input_path}")
        print(f"Total time: {result['total_elapsed_s']}s\n")

        print("--- DRAFT RUNBOOK ---")
        print(draft)

        if review:
            print("\n--- CLOUD REVIEW ---")
            print(review)

        print("\n" + "=" * 60)

        return result


# ---------------------------------------------------------------------------
# CLI entry point: python -m pipeline.runner
# ---------------------------------------------------------------------------

def main():
    import argparse

    ap = argparse.ArgumentParser(
        description="Run the full log → runbook pipeline"
    )
    ap.add_argument(
        "--input", "-i", required=True,
        help="Path to log file or text input"
    )
    ap.add_argument(
        "--config", "-c", default="config.yaml",
        help="Config file path"
    )
    ap.add_argument(
        "--no-review", action="store_true",
        help="Skip cloud review step"
    )
    ap.add_argument(
        "--no-rag", action="store_true",
        help="Skip RAG retrieval"
    )
    args = ap.parse_args()

    runner = PipelineRunner(config_path=args.config)
    runner.run(
        input_path=args.input,
        skip_review=args.no_review,
        skip_rag=args.no_rag,
    )


if __name__ == "__main__":
    main()
