# K8s/Helm Support Copilot

> **On-Prem, Offline-Capable K8s/Helm Support Copilot**
>
> Not a coding agent. A structured diagnosis tool that outputs copy-pasteable commands, YAML patches, and runbooks.

## What It Does

| Capability | Description |
|-----------|-------------|
| **Diagnose** | Parse kubectl describe/events/logs and produce a 5-section diagnosis |
| **Install** | Generate a complete install pack (install.sh, values.yaml, validate.sh, rollback.sh) |
| **Config Fix** | Suggest YAML/Helm configuration fixes with evidence citations |
| **Runbook** | Convert resolved incidents into reusable runbooks |

## What It Does NOT Do

- Write application code
- Execute commands on your cluster
- Hallucinate cluster state (requires real evidence as input)

## Quick Start

### 1. Install

```bash
cd k8s-copilot
pip install -e ".[dev]"
```

### 2. Start a Local LLM (Ollama)

```bash
# Install Ollama: https://ollama.ai
ollama pull qwen2.5:7b
ollama serve
```

### 3. Diagnose an Issue

```bash
# Using a pre-collected evidence file
python -m k8s_copilot diagnose --evidence examples/evidence_crashloop.json

# Auto-collect evidence from your cluster
python -m k8s_copilot collect --pod my-pod --namespace default -o evidence.json
python -m k8s_copilot diagnose --evidence evidence.json
```

### 4. Generate an Install Plan

```bash
python -m k8s_copilot install --component cert-manager --namespace cert-manager --save-dir ./output
```

### 5. Create a Runbook

```bash
# From a built-in template
python -m k8s_copilot runbook --template crashloopbackoff --title "Our CrashLoop Incident"

# List available templates
python -m k8s_copilot runbook --list-templates
```

## Evidence Bundle

The copilot requires structured evidence as input — this prevents hallucination.

### Required Fields
| Field | Source Command |
|-------|---------------|
| `pods_overview` | `kubectl get pods -A -o wide` |
| `cluster_info` | `kubectl version && kubectl cluster-info` |

### Task-Specific Fields
| Field | Source Command | When |
|-------|---------------|------|
| `pod_describe` | `kubectl describe pod <x> -n <ns>` | Troubleshooting |
| `pod_logs` | `kubectl logs <x> -n <ns> --tail=200` | Troubleshooting |
| `events` | `kubectl get events --sort-by=.lastTimestamp -A` | Troubleshooting |
| `helm_list` | `helm list -A` | Helm issues |
| `values_yaml` | Your values.yaml | Config fixes |

See `examples/` for complete evidence bundle samples.

## Output Format (5-Section Diagnosis)

Every diagnostic response follows this mandatory structure:

1. **Diagnosis** — Observed symptoms with evidence citations
2. **Root Cause** — Hypothesis + evidence chain + missing info
3. **Next Steps** — P0/P1/P2 prioritized actions with expected results
4. **Commands/YAML** — Copy-pasteable commands and valid YAML patches
5. **Rollback + Message** — How to undo + stakeholder communication

## Hard Constraints

| Rule | Description |
|------|-------------|
| R1 | No large code changes (>50 lines) |
| R2 | Only outputs: YAML / Helm / commands / runbooks |
| R3 | Every conclusion must cite evidence |
| R4 | Must list missing information if uncertain |
| R5 | Must include rollback procedure |
| R6 | Commands must be fully qualified and copy-pasteable |
| R7 | YAML must include apiVersion/kind/metadata |

## Architecture

```
Evidence Bundle (JSON) → Parser → System Prompt + LLM → Output Formatter → 5-Section Report
```

### Supported LLM Backends
- **Ollama** (recommended for on-prem): `ollama run qwen2.5:7b`
- **vLLM**: High-throughput for multi-user
- **llama.cpp**: Lightest weight, CPU-compatible
- Any OpenAI-compatible API

### Recommended Models
| Model | Size | Best For |
|-------|------|----------|
| Qwen-2.5-7B-Instruct | 7B | Chinese + English |
| Llama-3.1-8B-Instruct | 8B | English |
| Mistral-7B-Instruct | 7B | Low-resource |
| Phi-3-mini-4k | 3.8B | Edge/minimal |

## Project Structure

```
k8s-copilot/
├── DESIGN.md              # Full product design document
├── README.md              # This file
├── pyproject.toml         # Project configuration
├── copilot.py             # Core engine (Evidence → LLM → Output)
├── cli.py                 # CLI interface
├── prompts/
│   └── system_prompt.py   # System prompt + hard constraints
├── schemas/
│   └── evidence_bundle.py # Input schema (Pydantic v2)
├── formatters/
│   └── output_formatter.py # 5-section output parser & validator
├── generators/
│   ├── install_plan.py    # Install pack generator (5 files)
│   └── runbook.py         # Runbook templates & generator
├── examples/
│   ├── evidence_crashloop.json
│   ├── evidence_helm_upgrade.json
│   └── evidence_install.json
└── tests/
    ├── test_evidence_bundle.py
    ├── test_output_formatter.py
    ├── test_install_plan.py
    └── test_runbook.py
```

## Running Tests

```bash
cd k8s-copilot
pip install -e ".[dev]"
pytest tests/ -v
```

## Design Document

See [DESIGN.md](DESIGN.md) for the full product design, architecture decisions, and roadmap.
