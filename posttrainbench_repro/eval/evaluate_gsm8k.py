#!/usr/bin/env python3
"""
GSM8K Evaluation Script

Evaluates a model on the GSM8K (Grade School Math 8K) benchmark.
Extracts the final numerical answer after #### and compares with ground truth.

Usage:
    python eval/evaluate_gsm8k.py \
        --model-path results/qwen3_1.7b_gsm8k/final_model \
        --limit 100 \
        --output results/qwen3_1.7b_gsm8k/gsm8k_eval.json
"""

import argparse
import json
import re
import sys
import time
import logging
from pathlib import Path

import torch
from datasets import load_dataset
from transformers import AutoModelForCausalLM, AutoTokenizer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def extract_answer(text: str) -> str:
    """Extract the numerical answer from model output.
    
    Looks for patterns like:
    - #### 42
    - The answer is 42
    - = 42
    """
    # Try #### pattern first (GSM8K standard)
    match = re.search(r"####\s*(.+?)(?:\s*$|\n)", text)
    if match:
        return match.group(1).strip().replace(",", "")

    # Try "the answer is X" pattern
    match = re.search(r"(?:the answer is|answer:)\s*\$?([0-9,.-]+)", text, re.IGNORECASE)
    if match:
        return match.group(1).strip().replace(",", "")

    # Try last number in the text
    numbers = re.findall(r"-?[0-9,]+\.?[0-9]*", text)
    if numbers:
        return numbers[-1].replace(",", "")

    return ""


def extract_ground_truth(answer_text: str) -> str:
    """Extract ground truth answer from GSM8K answer field."""
    match = re.search(r"####\s*(.+?)$", answer_text, re.MULTILINE)
    if match:
        return match.group(1).strip().replace(",", "")
    return answer_text.strip()


def normalize_number(s: str) -> float:
    """Normalize a string to a number for comparison."""
    try:
        s = s.strip().replace(",", "").replace("$", "").replace("%", "")
        return float(s)
    except (ValueError, AttributeError):
        return float("nan")


def generate_answer(
    model, tokenizer, question: str, max_new_tokens: int = 512, device: str = "cuda"
) -> str:
    """Generate an answer for a math question."""
    prompt = (
        f"<|im_start|>user\n"
        f"Solve the following math problem step by step. "
        f"Show your reasoning clearly, then give the final answer after ####.\n\n"
        f"{question}<|im_end|>\n"
        f"<|im_start|>assistant\n"
    )

    inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=1024)
    inputs = {k: v.to(device) for k, v in inputs.items()}

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            temperature=0.1,
            top_p=0.95,
            do_sample=True,
            pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id,
        )

    response = tokenizer.decode(outputs[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
    return response


def evaluate_gsm8k(
    model_path: str,
    limit: int = -1,
    output_file: str = None,
    use_vllm: bool = False,
    max_new_tokens: int = 512,
) -> dict:
    """Evaluate model on GSM8K benchmark."""
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
    logger.info("Loading GSM8K test set...")
    dataset = load_dataset("openai/gsm8k", "main", split="test")
    if limit > 0:
        dataset = dataset.select(range(min(limit, len(dataset))))
    logger.info(f"Evaluating on {len(dataset)} examples")

    # Evaluate
    correct = 0
    total = 0
    results = []

    for i, example in enumerate(dataset):
        question = example["question"]
        ground_truth = extract_ground_truth(example["answer"])

        response = generate_answer(model, tokenizer, question, max_new_tokens, device)
        predicted = extract_answer(response)

        gt_num = normalize_number(ground_truth)
        pred_num = normalize_number(predicted)

        is_correct = (
            abs(gt_num - pred_num) < 1e-6
            if not (gt_num != gt_num or pred_num != pred_num)  # NaN check
            else ground_truth.strip() == predicted.strip()
        )

        if is_correct:
            correct += 1
        total += 1

        results.append({
            "id": i,
            "question": question[:100] + "...",
            "ground_truth": ground_truth,
            "predicted": predicted,
            "correct": is_correct,
        })

        if (i + 1) % 50 == 0 or i == 0:
            accuracy = correct / total * 100
            logger.info(f"[{i+1}/{len(dataset)}] Accuracy: {accuracy:.1f}% ({correct}/{total})")

    elapsed = time.time() - start_time
    accuracy = correct / total * 100

    metrics = {
        "benchmark": "gsm8k",
        "model_path": model_path,
        "accuracy": accuracy,
        "correct": correct,
        "total": total,
        "eval_time_seconds": elapsed,
        "eval_time_formatted": f"{elapsed/60:.1f}m",
    }

    logger.info("=" * 60)
    logger.info(f"GSM8K Evaluation Results")
    logger.info(f"Accuracy: {accuracy:.2f}% ({correct}/{total})")
    logger.info(f"Time: {metrics['eval_time_formatted']}")
    logger.info("=" * 60)

    if output_file:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump({"metrics": metrics, "results": results[:50]}, f, indent=2)
        logger.info(f"Results saved to: {output_file}")

    return metrics


def main():
    parser = argparse.ArgumentParser(description="Evaluate model on GSM8K")
    parser.add_argument("--model-path", type=str, required=True, help="Path to model")
    parser.add_argument("--limit", type=int, default=-1, help="Max examples to evaluate (-1=all)")
    parser.add_argument("--output", type=str, default=None, help="Output JSON file path")
    parser.add_argument("--max-new-tokens", type=int, default=512, help="Max new tokens to generate")
    args = parser.parse_args()

    metrics = evaluate_gsm8k(
        model_path=args.model_path,
        limit=args.limit,
        output_file=args.output,
        max_new_tokens=args.max_new_tokens,
    )

    print(f"\nGSM8K Accuracy: {metrics['accuracy']:.2f}%")


if __name__ == "__main__":
    main()
