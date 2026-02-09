"""
Runbook Generator

Converts a resolved incident into a reusable runbook:
  Symptom → Root Cause → Verification → Fix → Rollback → Lessons Learned

Can be used standalone or as part of the diagnostic flow.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from textwrap import dedent
from typing import Optional


@dataclass
class Runbook:
    """A structured runbook from a resolved incident."""

    # Meta
    title: str = ""
    component: str = ""
    severity: str = "P1"  # P0/P1/P2
    created_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    tags: list[str] = field(default_factory=list)

    # Sections
    symptom: str = ""
    root_cause: str = ""
    verification_steps: str = ""
    fix_procedure: str = ""
    rollback_procedure: str = ""
    lessons_learned: str = ""

    # Optional
    related_docs: list[str] = field(default_factory=list)
    time_to_resolve: str = ""

    def to_markdown(self) -> str:
        """Render the runbook as a Markdown document."""
        tags_str = ", ".join(f"`{t}`" for t in self.tags) if self.tags else "_none_"

        sections = [
            f"# Runbook: {self.title}\n",
            f"| Field | Value |",
            f"|-------|-------|",
            f"| Component | {self.component} |",
            f"| Severity | {self.severity} |",
            f"| Created | {self.created_at} |",
            f"| Tags | {tags_str} |",
        ]

        if self.time_to_resolve:
            sections.append(f"| TTR | {self.time_to_resolve} |")

        sections.append("\n---\n")

        # Main sections
        section_data = [
            ("Symptom", self.symptom),
            ("Root Cause", self.root_cause),
            ("Verification Steps", self.verification_steps),
            ("Fix Procedure", self.fix_procedure),
            ("Rollback Procedure", self.rollback_procedure),
            ("Lessons Learned", self.lessons_learned),
        ]

        for heading, content in section_data:
            sections.append(f"## {heading}\n")
            sections.append(content or "_To be documented._")
            sections.append("")

        # Related docs
        if self.related_docs:
            sections.append("## Related Documentation\n")
            for doc in self.related_docs:
                sections.append(f"- {doc}")

        return "\n".join(sections)

    def save(self, output_dir: str | Path) -> Path:
        """Save the runbook as a Markdown file.

        Args:
            output_dir: Directory to save in.

        Returns:
            Path to the saved file.
        """
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        # Generate filename from title
        safe_title = re.sub(r"[^\w\s-]", "", self.title.lower())
        safe_title = re.sub(r"[\s]+", "-", safe_title).strip("-")
        filename = f"runbook-{safe_title}-{self.created_at}.md"

        filepath = out / filename
        filepath.write_text(self.to_markdown(), encoding="utf-8")
        return filepath


# ─── Templates for common K8s issues ────────────────────────────────────────

RUNBOOK_TEMPLATES = {
    "crashloopbackoff": Runbook(
        title="Pod CrashLoopBackOff",
        component="Pod",
        severity="P0",
        tags=["pod", "crashloop", "restart"],
        symptom=dedent("""\
Pod is in CrashLoopBackOff state. `kubectl get pods` shows high restart count.
Container exits shortly after starting.
""").strip(),
        verification_steps=dedent("""\
1. Check pod status:
   ```bash
   kubectl get pod <POD_NAME> -n <NAMESPACE>
   ```

2. Check recent events:
   ```bash
   kubectl describe pod <POD_NAME> -n <NAMESPACE> | grep -A 20 Events
   ```

3. Check container logs (current + previous):
   ```bash
   kubectl logs <POD_NAME> -n <NAMESPACE> --tail=100
   kubectl logs <POD_NAME> -n <NAMESPACE> --previous --tail=100
   ```

4. Check resource usage:
   ```bash
   kubectl top pod <POD_NAME> -n <NAMESPACE>
   ```
""").strip(),
        fix_procedure=dedent("""\
**Common fixes (in order of likelihood):**

1. **Application error** — Check logs for stack traces:
   ```bash
   kubectl logs <POD_NAME> -n <NAMESPACE> --previous
   ```

2. **OOMKilled** — Increase memory limits:
   ```yaml
   resources:
     limits:
       memory: "512Mi"  # Increase as needed
   ```

3. **Missing config/secrets** — Verify mounts:
   ```bash
   kubectl describe pod <POD_NAME> -n <NAMESPACE> | grep -A 5 "Mounts"
   ```

4. **Liveness probe too aggressive** — Increase thresholds:
   ```yaml
   livenessProbe:
     initialDelaySeconds: 30
     periodSeconds: 10
     failureThreshold: 5
   ```
""").strip(),
        rollback_procedure=dedent("""\
If the fix involves a Helm release:
```bash
helm rollback <RELEASE> -n <NAMESPACE> --wait
```

If manually edited deployment:
```bash
kubectl rollout undo deployment/<DEPLOYMENT> -n <NAMESPACE>
```
""").strip(),
        lessons_learned="Document the root cause and add monitoring/alerts for early detection.",
    ),

    "imagepullbackoff": Runbook(
        title="ImagePullBackOff",
        component="Pod",
        severity="P0",
        tags=["pod", "image", "registry", "pull"],
        symptom="Pod stuck in ImagePullBackOff or ErrImagePull state.",
        verification_steps=dedent("""\
1. Check pod events for pull errors:
   ```bash
   kubectl describe pod <POD_NAME> -n <NAMESPACE> | grep -A 5 "Events"
   ```

2. Verify image exists:
   ```bash
   # For Docker Hub
   docker manifest inspect <IMAGE>:<TAG>
   # Or use crane/skopeo for private registries
   ```

3. Check imagePullSecrets:
   ```bash
   kubectl get pod <POD_NAME> -n <NAMESPACE> -o jsonpath='{.spec.imagePullSecrets}'
   ```

4. Test registry access from node:
   ```bash
   crictl pull <IMAGE>:<TAG>
   ```
""").strip(),
        fix_procedure=dedent("""\
1. **Wrong image name/tag** — Fix the image reference:
   ```bash
   kubectl set image deployment/<DEPLOY> <CONTAINER>=<CORRECT_IMAGE>:<TAG> -n <NS>
   ```

2. **Missing pull secret** — Create and attach:
   ```bash
   kubectl create secret docker-registry regcred \\
     --docker-server=<REGISTRY> \\
     --docker-username=<USER> \\
     --docker-password=<PASS> \\
     -n <NAMESPACE>
   ```

3. **Private registry in air-gapped env** — Push image to local registry:
   ```bash
   docker tag <IMAGE>:<TAG> <LOCAL_REGISTRY>/<IMAGE>:<TAG>
   docker push <LOCAL_REGISTRY>/<IMAGE>:<TAG>
   ```
""").strip(),
        rollback_procedure=dedent("""\
```bash
kubectl rollout undo deployment/<DEPLOYMENT> -n <NAMESPACE>
```
""").strip(),
        lessons_learned="Ensure image references are pinned to digests in production. Set up image mirroring for air-gapped environments.",
    ),

    "pvc_pending": Runbook(
        title="PVC Stuck in Pending",
        component="Storage",
        severity="P1",
        tags=["pvc", "storage", "storageclass"],
        symptom="PersistentVolumeClaim stuck in Pending state. Pods using this PVC cannot start.",
        verification_steps=dedent("""\
1. Check PVC status:
   ```bash
   kubectl get pvc -n <NAMESPACE>
   kubectl describe pvc <PVC_NAME> -n <NAMESPACE>
   ```

2. Check StorageClass:
   ```bash
   kubectl get sc
   kubectl describe sc <STORAGE_CLASS>
   ```

3. Check available PVs (for static provisioning):
   ```bash
   kubectl get pv
   ```

4. Check CSI driver pods:
   ```bash
   kubectl get pods -n kube-system -l app=csi-*
   ```
""").strip(),
        fix_procedure=dedent("""\
1. **No default StorageClass** — Set one:
   ```bash
   kubectl patch sc <SC_NAME> -p '{"metadata":{"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}'
   ```

2. **Wrong StorageClass in PVC** — Recreate PVC with correct SC:
   ```yaml
   apiVersion: v1
   kind: PersistentVolumeClaim
   metadata:
     name: <PVC_NAME>
     namespace: <NAMESPACE>
   spec:
     accessModes: ["ReadWriteOnce"]
     storageClassName: <CORRECT_SC>
     resources:
       requests:
         storage: 10Gi
   ```

3. **CSI driver not running** — Check and restart:
   ```bash
   kubectl rollout restart daemonset/<CSI_DRIVER> -n kube-system
   ```
""").strip(),
        rollback_procedure=dedent("""\
PVC changes are generally safe. To revert:
```bash
kubectl delete pvc <PVC_NAME> -n <NAMESPACE>
# Re-apply original PVC manifest
kubectl apply -f original-pvc.yaml
```

**Warning**: Deleting a PVC may delete the underlying PV (depends on reclaim policy).
""").strip(),
        lessons_learned="Always specify storageClassName explicitly in PVC manifests. Monitor CSI driver health.",
    ),
}


def generate_runbook(
    title: str,
    template_key: str | None = None,
    llm_content: dict[str, str] | None = None,
    **kwargs,
) -> Runbook:
    """Generate a runbook from template or LLM content.

    Args:
        title: Runbook title.
        template_key: Key for a built-in template (e.g. 'crashloopbackoff').
        llm_content: Dict with section content from LLM response.
        **kwargs: Additional Runbook fields.

    Returns:
        Populated Runbook instance.
    """
    # Start from template if available
    if template_key and template_key in RUNBOOK_TEMPLATES:
        runbook = RUNBOOK_TEMPLATES[template_key]
        # Override title if provided
        runbook.title = title or runbook.title
    else:
        runbook = Runbook(title=title, **kwargs)

    # Overlay LLM-generated content
    if llm_content:
        for field_name, value in llm_content.items():
            if hasattr(runbook, field_name) and value:
                setattr(runbook, field_name, value)

    return runbook


def list_runbook_templates() -> list[dict[str, str]]:
    """List available runbook templates.

    Returns:
        List of dicts with 'key', 'title', 'severity' for each template.
    """
    return [
        {
            "key": key,
            "title": rb.title,
            "severity": rb.severity,
            "tags": rb.tags,
        }
        for key, rb in RUNBOOK_TEMPLATES.items()
    ]
