#!/bin/bash
# =============================================================================
# PostTrainBench Full GPU Run
#
# Runs the full PostTrainBench reproduction on GPU (H100 recommended).
# This trains all 4 target models on GSM8K and HumanEval benchmarks.
#
# Prerequisites:
#   - NVIDIA GPU (H100 recommended, A100/4090 also work)
#   - ~40GB VRAM for full models, ~20GB with QLoRA
#   - Python packages: torch, transformers, datasets, peft, trl, vllm
#
# Usage:
#   bash scripts/run_gpu.sh               # Full run (all models, all benchmarks)
#   bash scripts/run_gpu.sh --quick       # Quick run (1 model, 1 benchmark)
#   bash scripts/run_gpu.sh --qlora       # QLoRA mode (saves VRAM)
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# Parse arguments
QUICK=false
QLORA=false
for arg in "$@"; do
    case $arg in
        --quick) QUICK=true ;;
        --qlora) QLORA=true ;;
    esac
done

echo "=============================================="
echo "  PostTrainBench Reproduction - GPU Run"
echo "=============================================="

# Check GPU
nvidia-smi || { echo "ERROR: No GPU detected!"; exit 1; }
echo ""

# Install dependencies
echo "Installing dependencies..."
pip install -q torch transformers datasets peft trl accelerate bitsandbytes vllm 2>/dev/null || true

if $QUICK; then
    echo "Quick mode: Training 1 model on 1 benchmark"
    MODELS="Qwen/Qwen3-1.7B"
    BENCHMARKS="gsm8k"
    MAX_SAMPLES=5000
    EVAL_LIMIT=100
else
    echo "Full mode: Training all models on all benchmarks"
    MODELS="Qwen/Qwen3-1.7B Qwen/Qwen3-4B HuggingFaceTB/SmolLM3-3B google/gemma-3-4b"
    BENCHMARKS="gsm8k humaneval"
    MAX_SAMPLES=10000
    EVAL_LIMIT=-1
fi

EXTRA_ARGS=""
if $QLORA; then
    echo "Using QLoRA (4-bit quantization)"
    EXTRA_ARGS="--quantize"
fi

echo ""
echo "Models: $MODELS"
echo "Benchmarks: $BENCHMARKS"
echo ""

# Run
python scripts/run_all.py \
    --mode full \
    --models $MODELS \
    --benchmarks $BENCHMARKS \
    --max-samples $MAX_SAMPLES \
    --eval-limit $EVAL_LIMIT \
    $EXTRA_ARGS

echo ""
echo "Done! Check the results/ directory for detailed outputs."
