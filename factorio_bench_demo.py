"""
Factorio benchmark demo using Weave and W&B.

This script loads Factorio benchmark runs from CSV/JSON/JSONL, computes
derived performance metrics (UPS, ms/tick), and logs them via Weave and
optional W&B workspace tables.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import statistics
import sys
from typing import Any, Iterable

import weave
import wandb

FIELD_ALIASES = {
    "run_id": ["run_id", "id", "run"],
    "map_name": ["map_name", "map", "scenario", "save_name"],
    "ticks": ["ticks", "tick_count", "benchmark_ticks"],
    "total_time_s": ["total_time_s", "time_s", "total_time_sec", "seconds"],
    "label": ["label", "branch", "variant", "tag"],
    "entity_count": ["entity_count", "entities"],
    "mod_count": ["mod_count", "mods"],
    "save_size_mb": ["save_size_mb", "save_mb", "save_size"],
    "build": ["build", "version"],
}

OPTIONAL_FIELDS = {"entity_count", "mod_count", "save_size_mb", "build"}

SAMPLE_RUNS = [
    {
        "run_id": "baseline-1",
        "map_name": "train_grid",
        "ticks": 10000,
        "total_time_s": 5.00,
        "entity_count": 120000,
        "mod_count": 12,
        "label": "baseline",
        "build": "1.1.100",
    },
    {
        "run_id": "candidate-1",
        "map_name": "train_grid",
        "ticks": 10000,
        "total_time_s": 5.30,
        "entity_count": 120000,
        "mod_count": 12,
        "label": "candidate",
        "build": "1.1.100+pr42",
    },
    {
        "run_id": "baseline-2",
        "map_name": "mega_base",
        "ticks": 10000,
        "total_time_s": 8.20,
        "entity_count": 350000,
        "mod_count": 22,
        "label": "baseline",
        "build": "1.1.100",
    },
    {
        "run_id": "candidate-2",
        "map_name": "mega_base",
        "ticks": 10000,
        "total_time_s": 7.90,
        "entity_count": 350000,
        "mod_count": 22,
        "label": "candidate",
        "build": "1.1.100+pr42",
    },
]


def _pick_field(raw: dict[str, Any], aliases: Iterable[str]) -> Any:
    for name in aliases:
        if name in raw and raw[name] not in ("", None):
            return raw[name]
    return None


def _coerce_int(value: Any, field_name: str) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid {field_name} value: {value!r}") from exc


def _coerce_float(value: Any, field_name: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid {field_name} value: {value!r}") from exc


def normalize_run(raw: dict[str, Any], index: int) -> dict[str, Any]:
    run_id = _pick_field(raw, FIELD_ALIASES["run_id"]) or f"run-{index}"
    map_name = _pick_field(raw, FIELD_ALIASES["map_name"])
    ticks = _pick_field(raw, FIELD_ALIASES["ticks"])
    total_time_s = _pick_field(raw, FIELD_ALIASES["total_time_s"])
    label = _pick_field(raw, FIELD_ALIASES["label"]) or "candidate"

    if map_name is None:
        raise ValueError("Missing map_name")
    if ticks is None:
        raise ValueError("Missing ticks")
    if total_time_s is None:
        raise ValueError("Missing total_time_s")

    normalized = {
        "run_id": str(run_id),
        "map_name": str(map_name),
        "ticks": _coerce_int(ticks, "ticks"),
        "total_time_s": _coerce_float(total_time_s, "total_time_s"),
        "label": str(label),
    }

    for field in OPTIONAL_FIELDS:
        value = _pick_field(raw, FIELD_ALIASES[field])
        if value is None:
            continue
        if field in {"entity_count", "mod_count"}:
            normalized[field] = _coerce_int(value, field)
        elif field == "save_size_mb":
            normalized[field] = _coerce_float(value, field)
        else:
            normalized[field] = str(value)

    if normalized["ticks"] <= 0:
        raise ValueError("ticks must be > 0")
    if normalized["total_time_s"] <= 0:
        raise ValueError("total_time_s must be > 0")

    return normalized


def _load_json(path: str) -> list[dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if isinstance(data, dict) and isinstance(data.get("runs"), list):
        return data["runs"]
    if isinstance(data, list):
        return data
    raise ValueError("JSON must be a list or contain a 'runs' list")


def _load_jsonl(path: str) -> list[dict[str, Any]]:
    runs = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            runs.append(json.loads(line))
    return runs


def _load_csv(path: str) -> list[dict[str, Any]]:
    with open(path, "r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader)


def load_runs(path: str | None) -> list[dict[str, Any]]:
    if not path:
        return [normalize_run(run, index + 1) for index, run in enumerate(SAMPLE_RUNS)]

    if not os.path.exists(path):
        raise FileNotFoundError(f"Input file not found: {path}")

    ext = os.path.splitext(path)[1].lower()
    if ext == ".csv":
        raw_runs = _load_csv(path)
    elif ext == ".jsonl":
        raw_runs = _load_jsonl(path)
    elif ext == ".json":
        raw_runs = _load_json(path)
    else:
        raise ValueError("Unsupported input format. Use CSV, JSONL, or JSON.")

    runs = []
    for index, raw in enumerate(raw_runs, start=1):
        runs.append(normalize_run(raw, index))
    return runs


@weave.op()
def compute_run_metrics(run: dict[str, Any]) -> dict[str, Any]:
    ticks = run["ticks"]
    total_time_s = run["total_time_s"]
    ups = ticks / max(total_time_s, 1e-9)
    ms_per_tick = (total_time_s * 1000.0) / max(ticks, 1)
    metrics = {
        "ups": ups,
        "ms_per_tick": ms_per_tick,
    }
    metrics.update(run)
    return metrics


@weave.op()
def build_baseline_index(
    runs: list[dict[str, Any]], baseline_label: str
) -> dict[str, dict[str, Any]]:
    by_map: dict[str, list[dict[str, Any]]] = {}
    for run in runs:
        if run.get("label") != baseline_label:
            continue
        metrics = compute_run_metrics(run)
        by_map.setdefault(run["map_name"], []).append(metrics)

    baseline_index: dict[str, dict[str, Any]] = {}
    for map_name, metrics_list in by_map.items():
        baseline_index[map_name] = {
            "baseline_ups": statistics.mean(m["ups"] for m in metrics_list),
            "baseline_ms_per_tick": statistics.mean(
                m["ms_per_tick"] for m in metrics_list
            ),
            "baseline_runs": len(metrics_list),
        }
    return baseline_index


def classify_regression(regression_pct: float | None, threshold: float) -> str:
    if regression_pct is None:
        return "no_baseline"
    if regression_pct <= -threshold:
        return "regression"
    if regression_pct >= threshold:
        return "improvement"
    return "neutral"


def make_regression_scorer(
    baseline_index: dict[str, dict[str, Any]], threshold: float
):
    @weave.op()
    def regression_scorer(run: dict[str, Any], model_output: dict[str, Any]) -> dict[str, Any]:
        metrics = compute_run_metrics(model_output)
        baseline = baseline_index.get(metrics["map_name"])
        if not baseline:
            return {
                "baseline_available": 0,
                "ups_regression_pct": None,
                "baseline_ups": None,
                "baseline_ms_per_tick": None,
                "regression_status": "no_baseline",
            }

        ups_delta = metrics["ups"] - baseline["baseline_ups"]
        regression_pct = ups_delta / max(baseline["baseline_ups"], 1e-9)

        return {
            "baseline_available": 1,
            "baseline_ups": baseline["baseline_ups"],
            "baseline_ms_per_tick": baseline["baseline_ms_per_tick"],
            "ups_regression_pct": regression_pct,
            "regression_status": classify_regression(regression_pct, threshold),
        }

    return regression_scorer


@weave.op()
def bench_metrics_scorer(run: dict[str, Any], model_output: dict[str, Any]) -> dict[str, Any]:
    metrics = compute_run_metrics(model_output)
    return {
        "ups": metrics["ups"],
        "ms_per_tick": metrics["ms_per_tick"],
        "map_name": metrics["map_name"],
        "label": metrics.get("label", ""),
        "entity_count": metrics.get("entity_count"),
        "mod_count": metrics.get("mod_count"),
    }


def build_report_rows(
    runs: list[dict[str, Any]],
    baseline_index: dict[str, dict[str, Any]],
    threshold: float,
) -> list[dict[str, Any]]:
    rows = []
    for run in runs:
        metrics = compute_run_metrics(run)
        baseline = baseline_index.get(metrics["map_name"])
        regression_pct = None
        if baseline:
            regression_pct = (metrics["ups"] - baseline["baseline_ups"]) / max(
                baseline["baseline_ups"], 1e-9
            )

        rows.append(
            {
                "run_id": metrics["run_id"],
                "map_name": metrics["map_name"],
                "label": metrics.get("label", ""),
                "build": metrics.get("build", ""),
                "ticks": metrics["ticks"],
                "total_time_s": metrics["total_time_s"],
                "ups": metrics["ups"],
                "ms_per_tick": metrics["ms_per_tick"],
                "entity_count": metrics.get("entity_count"),
                "mod_count": metrics.get("mod_count"),
                "baseline_ups": None if not baseline else baseline["baseline_ups"],
                "ups_regression_pct": regression_pct,
                "regression_status": classify_regression(regression_pct, threshold),
            }
        )

    return rows


def summarize_rows(rows: list[dict[str, Any]], baseline_label: str) -> dict[str, Any]:
    ups_values = [row["ups"] for row in rows]
    summary: dict[str, Any] = {
        "runs_total": len(rows),
        "avg_ups": statistics.mean(ups_values) if ups_values else 0.0,
    }

    baseline_ups = [row["ups"] for row in rows if row.get("label") == baseline_label]
    candidate_ups = [row["ups"] for row in rows if row.get("label") != baseline_label]

    if baseline_ups:
        summary["avg_baseline_ups"] = statistics.mean(baseline_ups)
    if candidate_ups:
        summary["avg_candidate_ups"] = statistics.mean(candidate_ups)

    regression_values = [
        row["ups_regression_pct"]
        for row in rows
        if row.get("ups_regression_pct") is not None
    ]
    if regression_values:
        summary["worst_regression_pct"] = min(regression_values)
        summary["best_improvement_pct"] = max(regression_values)

    return summary


def resolve_wandb_mode(args: argparse.Namespace) -> str:
    if args.skip_wandb:
        return "disabled"
    if args.wandb_mode:
        return args.wandb_mode
    return "online" if os.getenv("WANDB_API_KEY") else "disabled"


def log_wandb(
    rows: list[dict[str, Any]],
    summary: dict[str, Any],
    project: str,
    run_name: str | None,
    mode: str,
) -> wandb.sdk.wandb_run.Run | None:
    if mode == "disabled":
        return None

    run = wandb.init(project=project, name=run_name, mode=mode, config=summary)

    columns = list(rows[0].keys()) if rows else []
    table = wandb.Table(columns=columns)
    for row in rows:
        table.add_data(*[row.get(col) for col in columns])

    wandb.log({"bench_runs": table})
    wandb.log({f"summary/{key}": value for key, value in summary.items()})
    return run


class BenchPassThroughModel(weave.Model):
    @weave.op()
    async def predict(self, run: dict[str, Any]) -> dict[str, Any]:
        return run


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Factorio bench Weave demo")
    parser.add_argument("--input", help="CSV/JSON/JSONL benchmark data path")
    parser.add_argument("--project", default="factorio-bench-demo", help="Weave project")
    parser.add_argument(
        "--wandb-project", default="factorio-bench-demo", help="W&B project"
    )
    parser.add_argument("--wandb-mode", choices=["online", "offline", "disabled"])
    parser.add_argument("--skip-wandb", action="store_true")
    parser.add_argument("--baseline-label", default="baseline")
    parser.add_argument("--regression-threshold", type=float, default=0.02)
    parser.add_argument("--run-name", default=None)
    return parser.parse_args()


async def run_demo() -> int:
    args = parse_args()
    try:
        runs = load_runs(args.input)
    except (ValueError, FileNotFoundError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Loaded {len(runs)} benchmark runs")

    weave.init(args.project)

    baseline_index = build_baseline_index(runs, args.baseline_label)
    regression_scorer = make_regression_scorer(
        baseline_index, args.regression_threshold
    )

    dataset = [{"run": run} for run in runs]
    evaluation = weave.Evaluation(
        name="factorio_bench_evaluation",
        dataset=dataset,
        scorers=[bench_metrics_scorer, regression_scorer],
    )

    model = BenchPassThroughModel()
    await evaluation.evaluate(model)

    rows = build_report_rows(runs, baseline_index, args.regression_threshold)
    summary = summarize_rows(rows, args.baseline_label)

    wandb_mode = resolve_wandb_mode(args)
    run = log_wandb(rows, summary, args.wandb_project, args.run_name, wandb_mode)

    print("Summary:")
    for key, value in summary.items():
        print(f"  {key}: {value}")

    if run:
        run.finish()
        print(f"W&B workspace: {run.url}")

    print("Done. Check your Weave project for evaluation charts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run_demo()))
