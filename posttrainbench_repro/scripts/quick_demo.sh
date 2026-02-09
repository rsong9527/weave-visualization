#!/bin/bash
# =============================================================================
# PostTrainBench Quick Demo
# 
# A lightweight demo that runs on CPU with tiny models to demonstrate
# the post-training pipeline. For real results, use an H100 GPU.
#
# Usage:
#   bash scripts/quick_demo.sh
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "=============================================="
echo "  PostTrainBench Reproduction - Quick Demo"
echo "=============================================="
echo ""
echo "This demo will:"
echo "  1. Download a tiny model (SmolLM2-135M or Qwen2.5-0.5B)"
echo "  2. Post-train it on GSM8K math data"
echo "  3. Evaluate before and after training"
echo ""
echo "Note: This runs on CPU with minimal data."
echo "      For real results, use an H100 GPU with full models."
echo ""

# Install dependencies if needed
echo "[1/5] Checking dependencies..."
pip install -q torch transformers datasets peft trl accelerate 2>/dev/null || true

# Select model based on available memory
echo "[2/5] Selecting model..."
MODEL="HuggingFaceTB/SmolLM2-135M"
BENCHMARK="gsm8k"
OUTPUT_DIR="results/demo_${BENCHMARK}"
MAX_SAMPLES=50

echo "  Model:     $MODEL"
echo "  Benchmark: $BENCHMARK"
echo "  Samples:   $MAX_SAMPLES"
echo ""

# Run post-training
echo "[3/5] Post-training (this may take 5-15 minutes on CPU)..."
python scripts/post_train.py \
    --model "$MODEL" \
    --benchmark "$BENCHMARK" \
    --output-dir "$OUTPUT_DIR" \
    --mode lightweight \
    --max-samples "$MAX_SAMPLES"

# Evaluate
echo ""
echo "[4/5] Evaluating post-trained model on GSM8K..."
python eval/evaluate_gsm8k.py \
    --model-path "$OUTPUT_DIR/final_model" \
    --limit 20 \
    --output "$OUTPUT_DIR/eval_results.json"

# Summary
echo ""
echo "[5/5] Done!"
echo ""
echo "=============================================="
echo "  Results Summary"
echo "=============================================="
if [ -f "$OUTPUT_DIR/training_metrics.json" ]; then
    echo "Training metrics:"
    python -c "
import json
with open('$OUTPUT_DIR/training_metrics.json') as f:
    m = json.load(f)
    print(f'  Loss: {m[\"train_loss\"]:.4f}')
    print(f'  Time: {m[\"train_time_formatted\"]}')
    print(f'  Samples: {m[\"train_samples\"]}')
"
fi
if [ -f "$OUTPUT_DIR/eval_results.json" ]; then
    echo "Evaluation metrics:"
    python -c "
import json
with open('$OUTPUT_DIR/eval_results.json') as f:
    m = json.load(f)['metrics']
    score = m.get('accuracy', m.get('pass_at_1', 0))
    print(f'  Score: {score:.2f}%')
    print(f'  Correct: {m[\"correct\"]}/{m[\"total\"]}')
"
fi
echo ""
echo "Full results saved to: $OUTPUT_DIR/"
echo ""
echo "To run the full benchmark on GPU:"
echo "  python scripts/run_all.py --mode full --models Qwen/Qwen3-1.7B --benchmarks gsm8k"
