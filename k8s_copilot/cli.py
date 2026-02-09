"""
K8s/Helm Support Copilot — CLI Interface

Usage:
    python -m k8s_copilot diagnose --evidence evidence.json
    python -m k8s_copilot install --component nginx-ingress --namespace ingress
    python -m k8s_copilot runbook --title "Pod CrashLoop" --template crashloopbackoff
    python -m k8s_copilot collect --pod my-pod --namespace default
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .copilot import K8sCopilot, CopilotConfig
from .schemas.evidence_bundle import (
    EvidenceBundle,
    TaskType,
    parse_evidence_bundle,
    collect_evidence_interactive,
)
from .generators.install_plan import generate_install_plan
from .generators.runbook import generate_runbook, list_runbook_templates


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="k8s-copilot",
        description="K8s/Helm Support Copilot — On-Prem, Offline-Capable",
    )

    # Global options
    parser.add_argument(
        "--backend",
        choices=["ollama", "openai"],
        default="ollama",
        help="LLM backend (default: ollama)",
    )
    parser.add_argument(
        "--model",
        default="qwen2.5:7b",
        help="Model name (default: qwen2.5:7b)",
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:11434",
        help="LLM API base URL (default: http://localhost:11434)",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.1,
        help="Generation temperature (default: 0.1)",
    )
    parser.add_argument(
        "--output", "-o",
        help="Output file path (default: stdout)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # --- diagnose ---
    diag = subparsers.add_parser("diagnose", help="Diagnose K8s issues from evidence")
    diag.add_argument(
        "--evidence", "-e",
        required=True,
        help="Path to evidence JSON file",
    )

    # --- install ---
    inst = subparsers.add_parser("install", help="Generate install plan")
    inst.add_argument(
        "--component", "-c",
        required=True,
        help="Component to install (e.g. nginx-ingress, cert-manager)",
    )
    inst.add_argument(
        "--namespace", "-n",
        default="default",
        help="Target namespace",
    )
    inst.add_argument(
        "--evidence", "-e",
        help="Optional evidence file for cluster-aware planning",
    )
    inst.add_argument(
        "--save-dir",
        help="Save install pack to this directory",
    )

    # --- config-fix ---
    fix = subparsers.add_parser("config-fix", help="Suggest configuration fixes")
    fix.add_argument(
        "--evidence", "-e",
        required=True,
        help="Path to evidence JSON file",
    )

    # --- runbook ---
    rb = subparsers.add_parser("runbook", help="Generate or use a runbook")
    rb.add_argument(
        "--title", "-t",
        help="Runbook title",
    )
    rb.add_argument(
        "--template",
        help="Use built-in template (e.g. crashloopbackoff, imagepullbackoff, pvc_pending)",
    )
    rb.add_argument(
        "--evidence", "-e",
        help="Evidence file for LLM-enhanced runbook",
    )
    rb.add_argument(
        "--list-templates",
        action="store_true",
        help="List available runbook templates",
    )
    rb.add_argument(
        "--save-dir",
        help="Save runbook to this directory",
    )

    # --- collect ---
    col = subparsers.add_parser("collect", help="Auto-collect evidence from cluster")
    col.add_argument(
        "--pod",
        help="Pod name to investigate",
    )
    col.add_argument(
        "--namespace", "-n",
        help="Namespace",
    )
    col.add_argument(
        "--helm-release",
        help="Helm release name",
    )
    col.add_argument(
        "--task-type",
        choices=["diagnose", "install", "config_fix", "runbook"],
        default="diagnose",
        help="Task type (default: diagnose)",
    )
    col.add_argument(
        "--component",
        help="Component name (for install tasks)",
    )

    return parser


def _write_output(content: str, output_path: str | None) -> None:
    """Write content to file or stdout."""
    if output_path:
        Path(output_path).write_text(content, encoding="utf-8")
        print(f"[*] Output written to: {output_path}", file=sys.stderr)
    else:
        print(content)


def main(argv: list[str] | None = None) -> int:
    parser = create_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 1

    # Build config
    config = CopilotConfig(
        backend=args.backend,
        model=args.model,
        base_url=args.base_url,
        temperature=args.temperature,
    )

    output_path = getattr(args, "output", None)

    # ── collect ──
    if args.command == "collect":
        task_type = TaskType(args.task_type)
        bundle = collect_evidence_interactive(
            task_type=task_type,
            pod_name=args.pod,
            namespace=args.namespace,
            helm_release=args.helm_release,
            component_name=args.component,
        )
        content = bundle.model_dump_json(indent=2)
        _write_output(content, output_path)
        return 0

    # ── runbook --list-templates ──
    if args.command == "runbook" and args.list_templates:
        templates = list_runbook_templates()
        print("Available Runbook Templates:\n")
        for t in templates:
            tags = ", ".join(t["tags"])
            print(f"  {t['key']:20s} [{t['severity']}] {t['title']} ({tags})")
        return 0

    # ── Commands that may need LLM ──
    copilot = K8sCopilot(config)

    try:
        if args.command == "diagnose":
            result = copilot.diagnose(Path(args.evidence))
            _write_output(result, output_path)

        elif args.command == "install":
            evidence = None
            if args.evidence:
                evidence = parse_evidence_bundle(Path(args.evidence))

            plan = copilot.generate_install(
                component_name=args.component,
                namespace=args.namespace,
                evidence=evidence,
            )

            if args.save_dir:
                saved_path = plan.save(args.save_dir)
                print(f"[*] Install pack saved to: {saved_path}", file=sys.stderr)
            else:
                _write_output(plan.to_markdown(), output_path)

        elif args.command == "config-fix":
            result = copilot.fix_config(Path(args.evidence))
            _write_output(result, output_path)

        elif args.command == "runbook":
            if not args.title and not args.template:
                print("Error: --title or --template required", file=sys.stderr)
                return 1

            evidence = None
            if args.evidence:
                evidence = parse_evidence_bundle(Path(args.evidence))

            runbook = copilot.create_runbook(
                title=args.title or "",
                evidence=evidence,
                template_key=args.template,
            )

            if args.save_dir:
                saved_path = runbook.save(args.save_dir)
                print(f"[*] Runbook saved to: {saved_path}", file=sys.stderr)
            else:
                _write_output(runbook.to_markdown(), output_path)

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
