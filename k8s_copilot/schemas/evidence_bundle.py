"""
Evidence Bundle Schema & Parser

Defines the structured input format that the copilot requires.
Enforces mandatory fields to prevent the model from hallucinating.
"""

from __future__ import annotations

import json
import subprocess
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class TaskType(str, Enum):
    """Supported copilot task types."""
    DIAGNOSE = "diagnose"
    INSTALL = "install"
    CONFIG_FIX = "config_fix"
    RUNBOOK = "runbook"


class ClusterMetadata(BaseModel):
    """Cluster environment metadata."""
    k8s_version: Optional[str] = Field(None, description="Kubernetes version, e.g. v1.28.4")
    cri: Optional[str] = Field(None, description="Container runtime, e.g. containerd 1.7.x")
    cni: Optional[str] = Field(None, description="CNI plugin, e.g. calico 3.26")
    storage_class: Optional[str] = Field(None, description="Default StorageClass, e.g. longhorn")
    os: Optional[str] = Field(None, description="Node OS, e.g. Ubuntu 22.04")


class EvidenceBundle(BaseModel):
    """
    Structured evidence input for the K8s/Helm Support Copilot.

    Forces users to provide real cluster data instead of vague descriptions.
    The copilot will ONLY reason over what is provided here.
    """

    # --- Task type ---
    task_type: TaskType = Field(
        default=TaskType.DIAGNOSE,
        description="What the user wants the copilot to do",
    )

    # --- Always required ---
    pods_overview: str = Field(
        ...,
        min_length=10,
        description="Output of: kubectl get pods -A -o wide",
    )
    cluster_info: str = Field(
        ...,
        min_length=5,
        description="Output of: kubectl version --short && kubectl cluster-info",
    )

    # --- Conditionally required (troubleshooting) ---
    pod_describe: Optional[str] = Field(
        None,
        description="Output of: kubectl describe pod <name> -n <ns>",
    )
    pod_logs: Optional[str] = Field(
        None,
        description="Output of: kubectl logs <name> -n <ns> --tail=200",
    )
    events: Optional[str] = Field(
        None,
        description="Output of: kubectl get events --sort-by=.lastTimestamp -A",
    )

    # --- Helm-specific ---
    helm_list: Optional[str] = Field(
        None,
        description="Output of: helm list -A",
    )
    helm_status: Optional[str] = Field(
        None,
        description="Output of: helm status <release> -n <ns>",
    )
    values_yaml: Optional[str] = Field(
        None,
        description="Relevant values.yaml content",
    )

    # --- Resource-specific ---
    storage_info: Optional[str] = Field(
        None,
        description="Output of: kubectl get sc,pv,pvc -A",
    )
    network_info: Optional[str] = Field(
        None,
        description="Output of: kubectl get svc,ing,netpol -A",
    )
    node_info: Optional[str] = Field(
        None,
        description="Output of: kubectl get nodes -o wide",
    )

    # --- Environment ---
    cluster_metadata: Optional[ClusterMetadata] = Field(
        default=None,
        description="Cluster environment metadata",
    )

    # --- User's question ---
    user_question: str = Field(
        default="Please diagnose the issues found in the evidence.",
        description="The specific question or request from the user",
    )

    # --- Install-specific ---
    component_name: Optional[str] = Field(
        None,
        description="Component to install (e.g. 'nginx-ingress', 'cert-manager')",
    )
    target_namespace: Optional[str] = Field(
        None,
        description="Target namespace for installation",
    )

    @model_validator(mode="after")
    def validate_task_requirements(self) -> "EvidenceBundle":
        """Ensure task-specific required fields are present."""
        missing = []

        if self.task_type == TaskType.DIAGNOSE:
            if not self.pod_describe and not self.pod_logs and not self.events:
                missing.append(
                    "Troubleshooting requires at least one of: "
                    "pod_describe, pod_logs, or events"
                )

        if self.task_type == TaskType.INSTALL:
            if not self.component_name:
                missing.append(
                    "Install task requires 'component_name' "
                    "(e.g. 'nginx-ingress', 'cert-manager')"
                )

        if self.task_type == TaskType.CONFIG_FIX:
            if not self.values_yaml and not self.pod_describe:
                missing.append(
                    "Config fix requires 'values_yaml' or 'pod_describe'"
                )

        if missing:
            raise ValueError(
                "Missing required evidence for task "
                f"'{self.task_type.value}':\n"
                + "\n".join(f"  - {m}" for m in missing)
            )

        return self

    def to_context_string(self) -> str:
        """Format the evidence bundle as a structured context string for the LLM."""
        sections = []

        sections.append("# Evidence Bundle\n")
        sections.append(f"**Task**: {self.task_type.value}")
        sections.append(f"**User Question**: {self.user_question}\n")

        if self.cluster_metadata:
            sections.append("## Cluster Metadata")
            meta = self.cluster_metadata
            for field_name in ["k8s_version", "cri", "cni", "storage_class", "os"]:
                val = getattr(meta, field_name)
                if val:
                    sections.append(f"- {field_name}: {val}")
            sections.append("")

        # Add all evidence sections
        evidence_fields = [
            ("cluster_info", "Cluster Info"),
            ("pods_overview", "Pods Overview (kubectl get pods -A -o wide)"),
            ("node_info", "Node Info"),
            ("pod_describe", "Pod Describe"),
            ("pod_logs", "Pod Logs (tail=200)"),
            ("events", "Events"),
            ("helm_list", "Helm Releases"),
            ("helm_status", "Helm Status"),
            ("values_yaml", "values.yaml"),
            ("storage_info", "Storage (SC/PV/PVC)"),
            ("network_info", "Network (SVC/Ingress/NetPol)"),
        ]

        for field_name, title in evidence_fields:
            val = getattr(self, field_name, None)
            if val:
                sections.append(f"## {title}")
                sections.append(f"```\n{val.strip()}\n```\n")

        if self.component_name:
            sections.append(f"## Install Target")
            sections.append(f"- Component: {self.component_name}")
            if self.target_namespace:
                sections.append(f"- Namespace: {self.target_namespace}")
            sections.append("")

        return "\n".join(sections)

    def get_missing_recommendations(self) -> list[str]:
        """Return recommendations for additional evidence that would improve diagnosis."""
        recommendations = []

        if not self.cluster_metadata:
            recommendations.append(
                "Provide cluster_metadata (k8s_version, cri, cni, storage_class, os) "
                "for more accurate diagnosis"
            )
        if not self.events:
            recommendations.append(
                "Run: kubectl get events --sort-by=.lastTimestamp -A"
            )
        if not self.node_info:
            recommendations.append(
                "Run: kubectl get nodes -o wide"
            )
        if self.task_type == TaskType.DIAGNOSE:
            if not self.pod_logs:
                recommendations.append(
                    "Run: kubectl logs <problematic-pod> -n <ns> --tail=200"
                )
            if not self.pod_describe:
                recommendations.append(
                    "Run: kubectl describe pod <problematic-pod> -n <ns>"
                )
        if self.task_type in (TaskType.INSTALL, TaskType.CONFIG_FIX):
            if not self.helm_list:
                recommendations.append("Run: helm list -A")
            if not self.storage_info:
                recommendations.append("Run: kubectl get sc,pv,pvc -A")

        return recommendations


def parse_evidence_bundle(source: str | dict | Path) -> EvidenceBundle:
    """Parse an evidence bundle from various input formats.

    Args:
        source: Can be a JSON string, a dict, or a Path to a JSON file.

    Returns:
        Validated EvidenceBundle instance.

    Raises:
        ValueError: If the input is invalid or missing required fields.
    """
    if isinstance(source, Path) or (isinstance(source, str) and source.endswith(".json")):
        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"Evidence file not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    elif isinstance(source, str):
        data = json.loads(source)
    elif isinstance(source, dict):
        data = source
    else:
        raise TypeError(f"Unsupported source type: {type(source)}")

    return EvidenceBundle(**data)


def _run_kubectl(cmd: str) -> str:
    """Run a kubectl command and return output, or error message."""
    try:
        result = subprocess.run(
            cmd.split(),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return f"[ERROR] {result.stderr.strip()}"
    except FileNotFoundError:
        return "[ERROR] kubectl not found in PATH"
    except subprocess.TimeoutExpired:
        return "[ERROR] Command timed out after 30s"
    except Exception as e:
        return f"[ERROR] {e}"


def collect_evidence_interactive(
    task_type: TaskType = TaskType.DIAGNOSE,
    pod_name: str | None = None,
    namespace: str | None = None,
    helm_release: str | None = None,
    component_name: str | None = None,
) -> EvidenceBundle:
    """Auto-collect evidence by running kubectl/helm commands on the local machine.

    This is a convenience function for when the copilot is running on a machine
    with kubectl access. For air-gapped usage, users should provide a JSON file.

    Args:
        task_type: The type of task to perform.
        pod_name: Specific pod to investigate.
        namespace: Namespace of the target pod/release.
        helm_release: Helm release name for Helm-related tasks.
        component_name: Component to install (for install tasks).

    Returns:
        Populated EvidenceBundle.
    """
    print("[*] Collecting evidence from cluster...")

    # Always collect
    cluster_info = _run_kubectl("kubectl version --short") + "\n"
    cluster_info += _run_kubectl("kubectl cluster-info")
    pods_overview = _run_kubectl("kubectl get pods -A -o wide")
    node_info = _run_kubectl("kubectl get nodes -o wide")
    events = _run_kubectl("kubectl get events --sort-by=.lastTimestamp -A")

    # Pod-specific
    pod_describe = None
    pod_logs = None
    if pod_name and namespace:
        pod_describe = _run_kubectl(
            f"kubectl describe pod {pod_name} -n {namespace}"
        )
        pod_logs = _run_kubectl(
            f"kubectl logs {pod_name} -n {namespace} --tail=200"
        )

    # Helm-specific
    helm_list = _run_kubectl("helm list -A")
    helm_status = None
    if helm_release:
        ns_flag = f"-n {namespace}" if namespace else ""
        helm_status = _run_kubectl(f"helm status {helm_release} {ns_flag}".strip())

    # Storage & Network
    storage_info = _run_kubectl("kubectl get sc,pv,pvc -A")
    network_info = _run_kubectl("kubectl get svc,ing,netpol -A")

    # Cluster metadata
    k8s_ver_raw = _run_kubectl("kubectl version -o json")
    k8s_version = None
    if not k8s_ver_raw.startswith("[ERROR]"):
        try:
            ver_data = json.loads(k8s_ver_raw)
            k8s_version = ver_data.get("serverVersion", {}).get("gitVersion")
        except json.JSONDecodeError:
            pass

    metadata = ClusterMetadata(k8s_version=k8s_version)

    print("[*] Evidence collection complete.")

    bundle_kwargs = dict(
        task_type=task_type,
        pods_overview=pods_overview,
        cluster_info=cluster_info,
        pod_describe=pod_describe,
        pod_logs=pod_logs,
        events=events,
        helm_list=helm_list,
        helm_status=helm_status,
        storage_info=storage_info,
        network_info=network_info,
        node_info=node_info,
        cluster_metadata=metadata,
    )

    if component_name:
        bundle_kwargs["component_name"] = component_name
    if namespace:
        bundle_kwargs["target_namespace"] = namespace

    return EvidenceBundle(**bundle_kwargs)
