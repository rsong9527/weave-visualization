"""
Reviewer: optional cloud model review + RCA polish.

This is the ONE cloud call in the entire pipeline.
Use it for review / root-cause-analysis / polish — not for the heavy lifting.

"大模型只做 review，不做搬砖"
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)


class CloudReviewer:
    """Send a draft to a cloud LLM for review. One-shot, optional."""

    def __init__(self, config_path: str = "config.yaml"):
        with open(config_path) as fh:
            cfg = yaml.safe_load(fh)

        rev_cfg = cfg.get("reviewer", {})
        self.enabled = rev_cfg.get("enabled", False)
        self.provider = rev_cfg.get("provider", "openai")
        self.model = rev_cfg.get("model", "gpt-4o-mini")
        self.max_tokens = rev_cfg.get("max_tokens", 2048)
        self.temperature = rev_cfg.get("temperature", 0.4)

        # API key from env
        api_key_env = rev_cfg.get("api_key_env", "OPENAI_API_KEY")
        self.api_key = os.environ.get(api_key_env, "")

    def is_available(self) -> bool:
        """Check if cloud review is configured and available."""
        if not self.enabled:
            return False
        if not self.api_key:
            logger.warning(
                f"Cloud reviewer enabled but API key not found. "
                f"Set the environment variable specified in config.yaml."
            )
            return False
        return True

    def review(
        self,
        facts_text: str,
        draft_text: str,
        prompt_template_path: str = "prompts/review.txt",
    ) -> Optional[str]:
        """
        Send draft for cloud review.

        Args:
            facts_text: Original structured facts.
            draft_text: Draft runbook from local model.
            prompt_template_path: Path to review prompt template.

        Returns:
            Review text, or None if review is disabled/unavailable.
        """
        if not self.is_available():
            logger.info("Cloud review skipped (disabled or no API key)")
            return None

        # Load template
        template_path = Path(prompt_template_path)
        if template_path.exists():
            template = template_path.read_text()
        else:
            template = (
                "Review this runbook draft.\n\n"
                "## Facts\n{facts}\n\n"
                "## Draft\n{draft}\n\n"
                "## Review\n"
            )

        prompt = template.format(facts=facts_text, draft=draft_text)

        if self.provider == "openai":
            return self._call_openai(prompt)
        elif self.provider == "anthropic":
            return self._call_anthropic(prompt)
        else:
            logger.error(f"Unknown provider: {self.provider}")
            return None

    def _call_openai(self, prompt: str) -> str:
        """Call OpenAI API."""
        import requests

        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a senior SRE. Review the runbook and provide root cause analysis.",
                },
                {"role": "user", "content": prompt},
            ],
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }

        logger.info(f"Calling OpenAI ({self.model}) for review ...")
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()

        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        logger.info(
            f"Cloud review done: {usage.get('prompt_tokens', '?')} prompt + "
            f"{usage.get('completion_tokens', '?')} completion tokens"
        )
        return content.strip()

    def _call_anthropic(self, prompt: str) -> str:
        """Call Anthropic API."""
        import requests

        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }
        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "system": "You are a senior SRE. Review the runbook and provide root cause analysis.",
            "messages": [{"role": "user", "content": prompt}],
        }

        logger.info(f"Calling Anthropic ({self.model}) for review ...")
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()

        content = data["content"][0]["text"]
        usage = data.get("usage", {})
        logger.info(
            f"Cloud review done: {usage.get('input_tokens', '?')} input + "
            f"{usage.get('output_tokens', '?')} output tokens"
        )
        return content.strip()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    ap = argparse.ArgumentParser(description="Cloud review (one-shot)")
    ap.add_argument("--facts", required=True, help="Path to facts JSON")
    ap.add_argument("--draft", required=True, help="Path to draft text")
    ap.add_argument("--config", default="config.yaml")
    args = ap.parse_args()

    # Load inputs
    facts_data = json.loads(Path(args.facts).read_text())
    # Reconstruct facts_text from JSON
    lines = []
    for fact in facts_data.get("facts", []):
        lines.append(f"[{fact['category']}] {fact['value']}")
    facts_text = "\n".join(lines)

    draft_text = Path(args.draft).read_text()

    reviewer = CloudReviewer(config_path=args.config)
    result = reviewer.review(facts_text, draft_text)
    if result:
        print(result)
    else:
        print("Review skipped (disabled or unavailable)")


if __name__ == "__main__":
    main()
