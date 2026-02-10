# llama.cpp Local Inference Pipeline

**"解费用咒术" Edition** — local inference for the heavy lifting, cloud only for review.

```
logs/input ──→ Parser (CPU) ──→ facts.json
                                    │
                              RAG (SQLite) ──→ top-k context
                                    │
                           llama.cpp (7B local) ──→ draft runbook
                                    │
                          Cloud LLM (one-shot) ──→ review + RCA (optional)
```

## Design Principles

1. **The model never sees raw logs.** Parser extracts structured facts first. The model makes decisions on clean data, not garbage.
2. **Local does the heavy lifting.** A Q4-quantized 7B model handles runbook generation at ~30 tok/s on consumer GPUs.
3. **Cloud is optional and one-shot.** If enabled, a single cloud API call reviews the draft. That's it.
4. **Context is controlled.** `n_ctx=2048`, `n_parallel=1` by default. You tune up only after you measure.

## Quickstart

### 1. Install dependencies

```bash
cd llama_pipeline
pip install -r requirements.txt
```

### 2. Download a GGUF model

```bash
make download-model
```

Default: [Qwen2.5-7B-Instruct Q4_K_M](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct-GGUF) (~4.5 GB).

You can use any GGUF model. Set `MODEL_NAME` and `MODEL_URL`:

```bash
make download-model MODEL_NAME=mistral-7b-instruct-v0.3.Q4_K_M.gguf \
    MODEL_URL=https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.3-GGUF/resolve/main/mistral-7b-instruct-v0.3.Q4_K_M.gguf
```

### 3. Start the llama.cpp server

**Docker (recommended):**

```bash
make server
```

**Native (if you compiled llama.cpp):**

```bash
make server-native
```

Verify:

```bash
make health
# → OK
```

### 4. (Optional) Ingest knowledge base

```bash
make ingest DOCS=path/to/your/runbooks/
```

This builds the SQLite vector store so the pipeline can retrieve relevant context.

### 5. Run the pipeline

```bash
make run INPUT=data/sample_logs.txt
```

Without cloud review:

```bash
make run-no-review INPUT=data/sample_logs.txt
```

## Architecture

```
llama_pipeline/
├── config.yaml              # All tunable parameters
├── docker-compose.yml       # llama.cpp server (Docker)
├── Makefile                 # Common operations
├── requirements.txt         # Python dependencies
├── pipeline/
│   ├── __init__.py
│   ├── __main__.py          # python -m pipeline
│   ├── parser.py            # Stage 1: logs → structured facts
│   ├── rag.py               # Stage 2: SQLite vector store + retrieval
│   ├── inference.py         # Stage 3: llama.cpp API client
│   ├── reviewer.py          # Stage 4: cloud review (optional)
│   └── runner.py            # Orchestrator
├── prompts/
│   ├── runbook.txt          # Prompt template for runbook generation
│   └── review.txt           # Prompt template for cloud review
├── models/                  # GGUF model files (git-ignored)
├── data/                    # Pipeline artifacts
│   ├── sample_logs.txt      # Example input
│   └── runs/                # Per-run artifacts (facts, context, draft, review)
└── tests/
    └── test_parser.py       # Parser unit tests
```

## Configuration

All parameters live in `config.yaml`. Key settings:

| Parameter | Default | Why |
|-----------|---------|-----|
| `server.n_ctx` | `2048` | Start small. 2k is enough for structured facts. |
| `server.n_parallel` | `1` | One request at a time. Bump only after benchmarking. |
| `server.n_gpu_layers` | `-1` | Offload all layers to GPU. Set `0` for CPU-only. |
| `inference.temperature` | `0.3` | Low temperature for deterministic runbooks. |
| `inference.max_tokens` | `1024` | Cap output length. |
| `rag.top_k` | `5` | Number of context chunks to retrieve. |
| `rag.embedding_model` | `all-MiniLM-L6-v2` | Small, fast, CPU-friendly embeddings. |
| `reviewer.enabled` | `false` | Cloud review off by default. |

### Environment Variables (Docker)

Override via env vars without touching config:

```bash
LLAMA_MODEL=your-model.gguf LLAMA_CTX=4096 docker compose up -d
```

## Common Pitfalls (Pre-filled)

### "显存不够" — actually ctx too long + concurrency too high

- Default: `n_ctx=2048`, `n_parallel=1`
- A 7B Q4 model needs ~4-5 GB VRAM at ctx=2048
- Each parallel slot adds memory. Don't set parallel=4 on 8 GB VRAM.

### "模型不行" — actually the input isn't structured

- The parser extracts facts FIRST. The model never sees raw logs.
- If results are bad, check `data/runs/<id>/facts.json` — are the facts correct?
- Tune parser patterns in `config.yaml` before blaming the model.

### "需要 30B+" — actually 7B is fine for support work

- 7B models at Q4 are enough for: runbook generation, log summarization, patch drafts.
- Use cloud (GPT-4o / Claude) only for review and root-cause analysis.
- Cost: local = electricity + depreciation. Cloud = one API call per incident.

## Cost Model

| Component | Cost | When |
|-----------|------|------|
| Parser | ~0 | CPU, instant |
| RAG | ~0 | CPU, sentence-transformers |
| llama.cpp (7B) | Electricity | Every request, ~2-5s |
| Cloud review | ~$0.01-0.05 | Once per incident (optional) |

For a support agent handling 100 incidents/day with cloud review enabled:
- Local cost: negligible (your GPU is already depreciating)
- Cloud cost: ~$1-5/day

## Testing

```bash
make test
```

## Cleanup

```bash
make clean       # Remove run artifacts, keep models
make clean-all   # Remove everything including models
```
