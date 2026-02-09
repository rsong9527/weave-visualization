"""Tests for Evidence Bundle schema and parser."""

import json
import pytest
from pathlib import Path

from k8s_copilot.schemas.evidence_bundle import (
    EvidenceBundle,
    ClusterMetadata,
    TaskType,
    parse_evidence_bundle,
)


# ─── Fixtures ────────────────────────────────────────────────────────────────

MINIMAL_EVIDENCE = {
    "task_type": "diagnose",
    "pods_overview": "NAMESPACE  NAME  READY  STATUS\ndefault    test  1/1    Running",
    "cluster_info": "Server Version: v1.28.4",
    "pod_describe": "Name: test\nStatus: Running\nEvents:\n  Normal  Scheduled  1m  default-scheduler  OK",
}

FULL_EVIDENCE = {
    **MINIMAL_EVIDENCE,
    "pod_logs": "2026-01-01 some log line",
    "events": "NAMESPACE  LAST SEEN  TYPE  REASON  OBJECT  MESSAGE\ndefault  1m  Normal  Scheduled  pod/test  OK",
    "helm_list": "NAME  NAMESPACE  REVISION  STATUS  CHART",
    "values_yaml": "replicaCount: 1",
    "cluster_metadata": {
        "k8s_version": "v1.28.4",
        "cri": "containerd 1.7.11",
        "cni": "calico 3.26",
        "os": "Ubuntu 22.04",
    },
}


# ─── Tests ───────────────────────────────────────────────────────────────────

class TestEvidenceBundle:
    """Test Evidence Bundle creation and validation."""

    def test_minimal_valid(self):
        bundle = EvidenceBundle(**MINIMAL_EVIDENCE)
        assert bundle.task_type == TaskType.DIAGNOSE
        assert "test" in bundle.pods_overview

    def test_full_valid(self):
        bundle = EvidenceBundle(**FULL_EVIDENCE)
        assert bundle.cluster_metadata is not None
        assert bundle.cluster_metadata.k8s_version == "v1.28.4"

    def test_missing_pods_overview(self):
        data = {**MINIMAL_EVIDENCE}
        del data["pods_overview"]
        with pytest.raises(Exception):  # ValidationError
            EvidenceBundle(**data)

    def test_missing_cluster_info(self):
        data = {**MINIMAL_EVIDENCE}
        del data["cluster_info"]
        with pytest.raises(Exception):
            EvidenceBundle(**data)

    def test_diagnose_needs_evidence(self):
        """Diagnose task requires at least one of: pod_describe, pod_logs, events."""
        data = {
            "task_type": "diagnose",
            "pods_overview": "NAMESPACE  NAME  READY  STATUS\ndefault    test  1/1    Running",
            "cluster_info": "Server Version: v1.28.4",
        }
        with pytest.raises(ValueError, match="Missing required evidence"):
            EvidenceBundle(**data)

    def test_install_needs_component(self):
        data = {
            "task_type": "install",
            "pods_overview": "NAMESPACE  NAME  READY  STATUS\ndefault    test  1/1    Running",
            "cluster_info": "Server Version: v1.28.4",
        }
        with pytest.raises(ValueError, match="component_name"):
            EvidenceBundle(**data)

    def test_config_fix_needs_values_or_describe(self):
        data = {
            "task_type": "config_fix",
            "pods_overview": "NAMESPACE  NAME  READY  STATUS\ndefault    test  1/1    Running",
            "cluster_info": "Server Version: v1.28.4",
        }
        with pytest.raises(ValueError, match="values_yaml.*pod_describe"):
            EvidenceBundle(**data)


class TestContextString:
    """Test the to_context_string method."""

    def test_contains_all_sections(self):
        bundle = EvidenceBundle(**FULL_EVIDENCE)
        ctx = bundle.to_context_string()
        assert "# Evidence Bundle" in ctx
        assert "Pods Overview" in ctx
        assert "Cluster Info" in ctx
        assert "Pod Describe" in ctx

    def test_contains_metadata(self):
        bundle = EvidenceBundle(**FULL_EVIDENCE)
        ctx = bundle.to_context_string()
        assert "v1.28.4" in ctx
        assert "containerd" in ctx

    def test_contains_user_question(self):
        data = {**MINIMAL_EVIDENCE, "user_question": "Why is my pod failing?"}
        bundle = EvidenceBundle(**data)
        ctx = bundle.to_context_string()
        assert "Why is my pod failing?" in ctx


class TestMissingRecommendations:
    """Test the get_missing_recommendations method."""

    def test_minimal_has_recommendations(self):
        bundle = EvidenceBundle(**MINIMAL_EVIDENCE)
        recs = bundle.get_missing_recommendations()
        assert len(recs) > 0

    def test_full_has_fewer_recommendations(self):
        bundle = EvidenceBundle(**FULL_EVIDENCE)
        recs_full = bundle.get_missing_recommendations()
        bundle_min = EvidenceBundle(**MINIMAL_EVIDENCE)
        recs_min = bundle_min.get_missing_recommendations()
        assert len(recs_full) < len(recs_min)


class TestParseEvidenceBundle:
    """Test parsing from various input formats."""

    def test_from_dict(self):
        bundle = parse_evidence_bundle(MINIMAL_EVIDENCE)
        assert isinstance(bundle, EvidenceBundle)

    def test_from_json_string(self):
        json_str = json.dumps(MINIMAL_EVIDENCE)
        bundle = parse_evidence_bundle(json_str)
        assert isinstance(bundle, EvidenceBundle)

    def test_from_file(self, tmp_path):
        filepath = tmp_path / "evidence.json"
        filepath.write_text(json.dumps(MINIMAL_EVIDENCE))
        bundle = parse_evidence_bundle(filepath)
        assert isinstance(bundle, EvidenceBundle)

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            parse_evidence_bundle(Path("/nonexistent/evidence.json"))
