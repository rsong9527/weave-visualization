# PostTrainBench Reproduction

Reproducing [PostTrainBench](https://posttrainbench.com/) - measuring how well AI agents can post-train language models.

## What is PostTrainBench?

PostTrainBench is a benchmark that measures the ability of CLI agents (like Claude Code, Codex CLI, Gemini CLI) to post-train pre-trained large language models. The setup:

- **4 target models**: Qwen3-1.7B, Qwen3-4B, SmolLM3-3B, Gemma-3-4B
- **1 H100 GPU** per run
- **10 hours** time limit
- **7 benchmarks**: AIME 2025, Arena Hard, BFCL, GPQA Main, GSM8K, HealthBench, HumanEval

The agent's task is to improve a base LLM's performance on a given benchmark through post-training (SFT, RLHF, etc.).

### Leaderboard Highlights (from posttrainbench.com)

| Method | Average Score |
|---|---|
| Instruction Tuned* | 51.14% |
| GPT-5.2 (Codex CLI) | 21.49% |
| GPT 5.1 Codex Max | 20.16% |
| Gemini 3 Pro | 18.30% |
| Base Model | 18.08% |
| Opus 4.5 (OpenCode) | 17.29% |
| Opus 4.5 (Claude Code) | 17.12% |

*Instruction Tuned is not directly comparable (exceeds 10h + 1 GPU constraint).

## This Reproduction

This project provides scripts to **manually reproduce** the post-training pipeline. Instead of using an AI agent, you directly run the training and evaluation scripts.

### Approach

1. **Supervised Fine-Tuning (SFT)** with **LoRA** adapters on base LLMs
2. **Benchmark-specific training data**: math data for GSM8K, code data for HumanEval, etc.
3. **Evaluation** on the target benchmarks after training
4. **Comparison** with base model performance (before training)

## Quick Start

### 1. Install Dependencies

```bash
pip install -r posttrainbench_repro/requirements_repro.txt
```

### 2. Quick Demo (CPU, ~10 minutes)

```bash
cd posttrainbench_repro
bash scripts/quick_demo.sh
```

This trains a tiny model (SmolLM2-135M) on a small subset of GSM8K data to demonstrate the pipeline.

### 3. Full GPU Run (H100 recommended)

```bash
cd posttrainbench_repro

# Quick: 1 model, 1 benchmark (~1-2 hours)
bash scripts/run_gpu.sh --quick

# Full: all 4 models, 2 benchmarks (~8-10 hours)
bash scripts/run_gpu.sh

# With QLoRA to save VRAM (~20GB instead of ~40GB)
bash scripts/run_gpu.sh --qlora
```

### 4. Individual Model Training

```bash
# Train Qwen3-1.7B on GSM8K
python scripts/post_train.py \
    --model Qwen/Qwen3-1.7B \
    --benchmark gsm8k \
    --output-dir results/qwen3_1.7b_gsm8k \
    --mode full

# Evaluate
python eval/evaluate_gsm8k.py \
    --model-path results/qwen3_1.7b_gsm8k/final_model \
    --limit 200 \
    --output results/qwen3_1.7b_gsm8k/eval.json
```

### 5. Run Multiple Experiments

```bash
# Train specific models on specific benchmarks
python scripts/run_all.py \
    --mode full \
    --models Qwen/Qwen3-1.7B HuggingFaceTB/SmolLM3-3B \
    --benchmarks gsm8k humaneval \
    --eval-limit 200
```

## Project Structure

```
posttrainbench_repro/
├── configs/
│   ├── models.json          # Target model definitions
│   ├── benchmarks.json      # Benchmark configurations
│   └── training_config.json # LoRA and training hyperparameters
├── eval/
│   ├── evaluate_gsm8k.py    # GSM8K evaluation (math reasoning)
│   └── evaluate_humaneval.py # HumanEval evaluation (code generation)
├── scripts/
│   ├── post_train.py        # Main post-training script (SFT + LoRA)
│   ├── run_all.py           # Orchestrator for multiple experiments
│   ├── quick_demo.sh        # Quick CPU demo
│   └── run_gpu.sh           # Full GPU run script
├── results/                 # Output directory for trained models and metrics
├── requirements_repro.txt   # Python dependencies
└── README.md                # This file
```

## How It Works

### Training Pipeline

1. **Load base model** (e.g., Qwen3-1.7B) from HuggingFace
2. **Apply LoRA adapters** (rank 64, alpha 128) to attention and MLP layers
3. **Load benchmark-specific training data**:
   - GSM8K: GSM8K train split + MetaMathQA
   - HumanEval: Python code instructions + CodeAlpaca
   - General: SlimOrca / Alpaca
4. **Fine-tune** with SFT for 3 epochs (cosine LR schedule, AdamW)
5. **Merge LoRA weights** into base model
6. **Save final model** for evaluation

### Evaluation

- **GSM8K**: Generate step-by-step math solutions, extract final numerical answer after `####`, compare with ground truth
- **HumanEval**: Generate Python function completions, execute with test cases, measure pass@1

### Key Configuration

| Parameter | Full Mode | Lightweight Mode |
|---|---|---|
| LoRA rank | 64 | 16 |
| LoRA alpha | 128 | 32 |
| Epochs | 3 | 1 |
| Batch size | 4 | 1 |
| Max seq length | 2048 | 512 |
| Precision | bf16 | fp32 |
| Max samples | 10,000 | 200 |

## Hardware Requirements

| Mode | GPU | VRAM | Time |
|---|---|---|---|
| Full | H100/A100 | 40GB+ | 2-10 hours |
| Full + QLoRA | A100/4090 | 20GB | 2-10 hours |
| Lightweight | CPU | 8GB RAM | 10-30 minutes |

## Comparison with Official PostTrainBench

| Aspect | Official PostTrainBench | This Reproduction |
|---|---|---|
| **Who trains** | AI agent (Claude Code, Codex CLI) | You (human, running scripts) |
| **Models** | Qwen3-1.7B/4B, SmolLM3-3B, Gemma-3-4B | Same models supported |
| **GPU** | H100, 10h limit | Any GPU, no time limit |
| **Benchmarks** | 7 benchmarks | GSM8K + HumanEval (expandable) |
| **Method** | Agent chooses approach | SFT with LoRA (fixed approach) |
| **Container** | Apptainer sandbox | Direct Python execution |

## References

- [PostTrainBench Paper & Website](https://posttrainbench.com/)
- [PostTrainBench GitHub](https://github.com/aisa-group/PostTrainBench)
- [LoRA: Low-Rank Adaptation of Large Language Models](https://arxiv.org/abs/2106.09685)
- [TRL: Transformer Reinforcement Learning](https://github.com/huggingface/trl)
