"""Tests for the runbook generator."""

import pytest
from pathlib import Path

from k8s_copilot.generators.runbook import (
    generate_runbook,
    Runbook,
    RUNBOOK_TEMPLATES,
    list_runbook_templates,
)


class TestRunbook:
    """Test Runbook dataclass."""

    def test_to_markdown(self):
        rb = Runbook(
            title="Test Runbook",
            component="Pod",
            severity="P0",
            symptom="Pod is crashing",
            root_cause="OOMKilled",
            fix_procedure="Increase memory",
            rollback_procedure="Rollback deployment",
        )
        md = rb.to_markdown()
        assert "# Runbook: Test Runbook" in md
        assert "Pod is crashing" in md
        assert "OOMKilled" in md

    def test_save(self, tmp_path):
        rb = Runbook(title="Test Save Runbook")
        path = rb.save(tmp_path)
        assert path.exists()
        assert path.suffix == ".md"
        assert "runbook-" in path.name

    def test_empty_sections_render(self):
        rb = Runbook(title="Empty")
        md = rb.to_markdown()
        assert "To be documented" in md


class TestGenerateRunbook:
    """Test runbook generation."""

    def test_from_template(self):
        rb = generate_runbook(
            title="CrashLoop Issue",
            template_key="crashloopbackoff",
        )
        assert rb.title == "CrashLoop Issue"
        assert rb.symptom != ""
        assert "CrashLoopBackOff" in rb.symptom

    def test_from_template_with_override(self):
        rb = generate_runbook(
            title="Custom CrashLoop",
            template_key="crashloopbackoff",
            llm_content={"lessons_learned": "We should add better monitoring."},
        )
        assert "better monitoring" in rb.lessons_learned

    def test_unknown_template(self):
        rb = generate_runbook(
            title="Custom Issue",
            template_key="nonexistent",
        )
        assert rb.title == "Custom Issue"

    def test_no_template(self):
        rb = generate_runbook(title="Ad-hoc runbook")
        assert rb.title == "Ad-hoc runbook"


class TestRunbookTemplates:
    """Test built-in runbook templates."""

    def test_templates_exist(self):
        assert len(RUNBOOK_TEMPLATES) >= 3

    def test_crashloopbackoff_template(self):
        rb = RUNBOOK_TEMPLATES["crashloopbackoff"]
        assert rb.severity == "P0"
        assert "CrashLoopBackOff" in rb.symptom

    def test_imagepullbackoff_template(self):
        rb = RUNBOOK_TEMPLATES["imagepullbackoff"]
        assert "ImagePullBackOff" in rb.symptom

    def test_pvc_pending_template(self):
        rb = RUNBOOK_TEMPLATES["pvc_pending"]
        assert "PVC" in rb.title or "Pending" in rb.title

    def test_all_templates_have_fix(self):
        for key, rb in RUNBOOK_TEMPLATES.items():
            assert rb.fix_procedure, f"Template '{key}' has no fix_procedure"

    def test_all_templates_have_rollback(self):
        for key, rb in RUNBOOK_TEMPLATES.items():
            assert rb.rollback_procedure, f"Template '{key}' has no rollback_procedure"


class TestListTemplates:
    """Test template listing."""

    def test_returns_list(self):
        templates = list_runbook_templates()
        assert isinstance(templates, list)
        assert len(templates) >= 3

    def test_template_has_fields(self):
        templates = list_runbook_templates()
        for t in templates:
            assert "key" in t
            assert "title" in t
            assert "severity" in t
