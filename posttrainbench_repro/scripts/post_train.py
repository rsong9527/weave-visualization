#!/usr/bin/env python3
"""
PostTrainBench Reproduction - Main Post-Training Script

This script performs supervised fine-tuning (SFT) with LoRA/QLoRA on base LLMs
to improve their performance on specific benchmarks.

Usage:
    # Full GPU training (H100 recommended)
    python scripts/post_train.py \
        --model Qwen/Qwen3-1.7B \
        --benchmark gsm8k \
        --output-dir results/qwen3_1.7b_gsm8k \
        --mode full

    # Lightweight CPU/small GPU demo
    python scripts/post_train.py \
        --model Qwen/Qwen2.5-0.5B \
        --benchmark gsm8k \
        --output-dir results/demo_gsm8k \
        --mode lightweight

Reference: https://github.com/aisa-group/PostTrainBench
"""

import argparse
import json
import os
import sys
import time
import logging
from pathlib import Path
from typing import Optional

import torch
from datasets import load_dataset, concatenate_datasets, Dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
    BitsAndBytesConfig,
)
from peft import LoraConfig, get_peft_model, TaskType, prepare_model_for_kbit_training
from trl import SFTTrainer, SFTConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


# ─── Data Preparation ───────────────────────────────────────────────────────

def format_gsm8k_example(example: dict) -> dict:
    """Format a GSM8K example into instruction-response format."""
    question = example["question"]
    answer = example["answer"]
    text = (
        f"<|im_start|>user\n"
        f"Solve the following math problem step by step. "
        f"Show your reasoning clearly, then give the final answer after ####.\n\n"
        f"{question}<|im_end|>\n"
        f"<|im_start|>assistant\n"
        f"{answer}<|im_end|>"
    )
    return {"text": text}


def format_metamath_example(example: dict) -> dict:
    """Format a MetaMathQA example."""
    query = example.get("query", example.get("question", ""))
    response = example.get("response", example.get("answer", ""))
    text = (
        f"<|im_start|>user\n{query}<|im_end|>\n"
        f"<|im_start|>assistant\n{response}<|im_end|>"
    )
    return {"text": text}


def format_code_example(example: dict) -> dict:
    """Format a code instruction example."""
    instruction = example.get("instruction", example.get("prompt", ""))
    output = example.get("output", example.get("completion", ""))
    text = (
        f"<|im_start|>user\n"
        f"Write Python code to solve the following task:\n\n"
        f"{instruction}<|im_end|>\n"
        f"<|im_start|>assistant\n"
        f"{output}<|im_end|>"
    )
    return {"text": text}


def format_general_example(example: dict) -> dict:
    """Format a general instruction-following example."""
    # Handle different dataset column names
    if "conversations" in example:
        # OpenHermes style
        convs = example["conversations"]
        parts = []
        for c in convs:
            role = "user" if c.get("from") in ("human", "user") else "assistant"
            parts.append(f"<|im_start|>{role}\n{c['value']}<|im_end|>")
        text = "\n".join(parts)
    else:
        instruction = example.get("instruction", example.get("input", ""))
        response = example.get("output", example.get("response", ""))
        text = (
            f"<|im_start|>user\n{instruction}<|im_end|>\n"
            f"<|im_start|>assistant\n{response}<|im_end|>"
        )
    return {"text": text}


def load_training_data(benchmark: str, max_samples: int = 10000) -> Dataset:
    """Load and format training data based on the target benchmark."""
    logger.info(f"Loading training data for benchmark: {benchmark}")

    datasets_list = []

    if benchmark == "gsm8k":
        # GSM8K train split
        try:
            ds = load_dataset("openai/gsm8k", "main", split="train")
            ds = ds.map(format_gsm8k_example, remove_columns=ds.column_names)
            datasets_list.append(ds)
            logger.info(f"Loaded GSM8K train: {len(ds)} examples")
        except Exception as e:
            logger.warning(f"Failed to load GSM8K: {e}")

        # MetaMathQA for augmentation
        try:
            ds = load_dataset("meta-math/MetaMathQA", split="train")
            if len(ds) > max_samples:
                ds = ds.shuffle(seed=42).select(range(max_samples))
            ds = ds.map(format_metamath_example, remove_columns=ds.column_names)
            datasets_list.append(ds)
            logger.info(f"Loaded MetaMathQA: {len(ds)} examples")
        except Exception as e:
            logger.warning(f"Failed to load MetaMathQA: {e}")

    elif benchmark == "humaneval":
        # Code instruction datasets
        try:
            ds = load_dataset("iamtarun/python_code_instructions_18k_alpaca", split="train")
            ds = ds.map(format_code_example, remove_columns=ds.column_names)
            datasets_list.append(ds)
            logger.info(f"Loaded python code instructions: {len(ds)} examples")
        except Exception as e:
            logger.warning(f"Failed to load code dataset: {e}")

        try:
            ds = load_dataset("sahil2801/CodeAlpaca-20k", split="train")
            ds = ds.map(format_code_example, remove_columns=ds.column_names)
            datasets_list.append(ds)
            logger.info(f"Loaded CodeAlpaca: {len(ds)} examples")
        except Exception as e:
            logger.warning(f"Failed to load CodeAlpaca: {e}")

    elif benchmark in ("gpqamain", "bfcl", "aime2025"):
        # General reasoning / instruction following
        try:
            ds = load_dataset("Open-Orca/SlimOrca", split="train")
            if len(ds) > max_samples:
                ds = ds.shuffle(seed=42).select(range(max_samples))
            ds = ds.map(format_general_example, remove_columns=ds.column_names)
            datasets_list.append(ds)
            logger.info(f"Loaded SlimOrca: {len(ds)} examples")
        except Exception as e:
            logger.warning(f"Failed to load SlimOrca: {e}")

    else:
        # Default: general instruction following
        try:
            ds = load_dataset("tatsu-lab/alpaca", split="train")
            ds = ds.map(format_general_example, remove_columns=ds.column_names)
            datasets_list.append(ds)
            logger.info(f"Loaded Alpaca: {len(ds)} examples")
        except Exception as e:
            logger.warning(f"Failed to load Alpaca: {e}")

    if not datasets_list:
        raise RuntimeError("No training datasets could be loaded!")

    combined = concatenate_datasets(datasets_list)
    logger.info(f"Total training examples: {len(combined)}")
    return combined


def load_training_data_lightweight(benchmark: str, max_samples: int = 200) -> Dataset:
    """Load a tiny subset of training data for CPU demo."""
    logger.info(f"Loading lightweight training data for: {benchmark}")

    if benchmark == "gsm8k":
        try:
            ds = load_dataset("openai/gsm8k", "main", split="train")
            ds = ds.shuffle(seed=42).select(range(min(max_samples, len(ds))))
            ds = ds.map(format_gsm8k_example, remove_columns=ds.column_names)
            logger.info(f"Loaded {len(ds)} GSM8K examples (lightweight)")
            return ds
        except Exception as e:
            logger.warning(f"Failed to load GSM8K: {e}")
    elif benchmark == "humaneval":
        try:
            ds = load_dataset("iamtarun/python_code_instructions_18k_alpaca", split="train")
            ds = ds.shuffle(seed=42).select(range(min(max_samples, len(ds))))
            ds = ds.map(format_code_example, remove_columns=ds.column_names)
            logger.info(f"Loaded {len(ds)} code examples (lightweight)")
            return ds
        except Exception as e:
            logger.warning(f"Failed to load code dataset: {e}")

    # Fallback: create synthetic examples
    logger.info("Using synthetic training data as fallback")
    examples = []
    for i in range(max_samples):
        examples.append({
            "text": (
                f"<|im_start|>user\nWhat is {i+1} + {i+2}?<|im_end|>\n"
                f"<|im_start|>assistant\n"
                f"Let me solve this step by step.\n"
                f"{i+1} + {i+2} = {2*i+3}\n"
                f"#### {2*i+3}<|im_end|>"
            )
        })
    return Dataset.from_list(examples)


# ─── Model Setup ─────────────────────────────────────────────────────────────

def setup_model_and_tokenizer(
    model_name: str,
    mode: str = "full",
    quantize: bool = False,
):
    """Load model and tokenizer with appropriate configuration."""
    logger.info(f"Loading model: {model_name} (mode={mode})")

    tokenizer = AutoTokenizer.from_pretrained(
        model_name,
        trust_remote_code=True,
        padding_side="right",
    )

    # Set pad token if not present
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
        tokenizer.pad_token_id = tokenizer.eos_token_id

    model_kwargs = {
        "trust_remote_code": True,
    }

    if mode == "lightweight":
        # CPU-friendly settings
        model_kwargs["torch_dtype"] = torch.float32
        model_kwargs["device_map"] = None  # CPU
        logger.info("Loading model in float32 for CPU")
    elif quantize and torch.cuda.is_available():
        # QLoRA with 4-bit quantization
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,
        )
        model_kwargs["quantization_config"] = bnb_config
        model_kwargs["device_map"] = "auto"
        logger.info("Loading model with QLoRA (4-bit)")
    elif torch.cuda.is_available():
        # Full precision on GPU
        model_kwargs["torch_dtype"] = torch.bfloat16
        model_kwargs["device_map"] = "auto"
        logger.info("Loading model in bf16 on GPU")
    else:
        model_kwargs["torch_dtype"] = torch.float32
        model_kwargs["device_map"] = None
        logger.info("No GPU detected, loading in float32 on CPU")

    model = AutoModelForCausalLM.from_pretrained(model_name, **model_kwargs)

    if quantize and torch.cuda.is_available():
        model = prepare_model_for_kbit_training(model)

    model.config.use_cache = False

    return model, tokenizer


def setup_lora(model, config: dict):
    """Apply LoRA adapter to the model."""
    logger.info(f"Setting up LoRA with r={config['r']}, alpha={config['lora_alpha']}")

    lora_config = LoraConfig(
        r=config["r"],
        lora_alpha=config["lora_alpha"],
        lora_dropout=config.get("lora_dropout", 0.05),
        target_modules=config.get("target_modules", ["q_proj", "v_proj"]),
        task_type=TaskType.CAUSAL_LM,
        bias="none",
    )

    model = get_peft_model(model, lora_config)

    # Print trainable parameters
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total_params = sum(p.numel() for p in model.parameters())
    logger.info(
        f"Trainable parameters: {trainable_params:,} / {total_params:,} "
        f"({100 * trainable_params / total_params:.2f}%)"
    )

    return model


# ─── Training ────────────────────────────────────────────────────────────────

def train(
    model_name: str,
    benchmark: str,
    output_dir: str,
    mode: str = "full",
    quantize: bool = False,
    config_path: Optional[str] = None,
    max_samples: int = 10000,
):
    """Main training function."""
    start_time = time.time()
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Load config
    config_file = config_path or str(
        Path(__file__).parent.parent / "configs" / "training_config.json"
    )
    with open(config_file) as f:
        all_config = json.load(f)

    if mode == "lightweight":
        sft_config = all_config["sft_config_lightweight"]
    else:
        sft_config = all_config["sft_config"]

    lora_config = sft_config["lora"]
    train_config = sft_config["training"]

    # Load model
    model, tokenizer = setup_model_and_tokenizer(model_name, mode, quantize)

    # Apply LoRA
    model = setup_lora(model, lora_config)

    # Load data
    if mode == "lightweight":
        dataset = load_training_data_lightweight(benchmark, max_samples=max_samples)
    else:
        dataset = load_training_data(benchmark, max_samples=max_samples)

    # Setup training arguments
    max_seq_length = train_config.get("max_seq_length", 2048)

    training_args = SFTConfig(
        output_dir=str(output_path / "checkpoints"),
        num_train_epochs=train_config.get("num_train_epochs", 3),
        per_device_train_batch_size=train_config.get("per_device_train_batch_size", 4),
        gradient_accumulation_steps=train_config.get("gradient_accumulation_steps", 4),
        learning_rate=train_config.get("learning_rate", 2e-4),
        warmup_ratio=train_config.get("warmup_ratio", 0.1),
        weight_decay=train_config.get("weight_decay", 0.01),
        logging_steps=train_config.get("logging_steps", 10),
        save_strategy=train_config.get("save_strategy", "epoch"),
        optim=train_config.get("optim", "adamw_torch"),
        lr_scheduler_type=train_config.get("lr_scheduler_type", "cosine"),
        bf16=train_config.get("bf16", False) and torch.cuda.is_available(),
        fp16=train_config.get("fp16", False) and torch.cuda.is_available(),
        max_seq_length=max_seq_length,
        dataset_text_field="text",
        report_to="none",
        max_steps=train_config.get("max_steps", -1),
        dataloader_pin_memory=False if mode == "lightweight" else True,
        gradient_checkpointing=True if mode == "full" and torch.cuda.is_available() else False,
    )

    # Create trainer
    trainer = SFTTrainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
        processing_class=tokenizer,
    )

    # Train
    logger.info("=" * 60)
    logger.info(f"Starting training: {model_name} on {benchmark}")
    logger.info(f"Mode: {mode} | Samples: {len(dataset)} | Max seq len: {max_seq_length}")
    logger.info("=" * 60)

    train_result = trainer.train()

    # Save
    final_model_dir = str(output_path / "final_model")
    logger.info(f"Saving model to {final_model_dir}")

    # Merge LoRA weights and save
    merged_model = model.merge_and_unload()
    merged_model.save_pretrained(final_model_dir)
    tokenizer.save_pretrained(final_model_dir)

    # Save training metrics
    elapsed = time.time() - start_time
    metrics = {
        "model": model_name,
        "benchmark": benchmark,
        "mode": mode,
        "train_loss": train_result.training_loss,
        "train_samples": len(dataset),
        "train_time_seconds": elapsed,
        "train_time_formatted": f"{elapsed/3600:.1f}h {(elapsed%3600)/60:.0f}m",
        "lora_r": lora_config["r"],
        "lora_alpha": lora_config["lora_alpha"],
        "learning_rate": train_config["learning_rate"],
    }

    metrics_path = output_path / "training_metrics.json"
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)

    logger.info("=" * 60)
    logger.info(f"Training complete in {metrics['train_time_formatted']}")
    logger.info(f"Final loss: {train_result.training_loss:.4f}")
    logger.info(f"Model saved to: {final_model_dir}")
    logger.info("=" * 60)

    return final_model_dir, metrics


# ─── CLI ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="PostTrainBench Reproduction - Post-train base LLMs on benchmarks"
    )
    parser.add_argument(
        "--model",
        type=str,
        required=True,
        help="HuggingFace model ID (e.g., Qwen/Qwen3-1.7B)",
    )
    parser.add_argument(
        "--benchmark",
        type=str,
        required=True,
        choices=["gsm8k", "humaneval", "gpqamain", "bfcl", "aime2025", "general"],
        help="Target benchmark to optimize for",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        required=True,
        help="Directory to save the trained model and metrics",
    )
    parser.add_argument(
        "--mode",
        type=str,
        default="full",
        choices=["full", "lightweight"],
        help="Training mode: full (GPU) or lightweight (CPU demo)",
    )
    parser.add_argument(
        "--quantize",
        action="store_true",
        help="Use QLoRA (4-bit quantization) - reduces VRAM usage",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to custom training config JSON",
    )
    parser.add_argument(
        "--max-samples",
        type=int,
        default=10000,
        help="Maximum training samples to use",
    )

    args = parser.parse_args()

    final_model_dir, metrics = train(
        model_name=args.model,
        benchmark=args.benchmark,
        output_dir=args.output_dir,
        mode=args.mode,
        quantize=args.quantize,
        config_path=args.config,
        max_samples=args.max_samples,
    )

    print(f"\nDone! Model saved to: {final_model_dir}")
    print(f"Training loss: {metrics['train_loss']:.4f}")
    print(f"Time: {metrics['train_time_formatted']}")


if __name__ == "__main__":
    main()
