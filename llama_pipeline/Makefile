# =============================================================================
# llama.cpp Pipeline — Makefile
# =============================================================================

.PHONY: help setup download-model server server-stop server-logs \
        ingest run test clean

SHELL := /bin/bash

# Default model (Qwen2.5 7B Instruct, Q4_K_M quantization — ~4.5 GB)
MODEL_NAME   ?= qwen2.5-7b-instruct-q4_k_m.gguf
MODEL_URL    ?= https://huggingface.co/Qwen/Qwen2.5-7B-Instruct-GGUF/resolve/main/qwen2.5-7b-instruct-q4_k_m.gguf
MODEL_DIR    := ./models
MODEL_PATH   := $(MODEL_DIR)/$(MODEL_NAME)

# Server config
SERVER_HOST  ?= 127.0.0.1
SERVER_PORT  ?= 8080

help: ## Show this help
	@echo "llama.cpp Pipeline — available targets:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Quickstart:"
	@echo "  make setup            # install Python deps"
	@echo "  make download-model   # download default GGUF model"
	@echo "  make server           # start llama.cpp via Docker"
	@echo "  make run INPUT=path/to/logs.txt"

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

setup: ## Install Python dependencies
	pip install -r requirements.txt

download-model: ## Download the default GGUF model (~4.5 GB)
	@mkdir -p $(MODEL_DIR)
	@if [ -f "$(MODEL_PATH)" ]; then \
		echo "Model already exists: $(MODEL_PATH)"; \
	else \
		echo "Downloading $(MODEL_NAME) ..."; \
		echo "URL: $(MODEL_URL)"; \
		echo "This will take a while (~4.5 GB) ..."; \
		curl -L -o "$(MODEL_PATH)" "$(MODEL_URL)" || \
		wget -O "$(MODEL_PATH)" "$(MODEL_URL)"; \
		echo "Done: $(MODEL_PATH)"; \
	fi

# ---------------------------------------------------------------------------
# Server management
# ---------------------------------------------------------------------------

server: ## Start llama.cpp server (Docker)
	@echo "Starting llama.cpp server ..."
	LLAMA_MODEL=$(MODEL_NAME) docker compose up -d
	@echo "Server starting at http://$(SERVER_HOST):$(SERVER_PORT)"
	@echo "Health check: curl http://$(SERVER_HOST):$(SERVER_PORT)/health"

server-native: ## Start llama.cpp server (native binary, no Docker)
	@echo "Starting llama.cpp server (native) ..."
	@which llama-server > /dev/null 2>&1 || \
		(echo "ERROR: llama-server not found. Build llama.cpp first:" && \
		 echo "  git clone https://github.com/ggerganov/llama.cpp && cd llama.cpp && make -j" && \
		 exit 1)
	llama-server \
		--model $(MODEL_PATH) \
		--host $(SERVER_HOST) \
		--port $(SERVER_PORT) \
		--ctx-size 2048 \
		--parallel 1 \
		--n-gpu-layers -1 \
		--threads 4 \
		--batch-size 512 \
		--flash-attn

server-stop: ## Stop llama.cpp server (Docker)
	docker compose down

server-logs: ## Tail server logs
	docker compose logs -f

health: ## Check server health
	@curl -sf http://$(SERVER_HOST):$(SERVER_PORT)/health && echo " OK" || echo " FAILED"

# ---------------------------------------------------------------------------
# Pipeline operations
# ---------------------------------------------------------------------------

ingest: ## Ingest documents into RAG: make ingest DOCS=path/to/docs/
	@if [ -z "$(DOCS)" ]; then echo "Usage: make ingest DOCS=path/to/docs/"; exit 1; fi
	python -m pipeline.rag ingest --docs "$(DOCS)"

run: ## Run full pipeline: make run INPUT=path/to/logs.txt
	@if [ -z "$(INPUT)" ]; then echo "Usage: make run INPUT=path/to/logs.txt"; exit 1; fi
	python -m pipeline.runner --input "$(INPUT)"

run-no-review: ## Run pipeline without cloud review
	@if [ -z "$(INPUT)" ]; then echo "Usage: make run-no-review INPUT=path/to/logs.txt"; exit 1; fi
	python -m pipeline.runner --input "$(INPUT)" --no-review

# ---------------------------------------------------------------------------
# Maintenance
# ---------------------------------------------------------------------------

test: ## Run tests
	python -m pytest tests/ -v

clean: ## Clean generated data (keeps models)
	rm -rf ./data/runs/*
	rm -f ./data/vectors.db
	@echo "Cleaned. Models preserved in ./models/"

clean-all: clean ## Clean everything including models
	rm -rf ./models/*.gguf
	@echo "All cleaned including models."
