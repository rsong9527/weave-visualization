"""
Inference: llama.cpp OpenAI-compatible API client.

Talks to the local llama.cpp server via its /v1/chat/completions endpoint.
No OpenAI SDK needed — just plain HTTP requests.
"""

import json
import logging
import time
from pathlib import Path
from typing import Optional

import requests
import yaml

logger = logging.getLogger(__name__)


class LlamaClient:
    """Client for the local llama.cpp server (OpenAI-compatible API)."""

    def __init__(self, config_path: str = "config.yaml"):
        with open(config_path) as fh:
            cfg = yaml.safe_load(fh)

        server_cfg = cfg.get("server", {})
        inf_cfg = cfg.get("inference", {})

        self.base_url = server_cfg.get("base_url", "http://127.0.0.1:8080/v1")
        self.temperature = inf_cfg.get("temperature", 0.3)
        self.top_p = inf_cfg.get("top_p", 0.9)
        self.top_k = inf_cfg.get("top_k", 40)
        self.max_tokens = inf_cfg.get("max_tokens", 1024)
        self.repeat_penalty = inf_cfg.get("repeat_penalty", 1.1)
        self.stop = inf_cfg.get("stop", [])
        self.timeout = inf_cfg.get("timeout", 120)

    def health_check(self) -> bool:
        """Check if the llama.cpp server is reachable."""
        try:
            # llama.cpp health endpoint is at the root, not under /v1
            base = self.base_url.replace("/v1", "")
            resp = requests.get(f"{base}/health", timeout=5)
            return resp.status_code == 200
        except requests.RequestException:
            return False

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Send a chat completion request to the llama.cpp server.

        Args:
            messages: List of {"role": "...", "content": "..."} messages.
            temperature: Override default temperature.
            max_tokens: Override default max_tokens.

        Returns:
            The assistant's response text.
        """
        url = f"{self.base_url}/chat/completions"

        payload = {
            "messages": messages,
            "temperature": temperature if temperature is not None else self.temperature,
            "top_p": self.top_p,
            "top_k": self.top_k,
            "max_tokens": max_tokens or self.max_tokens,
            "repeat_penalty": self.repeat_penalty,
            "stop": self.stop,
            "stream": False,
        }

        logger.debug(f"POST {url}")
        logger.debug(f"Payload: {json.dumps(payload, indent=2)[:500]}")

        start = time.time()
        try:
            resp = requests.post(url, json=payload, timeout=self.timeout)
            resp.raise_for_status()
        except requests.ConnectionError:
            raise RuntimeError(
                f"Cannot connect to llama.cpp server at {self.base_url}. "
                f"Is it running? Try: make server"
            )
        except requests.Timeout:
            raise RuntimeError(
                f"llama.cpp server timed out after {self.timeout}s. "
                f"Try reducing max_tokens or ctx size."
            )
        except requests.HTTPError as e:
            raise RuntimeError(f"llama.cpp server error: {e}\n{resp.text}")

        elapsed = time.time() - start
        data = resp.json()

        # Extract response
        choices = data.get("choices", [])
        if not choices:
            raise RuntimeError(f"No choices in response: {data}")

        content = choices[0].get("message", {}).get("content", "")

        # Log stats
        usage = data.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        tokens_per_sec = completion_tokens / elapsed if elapsed > 0 else 0

        logger.info(
            f"Inference: {prompt_tokens} prompt + {completion_tokens} completion tokens, "
            f"{elapsed:.1f}s ({tokens_per_sec:.1f} tok/s)"
        )

        return content.strip()

    def generate_runbook(
        self,
        facts_text: str,
        context_text: str,
        prompt_template_path: str = "prompts/runbook.txt",
    ) -> str:
        """
        Generate a runbook/patch draft from facts and context.

        Args:
            facts_text: Structured facts (from parser).
            context_text: Retrieved context (from RAG).
            prompt_template_path: Path to the prompt template.

        Returns:
            The generated runbook text.
        """
        template_path = Path(prompt_template_path)
        if template_path.exists():
            template = template_path.read_text()
        else:
            logger.warning(f"Prompt template not found: {prompt_template_path}, using default")
            template = (
                "Given the following facts and context, produce a step-by-step runbook.\n\n"
                "## Facts\n{facts}\n\n"
                "## Context\n{context}\n\n"
                "## Runbook\n"
            )

        prompt = template.format(facts=facts_text, context=context_text)

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a precise on-premise support agent. "
                    "Respond with actionable runbook steps only. "
                    "Do not hallucinate information not present in the facts/context."
                ),
            },
            {"role": "user", "content": prompt},
        ]

        return self.chat(messages)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    ap = argparse.ArgumentParser(description="llama.cpp inference client")
    sub = ap.add_subparsers(dest="command")

    # health
    sub.add_parser("health", help="Check server health")

    # chat
    chat_p = sub.add_parser("chat", help="Interactive chat")
    chat_p.add_argument("--config", default="config.yaml")

    # generate
    gen_p = sub.add_parser("generate", help="Generate from prompt")
    gen_p.add_argument("prompt", help="Prompt text or @file")
    gen_p.add_argument("--config", default="config.yaml")

    args = ap.parse_args()

    if args.command == "health":
        client = LlamaClient()
        ok = client.health_check()
        print(f"Server health: {'OK' if ok else 'FAILED'}")

    elif args.command == "chat":
        client = LlamaClient(config_path=args.config)
        print("Chat with llama.cpp (type 'quit' to exit)")
        messages = []
        while True:
            try:
                user_input = input("\nYou: ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if user_input.lower() in ("quit", "exit", "q"):
                break
            messages.append({"role": "user", "content": user_input})
            response = client.chat(messages)
            print(f"\nAssistant: {response}")
            messages.append({"role": "assistant", "content": response})

    elif args.command == "generate":
        client = LlamaClient(config_path=args.config)
        prompt = args.prompt
        if prompt.startswith("@"):
            prompt = Path(prompt[1:]).read_text()
        messages = [{"role": "user", "content": prompt}]
        response = client.chat(messages)
        print(response)

    else:
        ap.print_help()


if __name__ == "__main__":
    main()
