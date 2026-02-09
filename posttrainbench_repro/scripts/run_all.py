#!/usr/bin/env python3
"""
PostTrainBench Reproduction - Run All Experiments

Orchestrates post-training and evaluation across multiple models and benchmarks.
Reproduces the PostTrainBench methodology: train base LLMs, then evaluate.

Usage:
    # Run full experiments on GPU (H100 recommended)
    python scripts/run_all.py --mode full

    # Run lightweight demo on CPU
    python scripts/run_all.py --mode lightweight

    # Run specific model + benchmark combo
    python scripts/run_all.py --models Qwen/Qwen3-1.7B --benchmarks gsm8k

    # Run with QLoRA (saves VRAM)
    python scripts/run_all.py --mode full --quantize
"""

import argparse
import json
import os
import sys
import time
import subprocess
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# Project root
PROJECT_ROOT = Path(__file__).parent.parent

# Default configurations
FULL_MODELS = [
    "Qwen/Qwen3-1.7B",
    "Qwen/Qwen3-4B",
    "HuggingFaceTB/SmolLM3-3B",
    "google/gemma-3-4b",
]

LIGHTWEIGHT_MODELS = [
    "Qwen/Qwen2.5-0.5B",
    "HuggingFaceTB/SmolLM2-135M",
]

BENCHMARKS = ["gsm8k", "humaneval"]

EVAL_SCRIPTS = {
    "gsm8k": "eval/evaluate_gsm8k.py",
    "humaneval": "eval/evaluate_humaneval.py",
}


def safe_model_name(model_id: str) -> str:
    """Convert model ID to filesystem-safe name."""
    return model_id.replace("/", "_").replace("-", "_").lower()


def run_command(cmd: list, cwd: str = None, timeout: int = None) -> dict:
    """Run a command and capture output."""
    logger.info(f"Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd or str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    except subprocess.TimeoutExpired:
        logger.error(f"Command timed out after {timeout}s")
        return {"returncode": -1, "stdout": "", "stderr": "TIMEOUT"}
    except Exception as e:
        logger.error(f"Command failed: {e}")
        return {"returncode": -1, "stdout": "", "stderr": str(e)}


def evaluate_baseline(model_id: str, benchmark: str, results_dir: Path, eval_limit: int) -> Optional[dict]:
    """Evaluate a base model (before post-training) as baseline."""
    logger.info(f"Evaluating baseline: {model_id} on {benchmark}")

    eval_script = EVAL_SCRIPTS.get(benchmark)
    if not eval_script:
        logger.warning(f"No evaluation script for benchmark: {benchmark}")
        return None

    output_file = str(results_dir / "baseline_eval.json")
    cmd = [
        sys.executable,
        str(PROJECT_ROOT / eval_script),
        "--model-path", model_id,
        "--limit", str(eval_limit),
        "--output", output_file,
    ]

    result = run_command(cmd, timeout=3600)

    if result["returncode"] == 0 and Path(output_file).exists():
        with open(output_file) as f:
            return json.load(f).get("metrics", {})
    else:
        logger.error(f"Baseline evaluation failed: {result['stderr'][-500:]}")
        return None


def post_train(
    model_id: str,
    benchmark: str,
    results_dir: Path,
    mode: str,
    quantize: bool,
    max_samples: int,
) -> Optional[str]:
    """Run post-training on a model."""
    logger.info(f"Post-training: {model_id} for {benchmark}")

    output_dir = str(results_dir)
    cmd = [
        sys.executable,
        str(PROJECT_ROOT / "scripts" / "post_train.py"),
        "--model", model_id,
        "--benchmark", benchmark,
        "--output-dir", output_dir,
        "--mode", mode,
        "--max-samples", str(max_samples),
    ]

    if quantize:
        cmd.append("--quantize")

    # Give generous timeout: 10 hours for full, 1 hour for lightweight
    timeout = 36000 if mode == "full" else 3600

    result = run_command(cmd, timeout=timeout)

    final_model = results_dir / "final_model"
    if result["returncode"] == 0 and final_model.exists():
        logger.info(f"Post-training successful: {final_model}")
        return str(final_model)
    else:
        logger.error(f"Post-training failed: {result['stderr'][-500:]}")
        return None


def evaluate_post_trained(
    model_path: str,
    benchmark: str,
    results_dir: Path,
    eval_limit: int,
) -> Optional[dict]:
    """Evaluate a post-trained model."""
    logger.info(f"Evaluating post-trained model: {model_path} on {benchmark}")

    eval_script = EVAL_SCRIPTS.get(benchmark)
    if not eval_script:
        logger.warning(f"No evaluation script for benchmark: {benchmark}")
        return None

    output_file = str(results_dir / "posttrain_eval.json")
    cmd = [
        sys.executable,
        str(PROJECT_ROOT / eval_script),
        "--model-path", model_path,
        "--limit", str(eval_limit),
        "--output", output_file,
    ]

    result = run_command(cmd, timeout=3600)

    if result["returncode"] == 0 and Path(output_file).exists():
        with open(output_file) as f:
            return json.load(f).get("metrics", {})
    else:
        logger.error(f"Post-train evaluation failed: {result['stderr'][-500:]}")
        return None


def generate_leaderboard(all_results: list, output_path: Path):
    """Generate a leaderboard summary from all results."""
    logger.info("Generating leaderboard...")

    # Build summary table
    summary = []
    for r in all_results:
        model_name = r["model_id"].split("/")[-1]
        benchmark = r["benchmark"]

        baseline_score = None
        posttrain_score = None

        if r.get("baseline_metrics"):
            baseline_score = r["baseline_metrics"].get("accuracy") or r["baseline_metrics"].get("pass_at_1", 0)

        if r.get("posttrain_metrics"):
            posttrain_score = r["posttrain_metrics"].get("accuracy") or r["posttrain_metrics"].get("pass_at_1", 0)

        improvement = None
        if baseline_score is not None and posttrain_score is not None:
            improvement = posttrain_score - baseline_score

        summary.append({
            "model": model_name,
            "benchmark": benchmark,
            "baseline": f"{baseline_score:.2f}%" if baseline_score is not None else "N/A",
            "post_trained": f"{posttrain_score:.2f}%" if posttrain_score is not None else "FAILED",
            "improvement": f"+{improvement:.2f}%" if improvement is not None else "N/A",
            "training_time": r.get("training_time", "N/A"),
        })

    # Sort by improvement
    summary.sort(key=lambda x: float(x["improvement"].replace("+", "").replace("%", "").replace("N/A", "-999")), reverse=True)

    # Print leaderboard
    print("\n" + "=" * 80)
    print("  PostTrainBench Reproduction - Leaderboard")
    print("=" * 80)
    print(f"{'Model':<20} {'Benchmark':<12} {'Baseline':<12} {'Post-Train':<12} {'Improvement':<12} {'Time'}")
    print("-" * 80)
    for s in summary:
        print(f"{s['model']:<20} {s['benchmark']:<12} {s['baseline']:<12} {s['post_trained']:<12} {s['improvement']:<12} {s['training_time']}")
    print("=" * 80)

    # Save
    leaderboard_data = {
        "generated_at": datetime.now().isoformat(),
        "summary": summary,
        "detailed_results": all_results,
    }

    with open(output_path, "w") as f:
        json.dump(leaderboard_data, f, indent=2, default=str)

    logger.info(f"Leaderboard saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="PostTrainBench Reproduction - Run All Experiments"
    )
    parser.add_argument(
        "--mode",
        type=str,
        default="lightweight",
        choices=["full", "lightweight"],
        help="Training mode",
    )
    parser.add_argument(
        "--models",
        type=str,
        nargs="+",
        default=None,
        help="Specific models to train (HuggingFace IDs)",
    )
    parser.add_argument(
        "--benchmarks",
        type=str,
        nargs="+",
        default=None,
        choices=["gsm8k", "humaneval"],
        help="Benchmarks to evaluate on",
    )
    parser.add_argument(
        "--quantize",
        action="store_true",
        help="Use QLoRA quantization",
    )
    parser.add_argument(
        "--max-samples",
        type=int,
        default=None,
        help="Max training samples per experiment",
    )
    parser.add_argument(
        "--eval-limit",
        type=int,
        default=50,
        help="Max evaluation examples per benchmark (use -1 for full eval)",
    )
    parser.add_argument(
        "--skip-baseline",
        action="store_true",
        help="Skip baseline evaluation (saves time)",
    )
    parser.add_argument(
        "--results-dir",
        type=str,
        default=None,
        help="Base directory for results",
    )

    args = parser.parse_args()

    # Select models
    if args.models:
        models = args.models
    elif args.mode == "lightweight":
        models = LIGHTWEIGHT_MODELS
    else:
        models = FULL_MODELS

    # Select benchmarks
    benchmarks = args.benchmarks or BENCHMARKS

    # Max samples
    if args.max_samples is not None:
        max_samples = args.max_samples
    elif args.mode == "lightweight":
        max_samples = 200
    else:
        max_samples = 10000

    # Results directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_base = Path(args.results_dir) if args.results_dir else PROJECT_ROOT / "results" / f"run_{timestamp}"
    results_base.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 60)
    logger.info("PostTrainBench Reproduction")
    logger.info(f"Mode: {args.mode}")
    logger.info(f"Models: {models}")
    logger.info(f"Benchmarks: {benchmarks}")
    logger.info(f"Max samples: {max_samples}")
    logger.info(f"Eval limit: {args.eval_limit}")
    logger.info(f"Results: {results_base}")
    logger.info("=" * 60)

    all_results = []
    total_start = time.time()

    for model_id in models:
        for benchmark in benchmarks:
            model_safe = safe_model_name(model_id)
            exp_dir = results_base / f"{model_safe}_{benchmark}"
            exp_dir.mkdir(parents=True, exist_ok=True)

            logger.info("=" * 60)
            logger.info(f"Experiment: {model_id} x {benchmark}")
            logger.info("=" * 60)

            result = {
                "model_id": model_id,
                "benchmark": benchmark,
                "mode": args.mode,
                "baseline_metrics": None,
                "posttrain_metrics": None,
                "training_time": None,
                "status": "pending",
            }

            # Step 1: Baseline evaluation
            if not args.skip_baseline:
                try:
                    baseline = evaluate_baseline(model_id, benchmark, exp_dir, args.eval_limit)
                    result["baseline_metrics"] = baseline
                except Exception as e:
                    logger.error(f"Baseline eval failed: {e}")

            # Step 2: Post-training
            try:
                train_start = time.time()
                final_model = post_train(
                    model_id, benchmark, exp_dir, args.mode, args.quantize, max_samples
                )
                train_time = time.time() - train_start
                result["training_time"] = f"{train_time/60:.1f}m"

                if final_model:
                    result["status"] = "trained"

                    # Step 3: Post-training evaluation
                    try:
                        posttrain = evaluate_post_trained(
                            final_model, benchmark, exp_dir, args.eval_limit
                        )
                        result["posttrain_metrics"] = posttrain
                        result["status"] = "evaluated"
                    except Exception as e:
                        logger.error(f"Post-train eval failed: {e}")
                        result["status"] = "eval_failed"
                else:
                    result["status"] = "train_failed"

            except Exception as e:
                logger.error(f"Training failed: {e}")
                result["status"] = "error"

            all_results.append(result)

            # Save intermediate results
            with open(results_base / "results_progress.json", "w") as f:
                json.dump(all_results, f, indent=2, default=str)

    total_time = time.time() - total_start

    # Generate leaderboard
    generate_leaderboard(all_results, results_base / "leaderboard.json")

    logger.info(f"\nTotal time: {total_time/3600:.1f}h {(total_time%3600)/60:.0f}m")
    logger.info(f"Results saved to: {results_base}")


if __name__ == "__main__":
    main()
