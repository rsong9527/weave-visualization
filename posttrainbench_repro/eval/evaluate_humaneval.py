#!/usr/bin/env python3
"""
HumanEval Evaluation Script

Evaluates a model on the HumanEval benchmark (Python code generation).
Uses function completion and execution-based testing.

Usage:
    python eval/evaluate_humaneval.py \
        --model-path results/qwen3_1.7b_humaneval/final_model \
        --limit 50 \
        --output results/qwen3_1.7b_humaneval/humaneval_eval.json
"""

import argparse
import json
import re
import sys
import time
import logging
import signal
import contextlib
import io
import tempfile
import os
from pathlib import Path
from typing import Optional

import torch
from datasets import load_dataset
from transformers import AutoModelForCausalLM, AutoTokenizer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


class TimeoutError(Exception):
    pass


@contextlib.contextmanager
def time_limit(seconds: int):
    """Context manager for timeout."""
    def signal_handler(signum, frame):
        raise TimeoutError("Timed out!")
    signal.signal(signal.SIGALRM, signal_handler)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)


def extract_code(response: str, entry_point: str = "") -> str:
    """Extract Python code from model response."""
    # Try to find code blocks
    code_blocks = re.findall(r"```(?:python)?\s*\n(.*?)```", response, re.DOTALL)
    if code_blocks:
        return code_blocks[0].strip()

    # Try to find function definition
    match = re.search(r"(def\s+\w+.*?)(?:\n\n|\Z)", response, re.DOTALL)
    if match:
        return match.group(1).strip()

    # Return everything (might be just the function body)
    return response.strip()


def check_correctness(
    problem: dict,
    completion: str,
    timeout: int = 5,
) -> dict:
    """Check if a code completion is correct by running test cases."""
    prompt = problem["prompt"]
    test = problem["test"]
    entry_point = problem["entry_point"]

    # Build the full program
    full_code = prompt + completion + "\n" + test + f"\ncheck({entry_point})\n"

    result = {"passed": False, "error": None}

    try:
        # Create a temporary file and execute it
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(full_code)
            f.flush()
            tmp_path = f.name

        try:
            with time_limit(timeout):
                exec_globals = {}
                exec(compile(full_code, tmp_path, "exec"), exec_globals)
            result["passed"] = True
        except TimeoutError:
            result["error"] = "timeout"
        except Exception as e:
            result["error"] = str(e)[:200]
        finally:
            os.unlink(tmp_path)
    except Exception as e:
        result["error"] = f"setup_error: {str(e)[:200]}"

    return result


def generate_completion(
    model,
    tokenizer,
    prompt: str,
    max_new_tokens: int = 512,
    device: str = "cuda",
) -> str:
    """Generate code completion for a HumanEval problem."""
    formatted_prompt = (
        f"<|im_start|>user\n"
        f"Complete the following Python function. "
        f"Only output the function body (no explanation):\n\n"
        f"{prompt}<|im_end|>\n"
        f"<|im_start|>assistant\n"
    )

    inputs = tokenizer(formatted_prompt, return_tensors="pt", truncation=True, max_length=1024)
    inputs = {k: v.to(device) for k, v in inputs.items()}

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            temperature=0.2,
            top_p=0.95,
            do_sample=True,
            pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id,
        )

    response = tokenizer.decode(outputs[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)

    # Extract just the code
    code = extract_code(response, "")
    return code


def evaluate_humaneval(
    model_path: str,
    limit: int = -1,
    output_file: str = None,
    max_new_tokens: int = 512,
) -> dict:
    """Evaluate model on HumanEval benchmark."""
    logger.info(f"Loading model from: {model_path}")
    start_time = time.time()

    # Determine device
    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info(f"Using device: {device}")

    # Load model
    dtype = torch.bfloat16 if device == "cuda" else torch.float32
    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        torch_dtype=dtype,
        device_map="auto" if device == "cuda" else None,
        trust_remote_code=True,
    )
    if device == "cpu":
        model = model.to(device)
    model.eval()

    tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # Load dataset
    logger.info("Loading HumanEval dataset...")
    dataset = load_dataset("openai/openai_humaneval", split="test")
    if limit > 0:
        dataset = dataset.select(range(min(limit, len(dataset))))
    logger.info(f"Evaluating on {len(dataset)} problems")

    # Evaluate
    passed = 0
    total = 0
    results = []

    for i, problem in enumerate(dataset):
        task_id = problem["task_id"]
        prompt = problem["prompt"]
        entry_point = problem["entry_point"]

        # Generate completion
        completion = generate_completion(model, tokenizer, prompt, max_new_tokens, device)

        # Test the completion
        check_result = check_correctness(problem, completion, timeout=10)

        if check_result["passed"]:
            passed += 1
        total += 1

        results.append({
            "task_id": task_id,
            "entry_point": entry_point,
            "passed": check_result["passed"],
            "error": check_result.get("error"),
            "completion_preview": completion[:200] + "..." if len(completion) > 200 else completion,
        })

        if (i + 1) % 20 == 0 or i == 0:
            pass_rate = passed / total * 100
            logger.info(f"[{i+1}/{len(dataset)}] pass@1: {pass_rate:.1f}% ({passed}/{total})")

    elapsed = time.time() - start_time
    pass_rate = passed / total * 100

    metrics = {
        "benchmark": "humaneval",
        "model_path": model_path,
        "pass_at_1": pass_rate,
        "passed": passed,
        "total": total,
        "eval_time_seconds": elapsed,
        "eval_time_formatted": f"{elapsed/60:.1f}m",
    }

    logger.info("=" * 60)
    logger.info(f"HumanEval Evaluation Results")
    logger.info(f"pass@1: {pass_rate:.2f}% ({passed}/{total})")
    logger.info(f"Time: {metrics['eval_time_formatted']}")
    logger.info("=" * 60)

    if output_file:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump({"metrics": metrics, "results": results}, f, indent=2)
        logger.info(f"Results saved to: {output_file}")

    return metrics


def main():
    parser = argparse.ArgumentParser(description="Evaluate model on HumanEval")
    parser.add_argument("--model-path", type=str, required=True, help="Path to model")
    parser.add_argument("--limit", type=int, default=-1, help="Max problems to evaluate (-1=all)")
    parser.add_argument("--output", type=str, default=None, help="Output JSON file path")
    parser.add_argument("--max-new-tokens", type=int, default=512, help="Max new tokens to generate")
    args = parser.parse_args()

    metrics = evaluate_humaneval(
        model_path=args.model_path,
        limit=args.limit,
        output_file=args.output,
        max_new_tokens=args.max_new_tokens,
    )

    print(f"\nHumanEval pass@1: {metrics['pass_at_1']:.2f}%")


if __name__ == "__main__":
    main()
