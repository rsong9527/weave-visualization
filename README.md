# Weave Word Frequency Analysis Demo

This project demonstrates how to use **Weave** and **W&B** for conversation word frequency analysis and visualization.

## Features

1. ✅ Track LLM conversations with Weave
2. ✅ English text tokenization
3. ✅ Word frequency statistics
4. ✅ W&B visualization (tables + charts)
5. ✅ Weave Evaluation integration

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure W&B API Key

```bash
export WANDB_API_KEY=your_api_key_here
```

### 3. Run Word Frequency Analysis

```bash
python weave_word_frequency.py
```

### 4. Run Weave Evaluation

```bash
python weave_evaluation_demo.py
```

### 5. Run Conversation Analysis

```bash
python weave_frequency_as_evaluation.py
```

### 6. Run Factorio Bench Demo

```bash
# Uses the bundled sample data
python factorio_bench_demo.py

# Or run with your own bench results
python factorio_bench_demo.py --input factorio_bench_sample.csv
```

## File Descriptions

| File | Description |
|------|-------------|
| `weave_word_frequency.py` | Main script: word frequency analysis + Weave tracing |
| `weave_evaluation_demo.py` | Weave Evaluation example with multiple scorers |
| `weave_frequency_as_evaluation.py` | Conversation topic analysis as Evaluation |
| `factorio_bench_demo.py` | Factorio benchmark evaluation + W&B table logging |
| `factorio_bench_sample.csv` | Sample Factorio bench dataset (CSV) |
| `requirements.txt` | Python dependencies |

## Factorio Bench Input Format

The bench demo accepts CSV, JSONL, or JSON. Required fields:

- `map_name`: Map or scenario name
- `ticks`: Benchmark ticks
- `total_time_s`: Total time in seconds

Optional fields (auto-detected via aliases):

- `run_id` (default: `run-N`)
- `label` (default: `candidate`, used for baselines)
- `entity_count`, `mod_count`, `save_size_mb`, `build`

If you have a baseline run, set `label=baseline` so the script can compute
regression percentages and status.

To skip W&B logging, run with `--skip-wandb` (Weave tracing still runs).

## Visualization

After running the scripts, you can see in W&B:

1. **Word Frequency Table** - Shows frequency of each word
2. **Bar Charts** - Top high-frequency words visualization
3. **Conversation Stats** - Token counts per conversation
4. **Evaluation Comparison** - Compare metrics across different Evaluations

## Displaying Custom Charts in Workspace

To display Evaluation charts in W&B Workspace:

1. Click **+ Add Panel** in W&B Workspace
2. Select **Custom Chart** or **Table**
3. Choose data source (logged tables)
4. Configure chart type and field mapping

## Reference Documentation

- [Weave Evaluation Docs](https://weave-docs.wandb.ai/guides/core-types/evaluations)
- [W&B Custom Charts](https://docs.wandb.ai/guides/app/features/custom-charts)
- [Weave Trace Plots (Beta)](https://app.getbeamer.com/wandb/en/create-custom-dashboards-using-trace-plots)
