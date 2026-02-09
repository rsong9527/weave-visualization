"""
K8s/Helm Support Copilot — Core Engine

Orchestrates: Evidence Bundle → System Prompt → LLM → Output Formatter

Supports multiple LLM backends:
  - Ollama (default, local)
  - OpenAI-compatible API (vLLM, llama.cpp server, etc.)
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from .schemas.evidence_bundle import EvidenceBundle, TaskType, parse_evidence_bundle
from .prompts.system_prompt import get_system_prompt
from .formatters.output_formatter import (
    DiagnosisOutput,
    format_diagnosis_output,
    parse_llm_response,
    validate_output_constraints,
)
from .generators.install_plan import generate_install_plan, InstallPlan
from .generators.runbook import generate_runbook, Runbook


class CopilotConfig:
    """Configuration for the copilot LLM backend."""

    def __init__(
        self,
        backend: str = "ollama",
        model: str = "qwen2.5:7b",
        base_url: str = "http://localhost:11434",
        api_key: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ):
        self.backend = backend
        self.model = model
        self.base_url = base_url
        self.api_key = api_key or os.getenv("LLM_API_KEY", "")
        self.temperature = temperature
        self.max_tokens = max_tokens


class K8sCopilot:
    """Main copilot engine.

    Usage:
        copilot = K8sCopilot()
        result = copilot.diagnose(evidence_bundle)
        print(result)
    """

    def __init__(self, config: CopilotConfig | None = None):
        self.config = config or CopilotConfig()

    def _call_llm(self, system_prompt: str, user_message: str) -> str:
        """Call the LLM backend and return the raw response.

        Supports:
          - ollama: Uses Ollama REST API
          - openai: Uses OpenAI-compatible API (vLLM, llama.cpp, etc.)

        For offline/air-gapped environments, Ollama is recommended.
        """
        if self.config.backend == "ollama":
            return self._call_ollama(system_prompt, user_message)
        elif self.config.backend == "openai":
            return self._call_openai_compatible(system_prompt, user_message)
        else:
            raise ValueError(f"Unknown backend: {self.config.backend}")

    def _call_ollama(self, system_prompt: str, user_message: str) -> str:
        """Call Ollama REST API."""
        import httpx

        url = f"{self.config.base_url}/api/chat"
        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "stream": False,
            "options": {
                "temperature": self.config.temperature,
                "num_predict": self.config.max_tokens,
            },
        }

        response = httpx.post(url, json=payload, timeout=300)
        response.raise_for_status()
        data = response.json()
        return data.get("message", {}).get("content", "")

    def _call_openai_compatible(self, system_prompt: str, user_message: str) -> str:
        """Call OpenAI-compatible API (vLLM, llama.cpp server, etc.)."""
        import httpx

        url = f"{self.config.base_url}/v1/chat/completions"
        headers = {}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"

        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }

        response = httpx.post(url, json=payload, headers=headers, timeout=300)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]

    # ─── Public API ──────────────────────────────────────────────────────

    def diagnose(self, evidence: EvidenceBundle | str | dict | Path) -> str:
        """Run a diagnosis on the provided evidence.

        Args:
            evidence: Evidence bundle (object, JSON string, dict, or file path).

        Returns:
            Formatted Markdown diagnosis (5-section output).
        """
        if not isinstance(evidence, EvidenceBundle):
            evidence = parse_evidence_bundle(evidence)

        system_prompt = get_system_prompt("diagnose")
        user_message = evidence.to_context_string()

        # Add recommendations for missing evidence
        recommendations = evidence.get_missing_recommendations()
        if recommendations:
            user_message += "\n\n## Recommendations for Better Diagnosis\n"
            user_message += "The following additional evidence would improve diagnosis:\n"
            for rec in recommendations:
                user_message += f"- {rec}\n"

        raw_response = self._call_llm(system_prompt, user_message)
        return format_diagnosis_output(raw_response)

    def generate_install(
        self,
        component_name: str,
        namespace: str = "default",
        evidence: EvidenceBundle | None = None,
    ) -> InstallPlan:
        """Generate an install plan for a K8s component.

        Args:
            component_name: Component to install.
            namespace: Target namespace.
            evidence: Optional evidence bundle for context.

        Returns:
            Complete InstallPlan with all 5 files.
        """
        # Ask LLM for customized values.yaml if evidence is provided
        llm_values = None
        llm_notes = None

        if evidence:
            system_prompt = get_system_prompt("install")
            context = evidence.to_context_string()
            context += f"\n\n## Install Request\n"
            context += f"Component: {component_name}\n"
            context += f"Namespace: {namespace}\n"
            context += (
                "\nBased on the cluster state above, generate:\n"
                "1. A customized values.yaml\n"
                "2. Any important notes for this specific cluster\n"
            )

            raw_response = self._call_llm(system_prompt, context)

            # Try to extract values.yaml from response
            import re
            yaml_match = re.search(
                r"```ya?ml\n([\s\S]*?)```", raw_response
            )
            if yaml_match:
                llm_values = yaml_match.group(1)

            # Extract notes
            notes_match = re.search(
                r"(?:notes?|important|注意)[:\s]*([\s\S]*?)(?:```|$)",
                raw_response,
                re.IGNORECASE,
            )
            if notes_match:
                llm_notes = notes_match.group(1).strip()

        return generate_install_plan(
            component_name=component_name,
            namespace=namespace,
            llm_values_yaml=llm_values,
            llm_extra_notes=llm_notes,
        )

    def fix_config(self, evidence: EvidenceBundle | str | dict | Path) -> str:
        """Suggest configuration fixes based on evidence.

        Args:
            evidence: Evidence bundle with values.yaml or pod describe.

        Returns:
            Formatted Markdown with fix suggestions.
        """
        if not isinstance(evidence, EvidenceBundle):
            evidence = parse_evidence_bundle(evidence)

        system_prompt = get_system_prompt("config_fix")
        user_message = evidence.to_context_string()

        raw_response = self._call_llm(system_prompt, user_message)
        return format_diagnosis_output(raw_response)

    def create_runbook(
        self,
        title: str,
        evidence: EvidenceBundle | str | dict | Path | None = None,
        template_key: str | None = None,
    ) -> Runbook:
        """Create a runbook from a resolved incident.

        Args:
            title: Runbook title.
            evidence: Optional evidence from the incident.
            template_key: Use a built-in template as base.

        Returns:
            Runbook instance.
        """
        llm_content = None

        if evidence:
            if not isinstance(evidence, EvidenceBundle):
                evidence = parse_evidence_bundle(evidence)

            system_prompt = get_system_prompt("runbook")
            context = evidence.to_context_string()
            context += f"\n\n## Runbook Request\nTitle: {title}\n"
            context += (
                "Create a runbook with these sections:\n"
                "- symptom\n- root_cause\n- verification_steps\n"
                "- fix_procedure\n- rollback_procedure\n- lessons_learned\n"
            )

            raw_response = self._call_llm(system_prompt, context)

            # Parse sections from LLM response
            llm_content = {}
            section_map = {
                r"symptom": "symptom",
                r"root.?cause": "root_cause",
                r"verif": "verification_steps",
                r"fix": "fix_procedure",
                r"rollback": "rollback_procedure",
                r"lesson": "lessons_learned",
            }

            import re
            for pattern, field_name in section_map.items():
                match = re.search(
                    rf"#{1,3}\s*.*?{pattern}.*?\n([\s\S]*?)(?=#{1,3}\s|\Z)",
                    raw_response,
                    re.IGNORECASE,
                )
                if match:
                    llm_content[field_name] = match.group(1).strip()

        return generate_runbook(
            title=title,
            template_key=template_key,
            llm_content=llm_content,
        )
